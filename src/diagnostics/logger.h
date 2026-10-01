#ifndef DIAGNOSTICS_LOGGER_H
#define DIAGNOSTICS_LOGGER_H

#include <QString>
#include <QFile>
#include <QTextStream>
#include <mutex>
#include <queue>
#include <thread>
#include <atomic>
#include <condition_variable>

// Severity Levels
enum class LogLevel {
    TRACE,   // Extreme detail (e.g., "Mouse moved to 400x500")
    INFO,    // Normal app flow (e.g., "TextBPN model loaded successfully")
    WARN,    // Non-fatal issues (e.g., "DirectX 12 not found, falling back to DirectX 11")
    ERR,     // AI failures or IO failures (e.g., "Failed to load image path")
    FATAL    // App-crashing events (e.g., "Out of VRAM")
};

// Internal struct to hold the queued message
struct LogMessage {
    LogLevel level;
    QString timestamp;
    QString message;
    QString filename;
    int line_number;
};

class Logger {
public:
    // Singleton Accessor
    static Logger& instance();

    // Initializes the background thread and log file. Call this ONCE in main.cpp or axis_cleaner.cpp
    void init(const QString& app_root_dir);

    // The actual log function (but you should use the Macros below!)
    void push_log(LogLevel level, const QString& message, const char* file = "", int line = 0);

    // Flushes remaining logs and stops the thread
    void shutdown();

private:
    Logger();
    ~Logger();
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;

    // Background thread function
    void process_queue();

    QString level_to_string(LogLevel level) const;

    // File filter: WARN and above always persist; INFO/TRACE only when the
    // message carries a hardware banner marker (GPU/adapter/CPU detection).
    static bool file_should_write(LogLevel level, const QString& message);

    // --- Threading & IO ---
    std::thread m_worker_thread;
    std::queue<LogMessage> m_queue;
    std::mutex m_mutex;
    std::condition_variable m_cond_var;
    std::atomic<bool> m_running;

    QFile m_log_file;
    QTextStream m_log_stream;
};

// ==========================================================
// AAA MACROS: Use these anywhere in your code!
// They automatically capture the File Name and Line Number.
// ==========================================================
#define LOG_TRACE(msg) Logger::instance().push_log(LogLevel::TRACE, msg, __FILE__, __LINE__)
#define LOG_INFO(msg)  Logger::instance().push_log(LogLevel::INFO, msg)
#define LOG_WARN(msg)  Logger::instance().push_log(LogLevel::WARN, msg, __FILE__, __LINE__)
#define LOG_ERROR(msg) Logger::instance().push_log(LogLevel::ERR, msg, __FILE__, __LINE__)
#define LOG_FATAL(msg) Logger::instance().push_log(LogLevel::FATAL, msg, __FILE__, __LINE__)

#endif // DIAGNOSTICS_LOGGER_H