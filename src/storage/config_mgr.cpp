#include "config_mgr.h"
#include "src/diagnostics/logger.h"
#include <QFile>
#include <QJsonDocument>
#include <QStandardPaths>
#include <QDir>
#include <QTimer>

config_mgr& config_mgr::instance() {
    static config_mgr _instance;
    return _instance;
}

void config_mgr::init(const QString& app_root_dir) {
    m_config_path = QDir(app_root_dir).filePath("settings.json");

    QString docs = QStandardPaths::writableLocation(QStandardPaths::DocumentsLocation);
    m_current_settings.import_path = docs + "/AxisStudio/Imports";
    m_current_settings.export_path = docs + "/AxisStudio/Exports";
    m_current_settings.wiz_batch_export_path = docs + "/AxisStudio/Batches";

    load_from_disk();
}

AppSettings config_mgr::get_settings() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_current_settings;
}

void config_mgr::update_settings(const AppSettings& new_settings) {
    bool write_now = false;
    bool schedule = false;

    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_current_settings = new_settings;
        m_dirty = true;

        // Debounce: the settings UI calls this on every slider tick / keystroke, so only
        // touch the disk once the user has been idle for a moment.
        write_now = (std::chrono::steady_clock::now() - m_last_save) >= std::chrono::milliseconds(750);
        schedule = !write_now && !m_flush_scheduled;
        if (schedule) m_flush_scheduled = true;
    }

    if (write_now) {
        save();
        return;
    }

    if (schedule) {
        // Guarantees the last edit lands on disk shortly after the user stops
        // interacting, instead of waiting for the next edit or app shutdown.
        QTimer::singleShot(750, []() { config_mgr::instance().flush(); });
    }
}

void config_mgr::flush() {
    bool dirty = false;
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        dirty = m_dirty;
        m_flush_scheduled = false;
    }

    if (dirty) {
        save();
    }
}

void config_mgr::load_from_disk() {
    QFile file(m_config_path);
    if (!file.exists()) {
        LOG_INFO("settings.json not found. Generating default configuration.");
        save();
        return;
    }

    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        LOG_ERROR("Failed to open settings.json for reading.");
        return;
    }

    QByteArray data = file.readAll();
    file.close();

    QJsonParseError parse_error;
    QJsonDocument doc = QJsonDocument::fromJson(data, &parse_error);

    if (parse_error.error != QJsonParseError::NoError) {
        // Corrupt settings must not be lost: the previous write is kept as a
        // .bak sibling, so restore it instead of silently falling back to
        // defaults (the very next save() would then overwrite the file).
        LOG_ERROR(QString("Failed to parse settings.json (%1). Trying backup...")
            .arg(parse_error.errorString()));

        QFile backup(m_config_path + ".bak");
        if (backup.open(QIODevice::ReadOnly | QIODevice::Text)) {
            QJsonParseError bak_error;
            QJsonDocument bak_doc = QJsonDocument::fromJson(backup.readAll(), &bak_error);
            backup.close();

            if (bak_error.error == QJsonParseError::NoError) {
                apply_json(bak_doc.object());
                save(); // re-write the healthy settings over the corrupt file
                LOG_INFO("Settings restored from settings.json.bak.");
                return;
            }
        }
        LOG_ERROR("Settings backup missing or corrupt too. Using memory defaults.");
        return;
    }

    apply_json(doc.object());

    // Healthy load: snapshot the good file so a FUTURE corruption can be
    // restored from it (only written when the content actually changed).
    QFile backup(m_config_path + ".bak");
    if (!backup.exists() || backup.readAll() != data) {
        if (backup.open(QIODevice::WriteOnly | QIODevice::Text)) {
            backup.write(data);
            backup.close();
        }
    }
}

void config_mgr::apply_json(const QJsonObject& root)
{

    if (root.contains("system")) {
        QJsonObject sys = root["system"].toObject();
        if (sys.contains("persist_bpn")) m_current_settings.persist_bpn = sys["persist_bpn"].toInt();
        if (sys.contains("persist_moebius")) m_current_settings.persist_moebius = sys["persist_moebius"].toInt();
        if (sys.contains("persist_lama")) m_current_settings.persist_lama = sys["persist_lama"].toInt();
        if (sys.contains("arch_dispatch_mode")) m_current_settings.arch_dispatch_mode = sys["arch_dispatch_mode"].toInt();
    }

    if (root.contains("models")) {
        QJsonObject mod = root["models"].toObject();
        if (mod.contains("bpn_prob")) m_current_settings.bpn_prob = mod["bpn_prob"].toInt();
        if (mod.contains("bpn_core")) m_current_settings.bpn_core = mod["bpn_core"].toInt();
        if (mod.contains("bpn_expand")) m_current_settings.bpn_expand = mod["bpn_expand"].toInt();
        if (mod.contains("moebius_steps")) m_current_settings.moebius_steps = mod["moebius_steps"].toInt();
        if (mod.contains("inpaint_engine")) m_current_settings.inpaint_engine = mod["inpaint_engine"].toInt();
    }

    if (root.contains("image")) {
        QJsonObject img = root["image"].toObject();
        if (img.contains("export_format_idx")) m_current_settings.export_format_idx = img["export_format_idx"].toInt();
        if (img.contains("jpg_quality")) m_current_settings.jpg_quality = img["jpg_quality"].toInt();
        if (img.contains("max_res_idx")) m_current_settings.max_res_idx = img["max_res_idx"].toInt();
        if (img.contains("color_space_idx")) m_current_settings.color_space_idx = img["color_space_idx"].toInt();
        if (img.contains("import_path")) m_current_settings.import_path = img["import_path"].toString();
        if (img.contains("export_path")) m_current_settings.export_path = img["export_path"].toString();
        if (img.contains("save_in_src")) m_current_settings.save_in_src = img["save_in_src"].toBool();
    }

    if (root.contains("wizard")) {
        QJsonObject wiz = root["wizard"].toObject();
        if (wiz.contains("wiz_run_bpn")) m_current_settings.wiz_run_bpn = wiz["wiz_run_bpn"].toBool();
        if (wiz.contains("wiz_run_moebius")) m_current_settings.wiz_run_moebius = wiz["wiz_run_moebius"].toBool();
        if (wiz.contains("wiz_batch_export_path")) m_current_settings.wiz_batch_export_path = wiz["wiz_batch_export_path"].toString();
        if (wiz.contains("wiz_batch_format_idx")) m_current_settings.wiz_batch_format_idx = wiz["wiz_batch_format_idx"].toInt();
        if (wiz.contains("wiz_error_handling_idx")) m_current_settings.wiz_error_handling_idx = wiz["wiz_error_handling_idx"].toInt();
        if (wiz.contains("wiz_create_zip")) m_current_settings.wiz_create_zip = wiz["wiz_create_zip"].toBool();
    }

    LOG_INFO("Successfully loaded user settings from JSON.");
}

void config_mgr::save() {
    std::lock_guard<std::mutex> lock(m_mutex);

    QJsonObject root;

    QJsonObject sys;
    sys["persist_bpn"] = m_current_settings.persist_bpn;
    sys["persist_moebius"] = m_current_settings.persist_moebius;
    sys["persist_lama"] = m_current_settings.persist_lama;
    sys["arch_dispatch_mode"] = m_current_settings.arch_dispatch_mode;
    root["system"] = sys;

    QJsonObject mod;
    mod["bpn_prob"] = m_current_settings.bpn_prob;
    mod["bpn_core"] = m_current_settings.bpn_core;
    mod["bpn_expand"] = m_current_settings.bpn_expand;
    mod["moebius_steps"] = m_current_settings.moebius_steps;
    mod["inpaint_engine"] = m_current_settings.inpaint_engine;
    root["models"] = mod;

    QJsonObject img;
    img["export_format_idx"] = m_current_settings.export_format_idx;
    img["jpg_quality"] = m_current_settings.jpg_quality;
    img["max_res_idx"] = m_current_settings.max_res_idx;
    img["color_space_idx"] = m_current_settings.color_space_idx;
    img["import_path"] = m_current_settings.import_path;
    img["export_path"] = m_current_settings.export_path;
    img["save_in_src"] = m_current_settings.save_in_src;
    root["image"] = img;

    QJsonObject wiz;
    wiz["wiz_run_bpn"] = m_current_settings.wiz_run_bpn;
    wiz["wiz_run_moebius"] = m_current_settings.wiz_run_moebius;
    wiz["wiz_batch_export_path"] = m_current_settings.wiz_batch_export_path;
    wiz["wiz_batch_format_idx"] = m_current_settings.wiz_batch_format_idx;
    wiz["wiz_error_handling_idx"] = m_current_settings.wiz_error_handling_idx;
    wiz["wiz_create_zip"] = m_current_settings.wiz_create_zip;
    root["wizard"] = wiz;

    QJsonDocument doc(root);
    QFile file(m_config_path);
    if (file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        file.write(doc.toJson(QJsonDocument::Indented));
        file.close();
        m_dirty = false;
        m_last_save = std::chrono::steady_clock::now();
        LOG_TRACE("Settings automatically saved to disk.");
    }
    else {
        LOG_ERROR("Failed to write to settings.json");
    }
}