#include "workspace.h"
#include "src/diagnostics/logger.h"

#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStandardPaths>

workspace& workspace::instance() {
    static workspace _instance;
    return _instance;
}

workspace::~workspace() {
    clear_temp_dir();
}

void workspace::init(const QString& app_root_dir) {
    m_app_root = app_root_dir;

    QDir root(m_app_root);

    if (!root.exists("cache")) root.mkdir("cache");
    if (!root.exists("logs")) root.mkdir("logs");

    m_cache_dir = root.absoluteFilePath("cache");
    m_batch_tracker_file = QDir(m_cache_dir).absoluteFilePath("batch_id.json");

    // Standard OS Temp location: AppData/Local/Temp/AxisStudio
    m_temp_dir = QDir::cleanPath(QStandardPaths::writableLocation(QStandardPaths::TempLocation) + "/AxisStudio");
    QDir(m_temp_dir).mkpath(".");

    LOG_INFO("Workspace directories verified: " + m_temp_dir);
}

QString workspace::get_temp_dir() const {
    return m_temp_dir;
}

void workspace::clear_temp_dir() {
    if (m_temp_dir.isEmpty()) return;

    QDir dir(m_temp_dir);
    if (dir.exists()) {
        dir.removeRecursively();
        dir.mkpath(".");
        LOG_TRACE("Temporary workspace cache wiped.");
    }
}

QString workspace::get_next_batch_name() {
    std::lock_guard<std::mutex> lock(m_mutex);

    int current_id = 1;

    // Read the last batch ID from cache
    QFile file(m_batch_tracker_file);
    if (file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        QJsonDocument doc = QJsonDocument::fromJson(file.readAll());
        file.close();
        if (!doc.isNull() && doc.isObject()) {
            current_id = doc.object()["last_id"].toInt(0) + 1;
        }
    }

    if (current_id > 99999) current_id = 1;

    // Save incremented ID
    QJsonObject root;
    root["last_id"] = current_id;
    if (file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        file.write(QJsonDocument(root).toJson());
        file.close();
    }

    return QString("batch_%1").arg(current_id, 5, 10, QChar('0'));
}

QString workspace::prepare_batch_directory(const QString& export_root) {
    QDir base_dir(export_root);
    if (!base_dir.exists()) {
        base_dir.mkpath(".");
    }

    QString batch_name = get_next_batch_name();
    base_dir.mkdir(batch_name);

    QString final_path = base_dir.absoluteFilePath(batch_name);
    LOG_INFO("Created batch destination folder: " + final_path);
    return final_path;
}