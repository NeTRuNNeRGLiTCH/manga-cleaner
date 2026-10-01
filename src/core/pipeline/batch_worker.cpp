#include "batch_worker.h"
#include "pipeline_manager.h"
#include "src/diagnostics/logger.h"
#include "src/storage/config_mgr.h"
#include "src/storage/psd_exporter.h"
#include "src/core/image_ops/inpaint_router.h"
#include "src/core/state/session_data.h"

// The TensorRT Engines
#include "src/engine/models/textbpn_engine.h"
#include "src/engine/models/moebius_engine.h"
#include "src/engine/models/lama_engine.h"

#include <QFile>
#include <QFileInfo>
#include <QDir>
#include <QProcess>
#include <future>
#include <vector>

batch_worker::batch_worker(AI_Engine_Pack models, std::shared_ptr<std::mutex> inference_mutex,
    pipeline_manager* pipeline, session_data* session, QObject* parent)
    : QThread(parent), m_cancel_requested(false), m_models(models),
      m_inference_mutex(std::move(inference_mutex)), m_pipeline(pipeline), m_session(session) {
    LOG_TRACE("Batch Worker thread initialized.");
}

batch_worker::~batch_worker() {
    cancel();
    wait();
}

void batch_worker::start_batch(const BatchConfig& config) {
    LOG_INFO("Initializing Wizard Batch Sequence...");
    m_config = config;
    m_cancel_requested = false;
    start();
}

void batch_worker::cancel() {
    if (isRunning()) {
        LOG_WARN("Wizard Batch cancellation requested by user.");
    }
    m_cancel_requested = true;
}

// Decodes a single page. Runs on the prefetch thread so the CPU decode of page N+1
// overlaps with the GPU inference of page N.
cv::Mat batch_worker::decode_image_file(const QString& filepath) {
    QFile file(filepath);
    if (!file.open(QIODevice::ReadOnly)) return cv::Mat();

    const QByteArray file_data = file.readAll();
    file.close();
    if (file_data.isEmpty()) return cv::Mat();

    const std::vector<uchar> buffer(file_data.begin(), file_data.end());
    return cv::imdecode(buffer, cv::IMREAD_UNCHANGED);
}

// Export-only page: pull the CLEANED pixels + mask from the Studio's per-page
// working state (the session's own persistence), falling back to the untouched
// decode for pages never edited. Returns false only when the page cannot be
// processed at all.
bool batch_worker::process_session_state_image(const QString& filepath, const cv::Mat& raw_img, bool* out_skipped)
{
    if (out_skipped) *out_skipped = false;

    cv::Mat working_img;
    cv::Mat persisted_mask; // loaded for state completeness; not exported anymore

    const bool has_state = session_data::load_persisted_page_state(
        filepath, raw_img.size(), working_img, persisted_mask);
    if (!has_state) {
        // Never edited in the Studio: writing a PSD of identical original+
        // cleaned layers would only duplicate the page on disk. Skip it -
        // the caller keeps counting it as processed, but not as failed.
        LOG_INFO(QString("No Studio edits for %1; skipping (untouched page).")
            .arg(QFileInfo(filepath).fileName()));
        if (out_skipped) *out_skipped = true;
        return false;
    }
    if (working_img.empty()) {
        if (raw_img.channels() == 4) cv::cvtColor(raw_img, working_img, cv::COLOR_BGRA2RGB);
        else if (raw_img.channels() == 3) cv::cvtColor(raw_img, working_img, cv::COLOR_BGR2RGB);
        else cv::cvtColor(raw_img, working_img, cv::COLOR_GRAY2RGB);
    }

    // "Original" layer source: the untouched page in RGB order.
    cv::Mat original_rgb;
    if (raw_img.channels() == 4) cv::cvtColor(raw_img, original_rgb, cv::COLOR_BGRA2RGB);
    else if (raw_img.channels() == 3) original_rgb = raw_img.clone();
    else cv::cvtColor(raw_img, original_rgb, cv::COLOR_GRAY2RGB);

    // PSD: layered export (original below, cleaned above). Flat: cleaned pixels
    // in the codec's BGR order.
    QFileInfo fi(filepath);
    const QString base_name = fi.baseName() + "_cleaned";
    if (m_config.export_format.toUpper() == "PSD") {
        const QString out_path = QDir(m_config.output_dir).filePath(base_name + ".psd");
        return psd_exporter::save_layered_psd(out_path, original_rgb, working_img);
    }
    else {
        cv::Mat bgr_out;
        cv::cvtColor(working_img, bgr_out, cv::COLOR_RGB2BGR);
        const QString ext = "." + m_config.export_format.toLower();
        const QString out_path = QDir(m_config.output_dir).filePath(base_name + ext);
        return save_image_unicode(out_path, bgr_out);
    }
}

void batch_worker::run() {
    const int total = m_config.input_files.size();
    int processed = 0;
    int failed = 0;

    LOG_INFO(QString("Starting batch processing of %1 images. Output: %2").arg(total).arg(m_config.output_dir));
    QDir().mkpath(m_config.output_dir);

    std::future<cv::Mat> pending;
    if (total > 0) {
        pending = std::async(std::launch::async, &batch_worker::decode_image_file, m_config.input_files.at(0));
    }

    for (int index = 0; index < total; ++index) {
        if (m_cancel_requested) break;

        const QString filepath = m_config.input_files.at(index);
        const QFileInfo file_info(filepath);
        emit current_task_changed("Processing: " + file_info.fileName());

        cv::Mat raw_img;
        if (pending.valid()) {
            try {
                raw_img = pending.get();
            }
            catch (const std::exception& e) {
                // The prefetch runs outside the main try/catch: without this
                // guard a decode exception would escape run() and terminate.
                LOG_ERROR(QString("Prefetch decode failed for upcoming image: %1").arg(e.what()));
            }
        }

        // Immediately start decoding the next page (CPU/GPU overlap).
        if (index + 1 < total && !m_cancel_requested) {
            pending = std::async(std::launch::async, &batch_worker::decode_image_file,
                m_config.input_files.at(index + 1));
        }
        else {
            pending = std::future<cv::Mat>();
        }

        try {
            bool ok = false;
            bool skipped = false;
            if (raw_img.empty()) {
                LOG_ERROR("Failed to decode image: " + filepath);
            }
            else if (m_config.use_session_state) {
                ok = process_session_state_image(filepath, raw_img, &skipped);
            }
            else {
                ok = process_single_image(filepath, raw_img);
            }

            if (!ok && !skipped) {
                LOG_ERROR("Failed to process image: " + filepath);
                ++failed;
                emit batch_progress_failed(failed);
                if (m_config.halt_on_error) {
                    emit error_occurred("Halted on error at: " + file_info.fileName());
                    emit batch_finished(false);
                    return;
                }
            }
        }
        catch (const std::exception& e) {
            LOG_ERROR(QString("Exception during batch processing of %1: %2").arg(file_info.fileName(), e.what()));
            ++failed;
            emit batch_progress_failed(failed);
            if (m_config.halt_on_error) {
                emit error_occurred(e.what());
                emit batch_finished(false);
                return;
            }
        }

        processed++;
        emit batch_progress(processed, total);
    }

    if (m_cancel_requested) {
        LOG_INFO("Batch sequence interrupted by user.");
        emit current_task_changed("Cancelled by User.");
        emit batch_finished(false);
        return;
    }

    // Post-Processing: Compress chapter to .zip
    if (m_config.create_zip) {
        emit current_task_changed("Packaging to ZIP Archive...");
        QDir out_dir(m_config.output_dir);
        create_zip_archive(m_config.output_dir, out_dir.dirName());
    }

    LOG_INFO("Batch processing sequence completed.");
    emit current_task_changed("Batch Complete.");
    emit batch_finished(true);
}

bool batch_worker::process_single_image(const QString& filepath, const cv::Mat& raw_img) {
    if (raw_img.empty()) return false;

    cv::Mat working_img;
    cv::Mat current_mask = cv::Mat::zeros(cv::Size(raw_img.cols, raw_img.rows), CV_8UC1);

    // 0. Stage 0: Transparency Scanner (Detect transparent pixels where alpha == 0)
    if (m_config.scan_transparency && raw_img.channels() == 4) {
        std::vector<cv::Mat> channels;
        cv::split(raw_img, channels);
        cv::Mat trans_mask;
        cv::compare(channels[3], 0, trans_mask, cv::CMP_EQ); // alpha == 0
        if (cv::countNonZero(trans_mask) > 0) {
            cv::bitwise_or(current_mask, trans_mask, current_mask);
        }
    }

    if (raw_img.channels() == 4) {
        cv::cvtColor(raw_img, working_img, cv::COLOR_BGRA2RGB);
    }
    else if (raw_img.channels() == 3) {
        cv::cvtColor(raw_img, working_img, cv::COLOR_BGR2RGB);
    }
    else {
        cv::cvtColor(raw_img, working_img, cv::COLOR_GRAY2RGB);
    }

    const cv::Mat original_img = working_img.clone();
    std::vector<cv::Point> bubble_centers;

    AppSettings s = config_mgr::instance().get_settings();

    // ==========================================================
    // GPU SECTION: serialized against the interactive Studio worker, because
    // both threads share the same TensorRT contexts and CUDA stream.
    // ==========================================================
    {
        std::unique_lock<std::mutex> gpu_lock;
        if (m_inference_mutex) gpu_lock = std::unique_lock<std::mutex>(*m_inference_mutex);

        // VRAM budgeting: the whole engine pack cannot be resident at once on
        // 8 GB GPUs, so EACH STAGE loads its engine right before it runs -
        // pre-loading both made the inpainting load evict TextBPN++ and the
        // next page's detect() then OOM'd re-initializing it (engine contexts
        // need their full activation memory at context creation time).

        // 1. Stage 1: TextBPN++ Detection
        if (m_config.run_bpn && m_models.bpn) {
            if (m_pipeline && !m_pipeline->ensure_model_loaded(pipeline_manager::EngineBpn)) {
                LOG_ERROR("Batch aborted: TextBPN++ could not be loaded into VRAM.");
                return false;
            }
            float cls_thresh = (s.bpn_prob * 0.01f);
            float dis_thresh = (s.bpn_core * 0.01f);
            TextBpnResult bpn_res = m_models.bpn->detect(working_img, cls_thresh, dis_thresh, 100, s.bpn_expand);
            if (!bpn_res.full_mask.empty()) {
                cv::bitwise_or(current_mask, bpn_res.full_mask, current_mask);
                bubble_centers = bpn_res.bubble_centers;
            }
        }

        // 2. Stage 2: Inpainting (Moebius latent suite or LaMa fast pass)
        if (m_config.run_moebius && cv::countNonZero(current_mask) > 0) {
            if (bubble_centers.empty()) {
                cv::Mat labels, stats, centroids;
                int num_labels = cv::connectedComponentsWithStats(current_mask, labels, stats, centroids, 8, CV_32S);
                for (int i = 1; i < num_labels; ++i) {
                    if (stats.at<int>(i, cv::CC_STAT_AREA) < 10) continue;
                    double cx = centroids.at<double>(i, 0);
                    double cy = centroids.at<double>(i, 1);
                    bubble_centers.push_back(cv::Point(static_cast<int>(cx), static_cast<int>(cy)));
                }
            }

            InpaintEngine engine = inpaint_router::resolve(
                static_cast<InpaintEngine>(s.inpaint_engine), working_img, current_mask);
            if (engine == InpaintEngine::LaMa && !m_models.lama) engine = InpaintEngine::Moebius;
            if (engine == InpaintEngine::Moebius && !m_models.moebius) engine = InpaintEngine::LaMa;

            // Load (and evict others for) the CHOSEN engine only now: the route
            // depends on the final post-detection mask, and TextBPN++ is free to
            // be evicted at this point - detection is already done.
            const pipeline_manager::EngineId wanted_id = (engine == InpaintEngine::LaMa)
                ? pipeline_manager::EngineLama
                : pipeline_manager::EngineMoebius;
            if (m_pipeline && !m_pipeline->ensure_model_loaded(wanted_id)) {
                LOG_ERROR("Batch aborted: inpainting engine could not be loaded into VRAM.");
                return false;
            }

            if (engine == InpaintEngine::LaMa && m_models.lama && m_models.lama->is_loaded()) {
                m_models.lama->inpaint_image(working_img, current_mask, bubble_centers);
            }
            else if (m_models.moebius && m_models.moebius->is_loaded()) {
                m_models.moebius->inpaint_image(working_img, current_mask, bubble_centers, s.moebius_steps);
            }
        }

    }

    // 4. Save Cleaned Output (PSD Layered vs Flat Image)
    QFileInfo fi(filepath);
    QString base_name = fi.baseName() + "_cleaned";

    if (m_config.export_format.toUpper() == "PSD") {
        QString out_path = QDir(m_config.output_dir).filePath(base_name + ".psd");
        return psd_exporter::save_layered_psd(out_path, original_img, working_img);
    }
    else {
        cv::Mat bgr_out;
        cv::cvtColor(working_img, bgr_out, cv::COLOR_RGB2BGR);
        QString ext = "." + m_config.export_format.toLower();
        QString out_path = QDir(m_config.output_dir).filePath(base_name + ext);
        return save_image_unicode(out_path, bgr_out);
    }
}

bool batch_worker::save_image_unicode(const QString& save_path, const cv::Mat& img) {
    std::vector<uchar> out_buf;
    std::string ext = QFileInfo(save_path).suffix().toStdString();

    if (!cv::imencode("." + ext, img, out_buf)) return false;

    QFile outFile(save_path);
    if (!outFile.open(QIODevice::WriteOnly)) return false;

    outFile.write(reinterpret_cast<const char*>(out_buf.data()), static_cast<qint64>(out_buf.size()));
    outFile.close();
    return true;
}

namespace {

// Quotes a value for use inside a PowerShell single-quoted string ('' escapes ').
QString ps_single_quote(const QString& value) {
    QString escaped = value;
    escaped.replace("'", "''");
    return "'" + escaped + "'";
}

} // namespace

void batch_worker::create_zip_archive(const QString& folder_path, const QString& batch_name) {
    QDir dir(folder_path);
    dir.cdUp();
    const QString zip_path = dir.absoluteFilePath(batch_name + ".zip");

    const QString script = QString("Compress-Archive -Path %1 -DestinationPath %2 -Force")
        .arg(ps_single_quote(QDir::toNativeSeparators(folder_path) + "\\*"),
             ps_single_quote(QDir::toNativeSeparators(zip_path)));

    // The script is shipped as UTF-16LE base64, so no shell quoting/injection is possible.
    QByteArray utf16;
    utf16.reserve(script.size() * 2);
    for (const QChar ch : script) {
        const ushort unit = ch.unicode();
        utf16.append(static_cast<char>(unit & 0xFF));
        utf16.append(static_cast<char>((unit >> 8) & 0xFF));
    }

    QStringList arguments;
    arguments << "-NoProfile" << "-NonInteractive"
              << "-EncodedCommand" << QString::fromLatin1(utf16.toBase64());

    QProcess process;
    process.start("powershell.exe", arguments);

    if (!process.waitForStarted(10000)) {
        LOG_ERROR("Failed to launch PowerShell for ZIP archive creation.");
        return;
    }
    if (!process.waitForFinished(600000)) {
        process.kill();
        LOG_ERROR("ZIP archive creation timed out.");
        return;
    }

    if (process.exitCode() == 0) {
        LOG_INFO("Successfully created zip archive: " + zip_path);
    }
    else {
        LOG_ERROR("Failed to create ZIP archive. PowerShell code: " + QString::number(process.exitCode()));
    }
}