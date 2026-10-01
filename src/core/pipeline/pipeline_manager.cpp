#include "pipeline_manager.h"
#include "src/diagnostics/logger.h"
#include "src/storage/config_mgr.h"
#include <QTimer>
#include <cuda_runtime.h>
#include <algorithm>

// The Unified TensorRT Engine Handlers
#include "src/engine/models/textbpn_engine.h"
#include "src/engine/models/moebius_engine.h"
#include "src/engine/models/lama_engine.h"

namespace {

// Conservative per-engine VRAM needs (activation memory + IO buffers + headroom),
// used to decide *before* a cudaMalloc storm whether other engines must be evicted.
// Measured on the real packs: TextBPN++ reports 5312 MB activation; the Moebius
// suite needs ~2.1 GB; LaMa's activation memory alone is 1341 MB, so 300 MB was
// fiction - it made ensure_vram skip eviction and the load then died in cudaMalloc.
constexpr size_t MB = 1024ull * 1024ull;
constexpr size_t EST_VRAM_BPN     = 5600 * MB;
constexpr size_t EST_VRAM_MOEBIUS = 2400 * MB;
constexpr size_t EST_VRAM_LAMA    = 1700 * MB;

bool engine_is_loaded(const AI_Engine_Pack& pack, pipeline_manager::EngineId id) {
    switch (id) {
    case pipeline_manager::EngineBpn:     return pack.bpn && pack.bpn->is_loaded();
    case pipeline_manager::EngineMoebius: return pack.moebius && pack.moebius->is_loaded();
    case pipeline_manager::EngineLama:    return pack.lama && pack.lama->is_loaded();
    }
    return false;
}

void unload_engine(const AI_Engine_Pack& pack, pipeline_manager::EngineId id) {
    switch (id) {
    case pipeline_manager::EngineBpn:     if (pack.bpn) pack.bpn->unload(); break;
    case pipeline_manager::EngineMoebius: if (pack.moebius) pack.moebius->unload(); break;
    case pipeline_manager::EngineLama:    if (pack.lama) pack.lama->unload(); break;
    }
}

int persistence_setting(pipeline_manager::EngineId id, const AppSettings& s) {
    switch (id) {
    case pipeline_manager::EngineBpn:     return s.persist_bpn;
    case pipeline_manager::EngineMoebius: return s.persist_moebius;
    case pipeline_manager::EngineLama:    return s.persist_lama;
    }
    return 0;
}

QString engine_display_name(pipeline_manager::EngineId id) {
    switch (id) {
    case pipeline_manager::EngineBpn:     return "TextBPN++";
    case pipeline_manager::EngineMoebius: return "Moebius";
    case pipeline_manager::EngineLama:    return "LaMa";
    }
    return "Engine";
}

size_t query_free_vram() {
    size_t free_bytes = 0, total_bytes = 0;
    if (cudaMemGetInfo(&free_bytes, &total_bytes) != cudaSuccess) {
        return 0;
    }
    return free_bytes;
}

} // namespace

pipeline_manager::pipeline_manager(session_data* session, history_stack* history, QObject* parent)
    : QObject(parent) {

    LOG_TRACE("Booting Pipeline Manager facade...");

    // Single GPU token shared by both workers: the engines, their execution contexts
    // and the CUDA stream are not safe to use from two threads at once.
    m_inference_mutex = std::make_shared<std::mutex>();

    // Engines poll this flag at their bubble/tile checkpoints (Stop button).
    g_task_cancel_flag = &m_cancel_requested;

    m_queue = new task_queue();
    create_engines();

    m_studio_worker = new studio_worker(m_queue, session, history, m_models, m_inference_mutex, this, this);
    m_studio_worker->start();

    m_batch_worker = new batch_worker(m_models, m_inference_mutex, this, session, this);

    // "Dynamic (Unload after 60s)" persistence mode.
    m_idle_unload_timer = new QTimer(this);
    m_idle_unload_timer->setSingleShot(true);
    m_idle_unload_timer->setInterval(60000);
    connect(m_idle_unload_timer, &QTimer::timeout, this, &pipeline_manager::unload_idle_models);

    setup_signal_routing();
    LOG_INFO("Pipeline Manager ready. AI engines load lazily per stage to fit the VRAM budget.");
}

pipeline_manager::~pipeline_manager() {
    LOG_TRACE("Shutting down Pipeline Manager...");

    m_queue->stop();
    m_studio_worker->quit();
    m_studio_worker->wait();

    if (m_batch_worker->isRunning()) {
        m_batch_worker->cancel();
        m_batch_worker->wait();
    }

    if (m_models.bpn) {
        delete m_models.bpn;
        m_models.bpn = nullptr;
    }
    if (m_models.moebius) {
        delete m_models.moebius;
        m_models.moebius = nullptr;
    }
    if (m_models.lama) {
        delete m_models.lama;
        m_models.lama = nullptr;
    }

    delete m_queue;
    LOG_TRACE("Pipeline Manager safely destroyed.");
}

void pipeline_manager::create_engines() {
    // Only construct the C++ objects. Deserialization + VRAM allocation happens in
    // ensure_model_loaded(), right before a stage actually runs. Loading all
    // engines at startup OOMs 8 GB cards (TextBPN++ alone wants ~5.3 GB).
    LOG_INFO("Creating TensorRT engine handlers (lazy VRAM residency)...");

    m_models.bpn = new textbpn_engine();
    m_models.moebius = new moebius_engine();
    m_models.lama = new lama_engine();
}

bool pipeline_manager::ensure_vram(size_t approx_needed, EngineId keep_ready) {
    // Caller must already hold m_inference_mutex.
    size_t free_bytes = query_free_vram();
    if (free_bytes == 0) return true; // Cannot query: let init() surface the real error.
    if (free_bytes >= approx_needed + 256 * MB) return true;

    LOG_WARN(QString("VRAM budget exceeded: %1 MB free, stage needs ~%2 MB. Evicting engines...")
        .arg(free_bytes / MB)
        .arg(approx_needed / MB));

    const AppSettings s = config_mgr::instance().get_settings();
    auto try_evict = [&](EngineId candidate) {
        if (candidate == keep_ready) return false;
        if (!engine_is_loaded(m_models, candidate)) return false;
        LOG_INFO(QString("Evicting %1 from VRAM to make room.").arg(engine_display_name(candidate)));
        unload_engine(m_models, candidate);
        emit loaded_models_changed(get_loaded_models_status());
        return true;
    };

    // Pass 1: evict engines whose persistence policy allows it. Value semantics
    // match the UI labels: 1 = Unload Immediately, 2 = Dynamic (also evictable),
    // and ONLY 0 = Keep Loaded (pinned) is spared here.
    for (int i = 0; i < static_cast<int>(EngineId::EngineLama) + 1; ++i) {
        const EngineId candidate = static_cast<EngineId>(i);
        if (candidate == keep_ready) continue;
        if (persistence_setting(candidate, s) == 0) continue;
        try_evict(candidate);

        free_bytes = query_free_vram();
        if (free_bytes >= approx_needed + 256 * MB) return true;
    }

    // Pass 2: still short - override even the pinned engines. A pinned engine that
    // stays resident while the next one OOMs helps nobody.
    LOG_WARN("Still short on VRAM after policy eviction: overriding pinned engines.");
    for (int i = 0; i < static_cast<int>(EngineId::EngineLama) + 1; ++i) {
        try_evict(static_cast<EngineId>(i));

        free_bytes = query_free_vram();
        if (free_bytes >= approx_needed + 256 * MB) return true;
    }

    LOG_ERROR(QString("VRAM still tight after evicting everything: %1 MB free, need ~%2 MB.")
        .arg(query_free_vram() / MB).arg(approx_needed / MB));
    return false;
}

bool pipeline_manager::ensure_model_loaded(EngineId id) {
    // Caller must already hold m_inference_mutex.

    auto load = [&](auto* engine, size_t est_bytes) -> bool {
        if (!engine) return false;
        if (engine->is_loaded()) return true;

        // Cold start: deserializing a 5 GB engine takes seconds. Tell the user
        // instead of showing a frozen progress bar.
        const QString name = engine_display_name(id);
        emit global_status_changed(QString("Loading %1 into VRAM (cold start)... Please wait.").arg(name));
        emit global_progress_updated(5);

        ensure_vram(est_bytes, id); // best effort: unloads others, never aborts here
        if (!engine->init()) {
            LOG_ERROR(QString("Failed to load %1 into VRAM.").arg(name));
            emit global_status_changed(QString("Failed to load %1 into VRAM.").arg(name));
            return false;
        }

        LOG_INFO(QString("%1 loaded into VRAM (%2 MB free).")
            .arg(name)
            .arg(query_free_vram() / MB));
        emit global_status_changed(QString("%1 ready.").arg(name));
        emit global_progress_updated(15);
        emit loaded_models_changed(get_loaded_models_status());
        return true;
    };

    switch (id) {
    case EngineBpn:     return load(m_models.bpn, EST_VRAM_BPN);
    case EngineMoebius: return load(m_models.moebius, EST_VRAM_MOEBIUS);
    case EngineLama:    return load(m_models.lama, EST_VRAM_LAMA);
    }
    return false;
}

void pipeline_manager::setup_signal_routing() {
    // Studio Worker -> Pipeline Manager Signals
    connect(m_studio_worker, &studio_worker::task_started, this, &pipeline_manager::global_status_changed);
    connect(m_studio_worker, &studio_worker::progress_updated, this, &pipeline_manager::global_progress_updated);
    connect(m_studio_worker, &studio_worker::error_occurred, this, &pipeline_manager::global_error_occurred);
    connect(m_studio_worker, &studio_worker::task_finished, this, &pipeline_manager::studio_task_finished);
    connect(m_studio_worker, &studio_worker::transcript_extracted, this, &pipeline_manager::new_transcript_available);

    // Batch Worker -> Pipeline Manager Signals
    connect(m_batch_worker, &batch_worker::current_task_changed, this, &pipeline_manager::global_status_changed);
    connect(m_batch_worker, &batch_worker::batch_progress, this, &pipeline_manager::batch_progress_stepped);
    connect(m_batch_worker, &batch_worker::batch_progress_failed, this, &pipeline_manager::batch_progress_failed);
    connect(m_batch_worker, &batch_worker::error_occurred, this, &pipeline_manager::global_error_occurred);
    connect(m_batch_worker, &batch_worker::batch_finished, this, &pipeline_manager::batch_job_finished);

    // === MODEL LIFECYCLE + BOTTOM-BAR BADGE ===
    // Engines are loaded/unloaded on the worker threads, so re-evaluate residency
    // (and apply the Model Persistence policy) whenever an operation completes.
    connect(m_studio_worker, &studio_worker::task_finished, this, [this](bool) {
        unload_after_work();
    });
    connect(m_batch_worker, &batch_worker::batch_finished, this, [this](bool) {
        unload_after_work();
    });
}

void pipeline_manager::unload_after_work() {
    const AppSettings s = config_mgr::instance().get_settings();
    bool needs_idle_timer = false;

    {
        std::lock_guard<std::mutex> gpu_lock(*m_inference_mutex);

        // "Unload Immediately" (1): release VRAM as soon as the job is done. The
        // engines lazy-init again on the next request. "Keep Loaded" (0) stays.
        if (s.persist_bpn == 1 && m_models.bpn) m_models.bpn->unload();
        if (s.persist_moebius == 1 && m_models.moebius) m_models.moebius->unload();
        if (s.persist_lama == 1 && m_models.lama) m_models.lama->unload();

        // "Dynamic" (2): arm the idle timer when something is still resident.
        needs_idle_timer =
            (s.persist_bpn == 2 && m_models.bpn && m_models.bpn->is_loaded()) ||
            (s.persist_moebius == 2 && m_models.moebius && m_models.moebius->is_loaded()) ||
            (s.persist_lama == 2 && m_models.lama && m_models.lama->is_loaded());
    }

    if (m_idle_unload_timer) {
        if (needs_idle_timer) m_idle_unload_timer->start();
        else m_idle_unload_timer->stop();
    }

    emit loaded_models_changed(get_loaded_models_status());
}

void pipeline_manager::unload_idle_models() {
    const AppSettings s = config_mgr::instance().get_settings();

    {
        std::lock_guard<std::mutex> gpu_lock(*m_inference_mutex);

        if (s.persist_bpn == 2 && m_models.bpn) m_models.bpn->unload();
        if (s.persist_moebius == 2 && m_models.moebius) m_models.moebius->unload();
        if (s.persist_lama == 2 && m_models.lama) m_models.lama->unload();
    }

    LOG_INFO("Idle timeout reached: dynamically loaded engines unloaded from VRAM.");
    emit loaded_models_changed(get_loaded_models_status());
}

void pipeline_manager::request_studio_task(AI_TaskType task_type) {
    // A fresh user request re-arms the pipeline: a Stop pressed earlier must not
    // abort it at the first engine checkpoint. (The flag stays raised for the
    // whole duration of the task it cancelled - that is what makes Stop work.)
    m_cancel_requested.store(false);

    AI_Task task;
    task.type = task_type;

    if (task_type == AI_TaskType::RunClean) {
        const int mode = config_mgr::instance().get_settings().inpaint_engine;
        task.inpaint_engine = static_cast<InpaintEngine>(std::clamp(mode, 0, 2));
    }

    m_queue->push_task(task);
}

void pipeline_manager::start_batch_job(const BatchConfig& config) {
    m_cancel_requested.store(false); // fresh batch: re-arm (see request_studio_task)

    if (m_batch_worker->isRunning()) {
        LOG_WARN("Attempted to start batch job while one is already active.");
        emit global_error_occurred("A batch operation is already in progress.");
        return;
    }
    m_batch_worker->start_batch(config);
}

void pipeline_manager::cancel_batch_job() {
    if (m_batch_worker->isRunning()) {
        m_batch_worker->cancel();
        emit global_status_changed("Cancelling batch operation...");
    }
}

void pipeline_manager::request_cancel() {
    if (m_cancel_requested.exchange(true)) return; // already stopping

    LOG_WARN("Stop requested: dropping queued tasks and aborting the running stage.");
    m_queue->cancel();
    m_batch_worker->cancel();
    emit global_status_changed("Stopping current task...");
}

bool pipeline_manager::is_cancelled() const {
    return m_cancel_requested.load();
}

QString pipeline_manager::get_loaded_models_status() const {
    // A model is tagged [VRAM] once its TensorRT execution context is resident on the GPU;
    // otherwise it is reported as [RAM] (present on disk / host, not resident yet).
    QStringList parts;

    auto append_status = [&parts](const QString& name, const auto* engine) {
        const bool resident = (engine != nullptr) && engine->is_loaded();
        parts << QString("%1 [%2]").arg(name, resident ? "VRAM" : "RAM");
    };

    append_status("TextBPN++", m_models.bpn);
    append_status("Moebius", m_models.moebius);
    append_status("LaMa", m_models.lama);

    return "Models: " + parts.join(", ");
}