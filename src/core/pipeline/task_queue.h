#ifndef CORE_PIPELINE_TASK_QUEUE_H
#define CORE_PIPELINE_TASK_QUEUE_H

#include <queue>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include "ai_types.h"

// ==========================================================
// Cooperative cancellation hook.
// pipeline_manager points this at its atomic cancel flag; the TensorRT engines
// poll task_cancel_requested() at safe checkpoints (bubble / tile boundaries)
// so a running job aborts within milliseconds of the user pressing Stop.
// ==========================================================
inline std::atomic<bool>* g_task_cancel_flag = nullptr;
inline bool task_cancel_requested() {
    return g_task_cancel_flag && g_task_cancel_flag->load(std::memory_order_relaxed);
}

// Defines what the AI Worker should do
enum class AI_TaskType {
    RunOCR,      // TextBPN++ -> text / SFX detection
    RunClean,    // Inpainting (Moebius latent suite or LaMa fast pass)
};

// A simple package holding the instructions for the background thread
struct AI_Task {
    AI_TaskType type = AI_TaskType::RunOCR;
    InpaintEngine inpaint_engine = InpaintEngine::Auto; // Only meaningful for RunClean
};

class task_queue {
public:
    task_queue();
    ~task_queue() = default;

    // Wakes the worker and makes it drop queued tasks; the in-flight task is
    // cancelled cooperatively by the engines (see pipeline_manager::request_cancel).
    void cancel();

    // Clears the cancellation flag before a fresh task is queued.
    void rearm();

    // True between a Stop request and the next queued task.
    bool is_cancelled() const { return m_cancel.load(std::memory_order_relaxed); }

    // Push a new job into the queue from the UI thread
    void push_task(const AI_Task& task);

    // The background worker calls this to get the next job.
    // If the queue is empty, the thread goes to sleep (zero CPU usage).
    bool pop_task(AI_Task& out_task);

    // Wakes up any sleeping threads and tells them to shut down
    void stop();

    // Safely empties all pending tasks
    void clear();

private:
    std::queue<AI_Task> m_queue;
    std::mutex m_mutex;
    std::condition_variable m_cond_var;
    std::atomic<bool> m_stop;
    std::atomic<bool> m_cancel;

    // Helper for clean logging
    const char* task_type_to_string(AI_TaskType type);
};

#endif // CORE_PIPELINE_TASK_QUEUE_H