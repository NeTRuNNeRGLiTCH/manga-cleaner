#include "logger.h"
#include <QDir>
#include <QDateTime>
#include <QFileInfo>
#include <iostream>

Logger& Logger::instance() {
    static Logger _instance;
    return _instance;
}

Logger::Logger() : m_running(false) {
}

Logger::~Logger() {
    shutdown();
}

void Logger::init(const QString& app_root_dir) {
    if (m_running) return;

    QDir dir(app_root_dir);
    if (!dir.exists("logs")) {
        dir.mkdir("logs");
    }

    // Create a new log file for this specific session (e.g., axis_session_20260508_143000.log)
    QString timestamp = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");
    QString log_path = dir.absoluteFilePath("logs/axis_session_" + timestamp + ".log");

    m_log_file.setFileName(log_path);
    if (m_log_file.open(QIODevice::WriteOnly | QIODevice::Append | QIODevice::Text)) {
        m_log_stream.setDevice(&m_log_file);
        m_log_stream.setEncoding(QStringConverter::Utf8);
    }

    m_running = true;
    m_worker_thread = std::thread(&Logger::process_queue, this);

    // Hardware banner (kept at INFO level so debug console mirrors stay intact):
    // the file writer filters INFO out, but these lines must survive it.
    push_log(LogLevel::INFO, "=== AXIS STUDIO v4.0.0 TITANIUM ENGINE STARTED ===", __FILE__, __LINE__);
}

void Logger::push_log(LogLevel level, const QString& message, const char* file, int line) {
    if (!m_running) return;

    LogMessage msg;
    msg.level = level;
    msg.timestamp = QDateTime::currentDateTime().toString("HH:mm:ss.zzz");
    msg.message = message;

    if (file && file[0] != '\0') {
        msg.filename = QFileInfo(QString(file)).fileName();
    }
    msg.line_number = line;

    // Lock, push, and wake the background thread
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_queue.push(msg);
    }
    m_cond_var.notify_one();
}

void Logger::process_queue() {
    while (m_running) {
        std::unique_lock<std::mutex> lock(m_mutex);

        // Thread sleeps here until a log is pushed OR shutdown is called
        m_cond_var.wait(lock, [this]() {
            return !m_queue.empty() || !m_running;
            });

        // Drain the entire queue while awake
        while (!m_queue.empty()) {
            LogMessage msg = m_queue.front();
            m_queue.pop();

            lock.unlock(); // Unlock quickly so the UI can keep pushing logs

            // File filter: only warnings/errors/fatal + the hardware banner are
            // persisted. Everything else stays in memory (still visible on the
            // debug console in Debug builds).
            // i was a bit lazy, you can edit it if you want (and if you know what you are doing)
            const bool write_to_file = file_should_write(msg.level, msg.message);

            // Format the string
            QString formatted_msg = QString("[%1] [%2] ").arg(msg.timestamp, level_to_string(msg.level));

            if (msg.level == LogLevel::TRACE || msg.level >= LogLevel::WARN) {
                // Add the exact C++ file and Line number for debugging errors
                formatted_msg += QString("{%1:%2} ").arg(msg.filename).arg(msg.line_number);
            }

            formatted_msg += msg.message;

            // 1. Write to Log File. Flushing every line costs an OS call per log
            // message; batch the writes and let the OS buffer handle persistence.
            if (write_to_file && m_log_file.isOpen()) {
                m_log_stream << formatted_msg << "\n";
#ifdef _DEBUG
                m_log_stream.flush(); // Debug builds: keep crash-proof logging.
#endif
            }

#ifdef _DEBUG
            // 2. Debug builds mirror to the console / VS Output window. Release builds
            //    skip this: it is pure overhead for a Windows GUI-subsystem binary.
            std::cout << formatted_msg.toStdString() << std::endl;
#endif

            lock.lock(); // Re-lock to check the next item
        }
    }
}

QString Logger::level_to_string(LogLevel level) const {
    switch (level) {
    case LogLevel::TRACE: return "TRACE";
    case LogLevel::INFO:  return "INFO ";
    case LogLevel::WARN:  return "WARN ";
    case LogLevel::ERR:   return "ERROR";
    case LogLevel::FATAL: return "FATAL";
    default: return "UNKNOWN";
    }
}

void Logger::shutdown() {
    if (!m_running) return;

    LOG_INFO("=== AXIS STUDIO SHUTTING DOWN ===");

    m_running = false;
    m_cond_var.notify_all();

    if (m_worker_thread.joinable()) {
        m_worker_thread.join();
    }

    if (m_log_file.isOpen()) {
        m_log_file.close();
    }
}

// === FILE FILTER ==========================================================
// The file keeps WARN and above plus the hardware banner; INFO/TRACE never
// reach the disk (no log growth, no noise). The banner is marked "forced" via
// these substrings so GPU/adapter lines always survive the filter.
namespace {
constexpr const char* k_hardware_markers[] = {
    "Registered Host CPU:",
    "Detected GPU [",
    "Selected Compute Device:",
    "GPU Detected:",
    "Hardware Router selected architecture",
};
} // namespace

bool Logger::file_should_write(LogLevel level, const QString& message)
{
    if (message.contains("AXIS STUDIO v4.0.0 TITANIUM ENGINE STARTED")) return true;

    for (const char* marker : k_hardware_markers) {
        if (message.contains(QString::fromLatin1(marker))) return true;
    }
    return level >= LogLevel::WARN;
}