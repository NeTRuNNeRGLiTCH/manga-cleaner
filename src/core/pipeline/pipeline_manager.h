#ifndef CORE_PIPELINE_MANAGER_H
#define CORE_PIPELINE_MANAGER_H

#include <QObject>
#include <atomic>
#include <memory>
#include <mutex>
#include "task_queue.h"
#include "studio_worker.h"
#include "batch_worker.h"

class session_data;
class history_stack;
class QTimer;

class pipeline_manager : public QObject {
    Q_OBJECT

public:
    explicit pipeline_manager(session_data* session, history_stack* history, QObject* parent = nullptr);
    ~pipeline_manager() override;

    // Which engine a stage wants resident in VRAM.
    enum EngineId {
        EngineBpn,
        EngineMoebius,
        EngineLama
    };

    // === STUDIO API (Interactive Single Image) ===
    void request_studio_task(AI_TaskType task_type);

    // === WIZARD API (Batch Chapter Automation) ===
    void start_batch_job(const BatchConfig& config);
    void cancel_batch_job();

    // === CANCELLATION (Stop button) ===
    // Cooperative cancellation: the current stage finishes at the next safe
    // checkpoint (bubble / tile boundary), pending tasks are dropped and no
    // result is committed to the canvas. The next queued task rearms it.
    void request_cancel();
    bool is_cancelled() const;

    // === VRAM BUDGETING (called from the worker threads before each stage) ===
    // Engines are lazy: they only occupy VRAM while a stage actually needs them.
    // TextBPN++ alone needs ~5.3 GB of activation memory, so loading the whole
    // pack eagerly OOMs on 8 GB cards, poisons the CUDA allocator and makes every
    // later enqueueV3 fail. This loads (and evicts others to make room) exactly
    // the engine a stage asks for.
    bool ensure_model_loaded(EngineId id);

    // === STATUS QUERY ===
    QString get_loaded_models_status() const;

signals:
    // Unified UI Status Signals
    void loaded_models_changed(const QString& models_status);
    void global_progress_updated(int percentage);
    void global_status_changed(const QString& status_message);
    void global_error_occurred(const QString& error_message);

    void studio_task_finished(bool success);
    void batch_job_finished(bool success);
    void batch_progress_stepped(int processed, int total);
    void batch_progress_failed(int failed);
    void new_transcript_available(const QString& text);

private:
    task_queue* m_queue;
    studio_worker* m_studio_worker;
    batch_worker* m_batch_worker;

    // Owns the TensorRT models in VRAM
    AI_Engine_Pack m_models;

    // Serializes GPU work between the interactive and the batch worker.
    std::shared_ptr<std::mutex> m_inference_mutex;
    QTimer* m_idle_unload_timer = nullptr;
    std::atomic<bool> m_cancel_requested{ false };

    void create_engines();
    void setup_signal_routing();

    // Frees VRAM by unloading resident engines (never `keep_ready`) until
    // `approx_needed` bytes are available.
    bool ensure_vram(size_t approx_needed, EngineId keep_ready);

    // Honors the Model Persistence settings after every finished job.
    void unload_after_work();
    void unload_idle_models();
};

#endif // CORE_PIPELINE_MANAGER_H