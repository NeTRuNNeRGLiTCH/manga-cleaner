#include "task_queue.h"
#include "src/diagnostics/logger.h"

task_queue::task_queue() : m_stop(false), m_cancel(false) {
    LOG_TRACE("Task Queue initialized.");
}

void task_queue::cancel() {
    m_cancel.store(true);

    // Drop every queued task and wake the worker so a sleeping thread returns
    // promptly and observes the flag on its next checkpoint.
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        std::queue<AI_Task> empty;
        std::swap(m_queue, empty);
    }
    m_cond_var.notify_all();
}

void task_queue::rearm() {
    m_cancel.store(false);
}

void task_queue::push_task(const AI_Task& task) {
    // A new request re-arms the queue after a Stop.
    rearm();

    LOG_TRACE(QString("Pushing task to queue: %1").arg(task_type_to_string(task.type)));

    // Lock the queue so we don't collide with the background thread pulling from it
    std::lock_guard<std::mutex> lock(m_mutex);

    m_queue.push(task);

    // Ring the bell! Wake up the background thread to process this task.
    m_cond_var.notify_one();
}

bool task_queue::pop_task(AI_Task& out_task) {
    // Unique lock allows us to safely put the thread to sleep
    std::unique_lock<std::mutex> lock(m_mutex);

    for (;;) {
        // The thread sleeps here. It only wakes up IF:
        // 1. m_stop is true (App is closing) OR
        // 2. The queue is no longer empty
        m_cond_var.wait(lock, [this]() {
            return m_stop.load() || !m_queue.empty();
            });

        // If we woke up because the app is shutting down, gracefully exit the loop
        if (m_stop.load() && m_queue.empty()) {
            return false;
        }

        // Stop button: discard queued tasks but keep the worker thread alive,
        // so the next user action is still served. The in-flight task observes
        // m_cancel at its own checkpoints inside the engines.
        if (m_cancel.load()) {
            std::queue<AI_Task> empty;
            std::swap(m_queue, empty);
            continue; // back to wait(); predicate is false until a new task arrives
        }

        out_task = m_queue.front();
        m_queue.pop();

        // IMPORTANT: do NOT rearm() here. The cancel flag must stay SET while this
        // task runs if a Stop was pressed. Re-arming happens later, in run(), after
        // the task has been processed - re-arming before it ran made the flag false
        // during inference and the Stop button a no-op.

        LOG_TRACE(QString("Popped task from queue: %1").arg(task_type_to_string(out_task.type)));

        return true;
    }
}

void task_queue::stop() {
    LOG_TRACE("Stopping Task Queue and waking up sleeping threads...");

    m_stop.store(true);

    // Wake up all threads so they evaluate the m_stop condition and gracefully exit
    m_cond_var.notify_all();
}

void task_queue::clear() {
    LOG_TRACE("Clearing all pending tasks from the queue.");

    std::lock_guard<std::mutex> lock(m_mutex);

    // The absolute fastest way to clear a std::queue in C++ is to swap it with an empty one
    std::queue<AI_Task> empty;
    std::swap(m_queue, empty);
}

const char* task_queue::task_type_to_string(AI_TaskType type) {
    switch (type) {
    case AI_TaskType::RunOCR:     return "RunOCR";
    case AI_TaskType::RunClean:   return "RunClean";
    default:                      return "Unknown";
    }
}