#include "studio_worker.h"
#include "pipeline_manager.h"
#include "src/diagnostics/logger.h"
#include "src/storage/config_mgr.h"
#include "src/engine/models/textbpn_engine.h"
#include "src/engine/models/moebius_engine.h"
#include "src/engine/models/lama_engine.h"
#include "src/core/image_ops/inpaint_router.h"
#include <algorithm>

studio_worker::studio_worker(task_queue* queue, session_data* session, history_stack* history, AI_Engine_Pack models,
    std::shared_ptr<std::mutex> inference_mutex, pipeline_manager* pipeline, QObject* parent)
    : QThread(parent), m_queue(queue), m_session(session), m_history(history), m_models(models),
      m_inference_mutex(std::move(inference_mutex)), m_pipeline(pipeline) {
    LOG_TRACE("Studio Worker background thread initialized.");
}

studio_worker::~studio_worker() {
    wait();
}

void studio_worker::run() {
    LOG_INFO("Studio Worker background thread is active and listening for tasks.");
    AI_Task current_task;

    while (m_queue->pop_task(current_task)) {
        if (!m_session || !m_session->has_active_image()) {
            LOG_WARN("Studio Worker received task, but no image is active.");
            emit error_occurred("No active image on canvas.");
            emit task_finished(false);
            m_queue->rearm();
            continue;
        }

        try {
            // Serialize all GPU work: the batch worker shares these exact engine
            // objects, execution contexts and CUDA stream, so only one inference
            // (studio or batch) may be in flight at any moment.
            std::unique_lock<std::mutex> gpu_lock;
            if (m_inference_mutex) gpu_lock = std::unique_lock<std::mutex>(*m_inference_mutex);

            if (current_task.type == AI_TaskType::RunOCR) {
                if (m_pipeline && !m_pipeline->ensure_model_loaded(pipeline_manager::EngineBpn)) {
                    emit error_occurred("Could not load the TextBPN++ engine into VRAM (free memory or engine pack missing).");
                    emit task_finished(false);
                    continue;
                }
                process_ocr(current_task);
            }
            else if (current_task.type == AI_TaskType::RunClean) {
                const InpaintEngine engine = inpaint_router::resolve(
                    current_task.inpaint_engine, m_session->get_current_image(), m_session->get_current_mask());
                if (m_pipeline && !ensure_inpaint_engine_loaded(engine)) {
                    emit error_occurred("Could not load the inpainting engine into VRAM (free memory or engine pack missing).");
                    emit task_finished(false);
                    continue;
                }
                process_clean(current_task);
            }
        }
        catch (const cv::Exception& e) {
            LOG_ERROR(QString("OpenCV Exception in Studio Worker: ") + e.what());
            emit error_occurred("OpenCV Math Error. Check logs.");
            emit task_finished(false); // terminal signal: UI reset + persistence hook
        }
        catch (const std::exception& e) {
            LOG_ERROR(QString("Standard Exception in Studio Worker: ") + e.what());
            emit error_occurred("Fatal Pipeline Error. Check logs.");
            emit task_finished(false);
        }

        // The task above has been processed. A Stop pressed during it stayed
        // raised the whole time (that is what let the engines abort at their
        // checkpoints); clear it only now, so the next user request starts clean.
        m_queue->rearm();
    }
}

// === VRAM BUDGETING: load the right inpainting engine before the stage runs ===
bool studio_worker::ensure_inpaint_engine_loaded(InpaintEngine engine) {
    if (!m_pipeline) return true; // No budget manager attached: old behavior.

    // Graceful fallback if the preferred engine's pack is not resident-able.
    if (engine == InpaintEngine::LaMa && !m_models.lama) engine = InpaintEngine::Moebius;
    if (engine == InpaintEngine::Moebius && !m_models.moebius) engine = InpaintEngine::LaMa;

    const pipeline_manager::EngineId id = (engine == InpaintEngine::LaMa)
        ? pipeline_manager::EngineLama
        : pipeline_manager::EngineMoebius;

    return m_pipeline->ensure_model_loaded(id);
}

// === STAGE 1: TEXT & SFX DETECTION (TextBPN++) ===
void studio_worker::process_ocr(const AI_Task& task) {
    if (!m_models.bpn || !m_models.bpn->is_loaded()) {
        emit error_occurred("TextBPN++ engine is not resident in VRAM.");
        emit task_finished(false);
        return;
    }

    emit task_started("Detecting Text & Sound Effects...");
    emit progress_updated(10);

    cv::Mat current_img = m_session->get_current_image();
    cv::Mat old_mask = m_session->get_current_mask();

    AppSettings s = config_mgr::instance().get_settings();

    float cls_thresh = (s.bpn_prob * 0.01f);
    float dis_thresh = (s.bpn_core * 0.01f);
    int dilation_rad = s.bpn_expand;

    TextBpnResult result = m_models.bpn->detect(
        current_img,
        cls_thresh,
        dis_thresh,
        100,            // Post-filter: ignore masks smaller than 100 px
        dilation_rad    // Elliptical dilation padding
    );

    emit progress_updated(85);

    if (result.full_mask.empty()) {
        // No region survived the confidence/area filters: a legitimate outcome
        // (clean page, thresholds too strict), not a fault. Report it, reset the
        // pipeline state and re-enable the UI - never leave it on "working".
        LOG_WARN("TextBPN++ detected no text or sound effects on active page.");
        emit error_occurred("No text or sound effects found on this page.");
        emit task_finished(false);
        return;
    }

    // Save previous mask state for undo/redo
    m_history->commit_mask_state(old_mask, result.full_mask);

    // Apply detected mask to active session
    m_session->set_mask(result.full_mask);

    emit progress_updated(100);
    LOG_INFO(QString("TextBPN++ detection completed. Found %1 regions.").arg(result.num_bubbles));
    emit task_finished(true);
}

// === STAGE 2: INPAINTING (Moebius latent suite / LaMa fast pass) ===
void studio_worker::process_clean(const AI_Task& task) {
    cv::Mat current_img = m_session->get_current_image();
    cv::Mat current_mask = m_session->get_current_mask();

    if (cv::countNonZero(current_mask) == 0) {
        emit error_occurred("Mask is empty. Draw or detect a mask first.");
        emit task_finished(false);
        return;
    }

    if (!m_models.moebius && !m_models.lama) {
        emit error_occurred("No inpainting engine is initialized.");
        emit task_finished(false);
        return;
    }

    // 1. Resolve the inpainting backend. Auto routes by the pixels SURROUNDING
    // each region: flat fills / single-hue gradients (speech bubbles, screentone
    // panels) go to LaMa; detailed art goes to Moebius.
    InpaintEngine engine = inpaint_router::resolve(task.inpaint_engine, current_img, current_mask);
    if (engine == InpaintEngine::LaMa && !m_models.lama) engine = InpaintEngine::Moebius;
    if (engine == InpaintEngine::Moebius && !m_models.moebius) engine = InpaintEngine::LaMa;

    const bool use_lama = (engine == InpaintEngine::LaMa);
    AppSettings s = config_mgr::instance().get_settings();
    emit task_started(use_lama ? "Inpainting Background (LaMa fast pass)..."
                               : QString("Inpainting Background (Moebius - %1 DDIM Steps)...").arg(s.moebius_steps));
    emit progress_updated(5);

    // 2. Extract region centroids from the current mask
    cv::Mat labels, stats, centroids;
    const int num_labels = cv::connectedComponentsWithStats(current_mask, labels, stats, centroids, 8, CV_32S);

    std::vector<cv::Point> bubble_centers;
    for (int i = 1; i < num_labels; ++i) {
        const int area = stats.at<int>(i, cv::CC_STAT_AREA);
        if (area < 10) continue; // Skip single stray noise pixels

        const double cx = centroids.at<double>(i, 0);
        const double cy = centroids.at<double>(i, 1);
        bubble_centers.push_back(cv::Point(static_cast<int>(cx), static_cast<int>(cy)));
    }

    // Bounding box of everything we may touch: also keeps the undo snapshot small
    // instead of cloning the entire page twice per operation.
    cv::Rect dirty = cv::boundingRect(current_mask) & cv::Rect(0, 0, current_img.cols, current_img.rows);
    if (dirty.area() == 0) dirty = cv::Rect(0, 0, current_img.cols, current_img.rows);

    if (bubble_centers.empty()) {
        bubble_centers.push_back(cv::Point(dirty.x + dirty.width / 2, dirty.y + dirty.height / 2));
    }

    // 3. Snapshot only the affected region for undo history.
    cv::Mat before_patch = current_img(dirty).clone();

    auto progress_cb = [this](int current, int total) {
        if (total <= 0) return;
        const int pct = 5 + static_cast<int>((static_cast<float>(current) / total) * 90.0f);
        emit progress_updated(pct);
    };

    const bool success = use_lama
        ? m_models.lama->inpaint_image(current_img, current_mask, bubble_centers, progress_cb)
        : m_models.moebius->inpaint_image(current_img, current_mask, bubble_centers, s.moebius_steps, progress_cb);

    if (!success) {
        if (task_cancel_requested()) {
            // User pressed Stop: not an error. Reset the progress UI quietly.
            LOG_INFO("Inpainting cancelled by user.");
            emit progress_updated(0);
        }
        else {
            emit error_occurred(use_lama ? "LaMa inpainting execution failed."
                                         : "Moebius inpainting execution failed.");
        }
        emit task_finished(false);
        return;
    }

    // 4. Record only the changed region in the history stack.
    m_history->commit_image_patch(dirty, before_patch, current_img(dirty));

    // 5. Update canvas and clear mask
    m_session->replace_image(current_img);
    m_session->set_mask(cv::Mat::zeros(current_img.size(), CV_8UC1));

    emit progress_updated(100);
    LOG_INFO(use_lama ? "LaMa inpainting completed successfully."
                      : "Moebius inpainting completed successfully.");
    emit task_finished(true);
}

