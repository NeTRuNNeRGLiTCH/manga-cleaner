#ifndef STORAGE_CONFIG_MGR_H
#define STORAGE_CONFIG_MGR_H

#include <QString>
#include <QJsonObject>
#include <mutex>
#include <chrono>

// Represents the absolute state of the entire UI and Engine.
struct AppSettings {
    // --- 1. System Tab ---
    // Semantics (matching the UI labels): 0 = Keep Loaded (pinned in VRAM),
    // 1 = Unload Immediately, 2 = Dynamic (unload after 60s idle).
    // LaMa defaults to pinned: at ~1.4 GB it is the cheap insurance policy that
    // keeps the fast inpainter usable when the big engines hog the GPU.
    int persist_bpn = 0;
    int persist_moebius = 0;
    int persist_lama = 0;

    int arch_dispatch_mode = 0; // 0 = Auto-Detect, 1 = Force Ada, 2 = Force Turing

    // --- 2. Models Tab ---
    int bpn_prob = 65;       // Candidate threshold (0.65)
    int bpn_core = 35;       // Core seed threshold (0.35)
    int bpn_expand = 0;      // Extra dilation padding on top of the guaranteed 8px text coverage (px)

    int moebius_steps = 30;  // 30 DDIM steps (Cheatsheet)

    // Inpainting backend for the Studio clean button and the Wizard batch pass.
    // Mirrors InpaintEngine: 0 = Auto, 1 = LaMa, 2 = Moebius.
    int inpaint_engine = 0;

    // --- 3. Image Tab ---
    int export_format_idx = 0; // 0=JPG, 1=PNG, 2=WEBP, 3=PSD
    int jpg_quality = 95;
    int max_res_idx = 0;
    int color_space_idx = 1;
    QString import_path = "";
    QString export_path = "";
    bool save_in_src = false;

    // --- 4. Wizard Tab ---
    bool wiz_run_bpn = true;
    bool wiz_run_moebius = true;

    QString wiz_batch_export_path = "";
    int wiz_batch_format_idx = 3; // Default PSD
    int wiz_error_handling_idx = 0;

    bool wiz_create_zip = false;
};

class config_mgr {
public:
    static config_mgr& instance();

    void init(const QString& app_root_dir);

    AppSettings get_settings() const;
    void update_settings(const AppSettings& new_settings);

    void save();

    // Writes to disk only when there are unsaved changes (call on shutdown).
    void flush();

private:
    config_mgr() = default;
    ~config_mgr() = default;
    config_mgr(const config_mgr&) = delete;
    config_mgr& operator=(const config_mgr&) = delete;

    QString m_config_path;
    AppSettings m_current_settings;

    // Settings are read from the worker threads and written from the UI thread,
    // so the in-memory copy needs explicit protection.
    mutable std::mutex m_mutex;
    bool m_dirty = false;
    bool m_flush_scheduled = false; // A coalescing debounce write is already queued
    std::chrono::steady_clock::time_point m_last_save = std::chrono::steady_clock::now();

    void load_from_disk();

    // Applies a parsed settings object to m_current_settings (shared by the
    // normal load and the corrupt-file backup restore).
    void apply_json(const QJsonObject& root);
};

#endif // STORAGE_CONFIG_MGR_H