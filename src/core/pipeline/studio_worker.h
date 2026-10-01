#ifndef CORE_PIPELINE_STUDIO_WORKER_H
#define CORE_PIPELINE_STUDIO_WORKER_H

#include <QThread>
#include <QString>
#include <memory>
#include <mutex>
#include "task_queue.h"
#include "src/core/state/session_data.h"
#include "src/core/state/history_stack.h"

// Forward declarations for the TensorRT Engine handlers
class textbpn_engine;
class moebius_engine;
class lama_engine;
class pipeline_manager;

// Unified AI Engine Pack containing pointers to the loaded TensorRT models
struct AI_Engine_Pack {
    textbpn_engine* bpn = nullptr;
    moebius_engine* moebius = nullptr;
    lama_engine* lama = nullptr;   // Fast single-pass inpainting alternative
};

class studio_worker : public QThread {
    Q_OBJECT

public:
    // inference_mutex is shared with the batch worker so the two threads can never
    // drive the same TensorRT contexts / CUDA stream at the same time.
    // m_pipeline (not owned) lazy-loads engines into VRAM right before each stage,
    // because the whole pack cannot be resident at once on 8 GB GPUs.
    studio_worker(task_queue* queue, session_data* session, history_stack* history, AI_Engine_Pack models,
        std::shared_ptr<std::mutex> inference_mutex, pipeline_manager* pipeline, QObject* parent = nullptr);
    ~studio_worker() override;

signals:
    void task_started(const QString& task_name);
    void progress_updated(int percentage);
    void task_finished(bool success);
    void error_occurred(const QString& message);
    void transcript_extracted(const QString& text);

protected:
    void run() override;

private:
    task_queue* m_queue;
    session_data* m_session;
    history_stack* m_history;
    AI_Engine_Pack m_models;
    std::shared_ptr<std::mutex> m_inference_mutex;
    pipeline_manager* m_pipeline;

    void process_ocr(const AI_Task& task);
    void process_clean(const AI_Task& task);

    // Resolves Auto/LaMa/Moebius to an engine id and lazy-loads it into VRAM.
    bool ensure_inpaint_engine_loaded(InpaintEngine engine);
};

#endif // CORE_PIPELINE_STUDIO_WORKER_H