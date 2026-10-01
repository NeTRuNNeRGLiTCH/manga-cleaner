#ifndef STORAGE_WORKSPACE_H
#define STORAGE_WORKSPACE_H

#include <QString>
#include <mutex>

class workspace {
public:
    static workspace& instance();

    void init(const QString& app_root_dir);

    // === BATCH DIRECTORY MANAGEMENT ===
    QString get_next_batch_name();
    QString prepare_batch_directory(const QString& export_root);

    // === TEMPORARY SCRATCHPAD CACHE ===
    QString get_temp_dir() const;
    void clear_temp_dir();

private:
    workspace() = default;
    ~workspace(); // Auto-wipes temp folder on app exit
    workspace(const workspace&) = delete;
    workspace& operator=(const workspace&) = delete;

    std::mutex m_mutex;
    QString m_app_root;
    QString m_cache_dir;
    QString m_temp_dir;
    QString m_batch_tracker_file;
};

#endif // STORAGE_WORKSPACE_H