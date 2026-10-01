#ifndef AXIS_CLEANER_H
#define AXIS_CLEANER_H

#include <QMainWindow>
#include <QDockWidget>
#include <QWidget>
#include <QStringList>

// === UI Forward Declarations ===
class status_bar;
class left_toolbar;
class top_bar;
class right_ai_panel;
class canvas_widget;

// === Core Forward Declarations ===
class telemetry;
class session_data;
class history_stack;
class pipeline_manager;
class shortcut_mgr;

// We need the BatchConfig struct definition
#include "src/core/pipeline/batch_worker.h"

class axis_cleaner : public QMainWindow {
    Q_OBJECT

public:
    axis_cleaner(QWidget* parent = nullptr);
    ~axis_cleaner();

private slots:
    // === DIALOG HANDLERS ===
    void on_settings_requested();
    void on_help_requested();
    void on_about_requested();

    // === FILE IO & GALLERY HANDLERS ===
    void on_open_image(const QStringList& file_paths);
    void on_open_folder(const QString& folder_path);
    void on_gallery_image_requested(const QString& filepath);

    // === BATCH EXPORT HANDLER ===
    void on_batch_export_requested(const QString& output_dir);

    // === EDIT & TOOL HANDLERS ===
    void on_scan_transparency();

    // Photoshop-style "focus mode": hides every panel around the canvas.
    void toggle_ui_panels();

private:
    // === CORE CONTAINERS ===
    QWidget* main_container;
    QMainWindow* dock_manager_window;

    // === CORE WIDGETS ===
    top_bar* custom_top_bar;
    left_toolbar* custom_left_toolbar;
    right_ai_panel* custom_right_panel;
    status_bar* bottom_status_bar;
    canvas_widget* central_canvas;

    // === DOCK CONTAINERS ===
    QDockWidget* left_dock;
    QDockWidget* right_dock;

    // === BACKEND MODULES ===
    telemetry* app_telemetry;
    session_data* app_session;
    history_stack* app_history;
    pipeline_manager* app_pipeline;
    shortcut_mgr* app_shortcuts;

    // Tracker for the currently loaded workspace files
    QStringList m_active_files;

    // Index into m_active_files of the page shown on the canvas (-1 = none).
    // Drives File > Remove, Save, the gallery highlight and PageUp/PageDown.
    int m_active_file_index = -1;

    // Photoshop-style Tab "focus mode": true when the surrounding panels are hidden
    bool m_ui_hidden = false;

    // === HELPERS ===
    void export_files(const QString& output_dir, const QStringList& files);

    // Re-highlights the gallery row of m_active_file_index (no image loading).
    void update_gallery_active();

    // PageUp/PageDown: moves the gallery selection by `delta` entries and loads
    // that page, keeping the current page's working state on disk.
    void navigate_gallery(int delta);

    // === SETUP METHODS ===
    void setup_struct();
    void setup_docks();
    void setup_core();
    void setup_connections();
    void load_stylesheet();
};

#endif // AXIS_CLEANER_H