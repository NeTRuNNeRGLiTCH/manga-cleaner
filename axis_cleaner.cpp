#include "axis_cleaner.h"
#include <QCoreApplication>
#include <QFile>
#include <QVBoxLayout>
#include <QTextStream>
#include <QMessageBox>
#include <QFileInfo>
#include <QDir>
#include <QDesktopServices>
#include <QUrl>
#include <vector>

// === UI ELEMENTS ===
#include "src/studio/panels/bars/status_bar.h"
#include "src/studio/panels/bars/left_toolbar.h"
#include "src/studio/panels/bars/top_bar.h"
#include "src/studio/panels/bars/right_ai_panel.h"
#include "src/studio/widgets/canvas_widget.h"

// === UI TABS ===
#include "src/studio/panels/tabs/studio_tab.h"
#include "src/studio/panels/tabs/wizard_tab.h"
#include "src/studio/panels/tabs/gallery_tab.h"
#include "src/studio/panels/tabs/transcript_tab.h"

// === TOP BAR ACTIONS ===
#include "src/studio/panels/topbar_actions/about.h"
#include "src/studio/panels/topbar_actions/settings.h"
#include "src/studio/panels/topbar_actions/help.h"
#include "src/studio/panels/topbar_actions/file.h"
#include "src/studio/panels/topbar_actions/folder.h"
#include "src/studio/panels/topbar_actions/edit.h"
#include "src/studio/panels/topbar_actions/view.h"
#include "src/studio/panels/topbar_actions/export.h"

// === CORE BACKEND ===
#include "src/core/hardware/system_scanner.h"
#include "src/core/hardware/telemetry.h"
#include "src/core/state/session_data.h"
#include "src/core/state/history_stack.h"
#include "src/core/pipeline/pipeline_manager.h"
#include "src/core/input/shortcut_mgr.h"
#include "src/storage/workspace.h"
#include "src/storage/config_mgr.h"
#include "src/diagnostics/logger.h"

axis_cleaner::axis_cleaner(QWidget* parent) : QMainWindow(parent) {
    Logger::instance().init(QCoreApplication::applicationDirPath());
    LOG_INFO("UI Initialization starting...");

    workspace::instance().init(QCoreApplication::applicationDirPath());
    config_mgr::instance().init(QCoreApplication::applicationDirPath());

    // Disk budget for the per-page edit cache: files untouched for 30 days are
    // deleted once at startup so cleaned-page PNGs cannot grow forever.
    session_data::prune_working_state(30);

    setup_struct();
    setup_docks();
    setup_core();
    setup_connections();
    load_stylesheet();

    LOG_INFO("UI Initialization complete. Axis Studio is ready.");
}

axis_cleaner::~axis_cleaner() {
    LOG_INFO("Commencing shutdown sequence...");

    // Persist the ACTIVE page's edits one last time: work done since the last
    // page switch would otherwise be lost on close.
    if (app_session && app_session->has_active_image()) {
        const QString active_path = app_session->get_current_filepath();
        if (!active_path.isEmpty()) {
            app_session->save_working_state(
                active_path, app_session->get_current_image(), app_session->get_current_mask());
        }
    }

    // Flush any settings change that is still inside the debounce window.
    config_mgr::instance().flush();

    Logger::instance().shutdown();
}

void axis_cleaner::setup_struct() {
    setWindowTitle("Axis Studio v4.0.0");
    setMinimumSize(1280, 720);

    main_container = new QWidget(this);
    QVBoxLayout* master_layout = new QVBoxLayout(main_container);
    master_layout->setContentsMargins(0, 0, 0, 0);
    master_layout->setSpacing(0);
    setCentralWidget(main_container);

    custom_top_bar = new top_bar(this);
    custom_top_bar->setObjectName("TopBar");
    custom_top_bar->setFixedHeight(56);
    master_layout->addWidget(custom_top_bar);

    dock_manager_window = new QMainWindow(this);
    dock_manager_window->setWindowFlags(Qt::Widget);
    master_layout->addWidget(dock_manager_window, 1);

    central_canvas = new canvas_widget(this);
    central_canvas->setObjectName("Canvas");
    dock_manager_window->setCentralWidget(central_canvas);

    bottom_status_bar = new status_bar(this);
    bottom_status_bar->setObjectName("StatusBar");
    bottom_status_bar->setFixedHeight(24);
    master_layout->addWidget(bottom_status_bar);

    bottom_status_bar->update_mode("Paint");
    bottom_status_bar->update_tool("Brush");
}

void axis_cleaner::setup_docks() {
    left_dock = new QDockWidget("Tools", this);
    left_dock->setAllowedAreas(Qt::LeftDockWidgetArea | Qt::RightDockWidgetArea);
    left_dock->setFeatures(QDockWidget::DockWidgetMovable | QDockWidget::DockWidgetFloatable);
    QWidget* empty_left_title = new QWidget(this);
    left_dock->setTitleBarWidget(empty_left_title);

    custom_left_toolbar = new left_toolbar(this);
    custom_left_toolbar->setObjectName("LeftToolbar");
    custom_left_toolbar->setFixedWidth(64);
    left_dock->setWidget(custom_left_toolbar);
    dock_manager_window->addDockWidget(Qt::LeftDockWidgetArea, left_dock);

    right_dock = new QDockWidget("AI Settings", this);
    right_dock->setAllowedAreas(Qt::LeftDockWidgetArea | Qt::RightDockWidgetArea);
    right_dock->setFeatures(QDockWidget::DockWidgetMovable | QDockWidget::DockWidgetFloatable);
    QWidget* empty_right_title = new QWidget(this);
    right_dock->setTitleBarWidget(empty_right_title);

    custom_right_panel = new right_ai_panel(this);
    custom_right_panel->setObjectName("RightAIPanel");
    custom_right_panel->setFixedWidth(320);
    right_dock->setWidget(custom_right_panel);
    dock_manager_window->addDockWidget(Qt::RightDockWidgetArea, right_dock);
}

void axis_cleaner::setup_core() {
    LOG_TRACE("Allocating core memory sessions...");
    app_session = new session_data();
    app_history = new history_stack(20);
    central_canvas->set_backend(app_session, app_history);

    LOG_TRACE("Initializing AI Pipeline Manager...");
    app_pipeline = new pipeline_manager(app_session, app_history, this);
    app_shortcuts = new shortcut_mgr(this);

    // Initial status badge for loaded TensorRT models
    bottom_status_bar->update_loaded_models(app_pipeline->get_loaded_models_status());

    LOG_INFO("Scanning hardware environment...");
    ComputeDevice best_gpu = system_scanner::get_best_device();

    QString dev_log = QString("Selected Compute Device: %1 [%2]").arg(best_gpu.name).arg(best_gpu.get_vram_string());
    LOG_INFO(dev_log);

    custom_top_bar->set_processor_mode(best_gpu.type != DeviceType::CPU);

    app_telemetry = new telemetry(best_gpu.adapter_index, this);
    connect(app_telemetry, &telemetry::metrics_updated, this, [this](double ram, double vram) {
        custom_top_bar->update_ram(ram);
        custom_top_bar->update_vram(vram);
        });
    app_telemetry->start(1500);
}

void axis_cleaner::setup_connections() {
    LOG_TRACE("Wiring UI signals to backend controllers...");

    // === TOP BAR DIALOGS & ACTIONS ===
    connect(custom_top_bar, &top_bar::about_requested, this, &axis_cleaner::on_about_requested);
    connect(custom_top_bar, &top_bar::settings_requested, this, &axis_cleaner::on_settings_requested);
    connect(custom_top_bar, &top_bar::help_requested, this, &axis_cleaner::on_help_requested);
    connect(custom_top_bar, &top_bar::feedback_requested, this, []() {
        QDesktopServices::openUrl(QUrl("https://discord.gg"));
        });

    // === FILE I/O ROUTING ===
    connect(custom_top_bar->get_file_actions(), &file_actions::request_open_image, this, &axis_cleaner::on_open_image);
    connect(custom_top_bar->get_file_actions(), &file_actions::request_add_image, this, [this](const QStringList& paths) {
        m_active_files.append(paths);
        custom_right_panel->get_gallery_tab()->populate_gallery(m_active_files);
        update_gallery_active();
        });
    connect(custom_top_bar->get_file_actions(), &file_actions::request_open_chapter, this, &axis_cleaner::on_open_folder);
    connect(custom_top_bar->get_folder_actions(), &folder_actions::request_open_folder, this, &axis_cleaner::on_open_folder);
    connect(custom_top_bar->get_export_actions(), &export_actions::request_batch_export, this, &axis_cleaner::on_batch_export_requested);

    // File menu: Save exports the active page, Save All the whole gallery, Remove
    // drops the active page, Exit closes the window.
    connect(custom_top_bar->get_file_actions(), &file_actions::request_save, this, [this]() {
        AppSettings s = config_mgr::instance().get_settings();
        const QString dir = s.export_path.isEmpty() ? s.wiz_batch_export_path : s.export_path;
        // Save ONLY the page that is active (File > Save and Ctrl+S are
        // the same command); Save All covers the whole gallery.
        const QString active_path = app_session->get_current_filepath();
        if (active_path.isEmpty()) return;
        export_files(dir, QStringList{ active_path });
        });
    connect(custom_top_bar->get_file_actions(), &file_actions::request_save_all, this, [this]() {
        AppSettings s = config_mgr::instance().get_settings();
        export_files(s.export_path.isEmpty() ? s.wiz_batch_export_path : s.export_path, m_active_files);
        });
    connect(custom_top_bar->get_file_actions(), &file_actions::request_clear_cached_edits, this, [this]() {
        // The active page is flushed separately when its session dies, so it
        // would be re-written on the next page switch; dropping the session
        // first keeps "Clear" truly exhaustive.
        const int removed = session_data::clear_working_state();
        app_session->clear_session();
        app_history->clear();
        m_active_file_index = -1;
        central_canvas->update();
        bottom_status_bar->update_status(QString("Cleared %1 cached page edit(s) from disk.").arg(removed));
        });
    connect(custom_top_bar->get_file_actions(), &file_actions::request_remove, this, [this]() {
        if (m_active_files.isEmpty()) return;

        // Remove the page the user is LOOKING at, not blindly the first entry.
        // The session was loaded from the same index, so the fallback keeps the
        // two in sync even if a load ever failed.
        int index = m_active_file_index;
        if (index < 0 || index >= m_active_files.size()) index = 0;

        const QString removed = m_active_files.takeAt(index);
        app_session->clear_session();
        app_history->clear();

        // Re-point the tracker at the entry that slid into the removed slot.
        m_active_file_index = (index < m_active_files.size()) ? index : m_active_files.size() - 1;

        custom_right_panel->get_gallery_tab()->populate_gallery(m_active_files);

        if (m_active_file_index >= 0) {
            on_gallery_image_requested(m_active_files.at(m_active_file_index));
        }
        else {
            central_canvas->update();
            bottom_status_bar->update_status("Removed: " + QFileInfo(removed).fileName());
        }
        });
    connect(custom_top_bar->get_file_actions(), &file_actions::request_exit, this, &axis_cleaner::close);

    // View menu
    connect(custom_top_bar->get_view_actions(), &view_actions::request_zoom_in, central_canvas, &canvas_widget::zoom_in);
    connect(custom_top_bar->get_view_actions(), &view_actions::request_zoom_out, central_canvas, &canvas_widget::zoom_out);
    connect(custom_top_bar->get_view_actions(), &view_actions::request_zoom_fit, central_canvas, &canvas_widget::zoom_fit);
    connect(custom_top_bar->get_view_actions(), &view_actions::request_toggle_panels, this, &axis_cleaner::toggle_ui_panels);

    connect(custom_right_panel->get_gallery_tab(), &gallery_tab::request_open_image, this, &axis_cleaner::on_gallery_image_requested);

    // Gallery trash button: the panel wipes its own items; drop the main
    // window's copy of the list too, or Save All / Run Wizard would still
    // process every file the user just "deleted".
    connect(custom_right_panel->get_gallery_tab(), &gallery_tab::clear_requested, this, [this]() {
        m_active_files.clear();
        m_active_file_index = -1;
        app_session->clear_session();
        app_history->clear();
        central_canvas->update();
        bottom_status_bar->update_status("Gallery cleared.");
        });

    // === LEFT TOOLBAR -> CANVAS WIRING ===
    connect(custom_left_toolbar, &left_toolbar::tool_changed, this, [this](const QString& tool_name) {
        bottom_status_bar->update_tool(tool_name);
        if (tool_name == "Brush") central_canvas->set_tool(CanvasTool::Brush);
        else if (tool_name == "Rectangle") central_canvas->set_tool(CanvasTool::Rect);
        else if (tool_name == "Lasso") central_canvas->set_tool(CanvasTool::Lasso);
        else if (tool_name == "Wand") central_canvas->set_tool(CanvasTool::Wand);
        else if (tool_name == "Color") central_canvas->set_tool(CanvasTool::Color);
        });

    connect(custom_left_toolbar, &left_toolbar::mode_changed, this, [this](const QString& mode_name) {
        bottom_status_bar->update_mode(mode_name);
        central_canvas->set_erase_mode(mode_name == "Erase");
        if (mode_name == "Move") central_canvas->set_tool(CanvasTool::Move);
        });

    connect(custom_left_toolbar, &left_toolbar::brush_size_changed, this, [this](int size) { central_canvas->set_brush_size(size); });
    connect(custom_left_toolbar, &left_toolbar::wand_tolerance_changed, this, [this](int tol) { central_canvas->set_wand_tolerance(tol); });
    connect(central_canvas, &canvas_widget::brush_size_changed, custom_left_toolbar, &left_toolbar::set_brush_size);

    // === RIGHT PANEL -> PIPELINE MANAGER ===
    connect(custom_right_panel->get_studio_tab(), &studio_tab::run_detect_requested, this, [this]() {
        app_pipeline->request_studio_task(AI_TaskType::RunOCR);
        });
    connect(custom_right_panel->get_studio_tab(), &studio_tab::scan_transparency_requested, this, &axis_cleaner::on_scan_transparency);
    connect(custom_right_panel->get_studio_tab(), &studio_tab::run_clean_requested, this, [this]() {
        app_pipeline->request_studio_task(AI_TaskType::RunClean);
        });
    // Kill switch: drops queued tasks and cooperatively aborts the running stage.
    connect(custom_right_panel->get_studio_tab(), &studio_tab::stop_requested, this, [this]() {
        app_pipeline->request_cancel();
        custom_right_panel->update_progress(0);
        });

    // === INPAINTING MODEL SELECTOR (persisted) ===
    studio_tab* studio_panel = custom_right_panel->get_studio_tab();
    studio_panel->set_inpaint_engine(config_mgr::instance().get_settings().inpaint_engine);
    connect(studio_panel, &studio_tab::inpaint_engine_changed, this, [](int engine) {
        AppSettings s = config_mgr::instance().get_settings();
        s.inpaint_engine = engine;
        config_mgr::instance().update_settings(s);
        });

    connect(custom_right_panel->get_wizard_tab(), &wizard_tab::run_wizard_requested, this, [this](bool scan_transparency) {
        if (m_active_files.isEmpty()) {
            QMessageBox::warning(this, "Empty Batch", "Please load a folder or add images to the Gallery first.");
            return;
        }

        AppSettings s = config_mgr::instance().get_settings();
        BatchConfig config;
        config.input_files = m_active_files;
        config.output_dir = s.wiz_batch_export_path;

        QStringList formats = { "JPG", "PNG", "WEBP", "PSD" };
        if (s.wiz_batch_format_idx >= 0 && s.wiz_batch_format_idx < formats.size()) {
            config.export_format = formats[s.wiz_batch_format_idx];
        }
        else {
            config.export_format = "PSD";
        }

        config.run_bpn = s.wiz_run_bpn;
        config.scan_transparency = scan_transparency;
        config.run_moebius = s.wiz_run_moebius;

        config.halt_on_error = (s.wiz_error_handling_idx == 1);
        config.create_zip = s.wiz_create_zip;

        custom_right_panel->get_wizard_tab()->update_status_total(m_active_files.size());
        custom_right_panel->get_wizard_tab()->update_status_processed(0);
        custom_right_panel->get_wizard_tab()->update_status_failed(0);

        app_pipeline->start_batch_job(config);
        });

    connect(custom_right_panel->get_wizard_tab(), &wizard_tab::stop_wizard_requested, app_pipeline, &pipeline_manager::cancel_batch_job);

    // === PIPELINE MANAGER -> RIGHT PANEL ===
    connect(app_pipeline, &pipeline_manager::global_status_changed, this, [this](const QString& status) {
        custom_right_panel->set_ai_state("working", status);
        custom_right_panel->get_wizard_tab()->update_status_task(status);
        });
    connect(app_pipeline, &pipeline_manager::global_progress_updated, this, [this](int pct) {
        custom_right_panel->update_progress(pct);
        });
    connect(app_pipeline, &pipeline_manager::global_error_occurred, this, [this](const QString& error) {
        LOG_ERROR(error);
        custom_right_panel->set_ai_state("error", error);
        });
    connect(app_pipeline, &pipeline_manager::studio_task_finished, this, [this](bool success) {
        if (success) {
            custom_right_panel->set_ai_state("idle");
        }
        else if (app_pipeline->is_cancelled()) {
            custom_right_panel->set_ai_state("idle");
        }
        central_canvas->update();
        });
    connect(app_pipeline, &pipeline_manager::batch_progress_stepped, this, [this](int processed, int total) {
        custom_right_panel->get_wizard_tab()->update_status_processed(processed);
        });
    connect(app_pipeline, &pipeline_manager::batch_progress_failed, this, [this](int failed) {
        custom_right_panel->get_wizard_tab()->update_status_failed(failed);
        });
    connect(app_pipeline, &pipeline_manager::batch_job_finished, this, [this](bool success) {
        custom_right_panel->set_ai_state("idle");
        custom_right_panel->get_wizard_tab()->update_status_task("Idle");
        if (success) QMessageBox::information(this, "Batch Complete", "Wizard processing completed successfully.");
        });
    connect(app_pipeline, &pipeline_manager::new_transcript_available, this, [this](const QString& text) {
        custom_right_panel->get_transcript_tab()->append_transcript_text(text);
        });
    connect(app_pipeline, &pipeline_manager::loaded_models_changed, bottom_status_bar, &status_bar::update_loaded_models);

    // === EDIT MENU ACTIONS ===
    connect(custom_top_bar->get_edit_actions(), &edit_actions::request_undo_selection, this, [this]() {
        if (app_history->undo_selection(app_session)) central_canvas->update();
        });
    connect(custom_top_bar->get_edit_actions(), &edit_actions::request_redo_selection, this, [this]() {
        if (app_history->redo_selection(app_session)) central_canvas->update();
        });
    connect(custom_top_bar->get_edit_actions(), &edit_actions::request_undo_inpaint, this, [this]() {
        if (app_history->undo_inpaint(app_session)) central_canvas->update();
        });
    connect(custom_top_bar->get_edit_actions(), &edit_actions::request_redo_inpaint, this, [this]() {
        if (app_history->redo_inpaint(app_session)) central_canvas->update();
        });
    connect(custom_top_bar->get_edit_actions(), &edit_actions::request_delete_mask, this, [this]() {
        if (!app_session || !app_session->has_active_image()) return;
        cv::Mat old_mask = app_session->get_current_mask();
        if (!old_mask.empty()) {
            cv::Mat empty_mask = cv::Mat::zeros(old_mask.size(), CV_8UC1);
            app_session->set_mask(empty_mask);
            app_history->commit_mask_state(old_mask, empty_mask);
            central_canvas->update();
            bottom_status_bar->update_status("Mask cleared.");
        }
        });
    connect(custom_top_bar->get_edit_actions(), &edit_actions::request_scan_transparency, this, &axis_cleaner::on_scan_transparency);

    // === GLOBAL SHORTCUTS & HISTORY ===
    connect(app_shortcuts, &shortcut_mgr::sig_undo_mask, this, [this]() {
        if (app_history->undo_selection(app_session)) central_canvas->update();
        });
    connect(app_shortcuts, &shortcut_mgr::sig_redo_mask, this, [this]() {
        if (app_history->redo_selection(app_session)) central_canvas->update();
        });
    connect(app_shortcuts, &shortcut_mgr::sig_undo_image, this, [this]() {
        if (app_history->undo_inpaint(app_session)) central_canvas->update();
        });
    connect(app_shortcuts, &shortcut_mgr::sig_redo_image, this, [this]() {
        if (app_history->redo_inpaint(app_session)) central_canvas->update();
        });

    // Tool Selection Shortcuts
    connect(app_shortcuts, &shortcut_mgr::sig_mode_paint, this, [this]() {
        custom_left_toolbar->set_mode("Paint");
        });
    connect(app_shortcuts, &shortcut_mgr::sig_mode_erase, this, [this]() {
        custom_left_toolbar->set_mode("Erase");
        });
    connect(app_shortcuts, &shortcut_mgr::sig_tool_move, this, [this]() {
        custom_left_toolbar->set_mode("Move");
        });
    connect(app_shortcuts, &shortcut_mgr::sig_tool_brush, this, [this]() {
        custom_left_toolbar->set_tool("Brush");
        });
    connect(app_shortcuts, &shortcut_mgr::sig_tool_rect, this, [this]() {
        custom_left_toolbar->set_tool("Rectangle");
        });
    connect(app_shortcuts, &shortcut_mgr::sig_tool_lasso, this, [this]() {
        custom_left_toolbar->set_tool("Lasso");
        });
    connect(app_shortcuts, &shortcut_mgr::sig_tool_wand, this, [this]() {
        custom_left_toolbar->set_tool("Wand");
        });

    // Brush Sizing Shortcuts ([ and ])
    connect(app_shortcuts, &shortcut_mgr::sig_decrease_value, this, [this]() {
        custom_left_toolbar->adjust_brush_size(-5);
        });
    connect(app_shortcuts, &shortcut_mgr::sig_increase_value, this, [this]() {
        custom_left_toolbar->adjust_brush_size(5);
        });

    // Zoom Shortcuts
    connect(app_shortcuts, &shortcut_mgr::sig_zoom_in, central_canvas, &canvas_widget::zoom_in);
    connect(app_shortcuts, &shortcut_mgr::sig_zoom_out, central_canvas, &canvas_widget::zoom_out);
    connect(app_shortcuts, &shortcut_mgr::sig_zoom_fit, central_canvas, &canvas_widget::zoom_fit);

    // PageUp/PageDown: flip through the gallery (per-page working state keeps
    // every page's edits while navigating).
    connect(app_shortcuts, &shortcut_mgr::sig_page_next, this, [this]() { navigate_gallery(+1); });
    connect(app_shortcuts, &shortcut_mgr::sig_page_prev, this, [this]() { navigate_gallery(-1); });

    // Tab / View > Toggle Panels: Photoshop-style "focus mode".
    connect(app_shortcuts, &shortcut_mgr::sig_toggle_ui, this, &axis_cleaner::toggle_ui_panels);

    // AI Execution Shortcuts
    connect(app_shortcuts, &shortcut_mgr::sig_run_ocr, this, [this]() {
        app_pipeline->request_studio_task(AI_TaskType::RunOCR);
        });
    connect(app_shortcuts, &shortcut_mgr::sig_run_inpaint, this, [this]() {
        app_pipeline->request_studio_task(AI_TaskType::RunClean);
        });

    // File & Export Shortcuts
    connect(app_shortcuts, &shortcut_mgr::sig_export, this, [this]() {
        // Same command as File > Save: export only the page on the canvas.
        AppSettings s = config_mgr::instance().get_settings();
        const QString dir = s.export_path.isEmpty() ? s.wiz_batch_export_path : s.export_path;
        const QString active_path = app_session->get_current_filepath();
        if (active_path.isEmpty()) return;
        export_files(dir, QStringList{ active_path });
        });
    connect(app_shortcuts, &shortcut_mgr::sig_open, this, [this]() {
        QList<QAction*> acts = custom_top_bar->get_file_actions()->get_menu()->actions();
        if (!acts.isEmpty()) acts.first()->trigger();
        });
    connect(app_shortcuts, &shortcut_mgr::sig_open_folder, this, [this]() {
        custom_top_bar->get_folder_actions()->on_folder_button_clicked();
        });
}

// === FILE I/O HANDLERS ===

void axis_cleaner::on_open_image(const QStringList& file_paths) {
    if (file_paths.isEmpty()) return;

    LOG_INFO("Opening Image: " + file_paths.first());

    m_active_files = file_paths;
    m_active_file_index = 0;
    custom_right_panel->get_gallery_tab()->populate_gallery(m_active_files);
    on_gallery_image_requested(m_active_files.first());
}

void axis_cleaner::on_open_folder(const QString& folder_path) {
    LOG_INFO("Opening Folder: " + folder_path);
    QDir dir(folder_path);

    QStringList filters;
    filters << "*.png" << "*.jpg" << "*.jpeg" << "*.webp" << "*.bmp";
    QStringList files = dir.entryList(filters, QDir::Files | QDir::NoSymLinks);

    QStringList absolute_paths;
    for (const auto& file : files) {
        absolute_paths << dir.absoluteFilePath(file);
    }

    if (!absolute_paths.isEmpty()) {
        m_active_files = absolute_paths;
        m_active_file_index = 0;
        custom_right_panel->get_gallery_tab()->populate_gallery(m_active_files);
        on_gallery_image_requested(m_active_files.first());
    }
    else {
        LOG_WARN("Opened folder contains no supported images.");
    }
}

void axis_cleaner::on_gallery_image_requested(const QString& filepath) {
    LOG_INFO("Loading image into canvas: " + filepath);

    if (app_session->load_image(filepath)) {
        app_history->clear();

        // Track which gallery row is on the canvas so Remove / Save / PageUp /
        // PageDown operate on the page the user actually sees.
        m_active_file_index = m_active_files.indexOf(filepath);
        update_gallery_active();

        central_canvas->update();

        QFileInfo fi(filepath);
        bottom_status_bar->update_status("Loaded: " + fi.fileName());
    }
    else {
        LOG_ERROR("Failed to load image from gallery: " + filepath);
    }
}

void axis_cleaner::update_gallery_active() {
    if (m_active_file_index >= 0 && m_active_file_index < m_active_files.size()) {
        custom_right_panel->get_gallery_tab()->set_active_file(m_active_files.at(m_active_file_index));
    }
}

void axis_cleaner::navigate_gallery(int delta) {
    if (m_active_files.isEmpty()) return;

    const int target = m_active_file_index + delta;
    if (target < 0 || target >= m_active_files.size()) return; // already at the first/last page

    // Re-entering load_image saves the current page's edits and restores the
    // target page's persisted state, so flipping pages never loses work.
    on_gallery_image_requested(m_active_files.at(target));
}

void axis_cleaner::on_batch_export_requested(const QString& output_dir) {
    export_files(output_dir, m_active_files);
}

void axis_cleaner::export_files(const QString& output_dir, const QStringList& files) {
    if (files.isEmpty()) {
        QMessageBox::warning(this, "Empty Export", "No files loaded in the Gallery to export.");
        return;
    }

    BatchConfig config;
    config.input_files = files;
    config.output_dir = output_dir;

    int fmt_idx = config_mgr::instance().get_settings().export_format_idx;
    QStringList formats = { "JPG", "PNG", "WEBP", "PSD" };
    if (fmt_idx >= 0 && fmt_idx < formats.size()) {
        config.export_format = formats[fmt_idx];
    }
    else {
        config.export_format = "PSD";
    }

    config.run_bpn = false;
    config.scan_transparency = false;
    config.run_moebius = false;
    config.create_zip = false;
    config.halt_on_error = false;
    config.use_session_state = true;

    if (app_session && app_session->has_active_image()) {
        const QString active_path = app_session->get_current_filepath();
        if (!active_path.isEmpty()) {
            app_session->save_working_state(
                active_path, app_session->get_current_image(), app_session->get_current_mask());
        }
    }

    app_pipeline->start_batch_job(config);
}

// === EDIT & TOOL HANDLERS ===

void axis_cleaner::on_scan_transparency() {
    if (!app_session || !app_session->has_active_image()) {
        bottom_status_bar->update_status("Transparency Scanner: No active image loaded.");
        return;
    }

    cv::Mat img = app_session->get_current_image();
    if (img.channels() != 4) {
        img = app_session->get_original_image();
    }

    if (img.empty() || img.channels() != 4) {
        bottom_status_bar->update_status("Transparency Scanner: Image has no alpha channel (0 transparent pixels).");
        return;
    }

    std::vector<cv::Mat> channels;
    cv::split(img, channels);
    cv::Mat alpha = channels[3];

    // Pixels where alpha == 0
    cv::Mat transparent_mask = (alpha == 0);
    int count = cv::countNonZero(transparent_mask);

    if (count > 0) {
        cv::Mat old_mask = app_session->get_current_mask();
        cv::Mat new_mask;
        if (old_mask.empty() || old_mask.size() != transparent_mask.size()) {
            new_mask = transparent_mask.clone();
        }
        else {
            cv::bitwise_or(old_mask, transparent_mask, new_mask);
        }
        app_session->set_mask(new_mask);
        app_history->commit_mask_state(old_mask, new_mask);
        central_canvas->update();
        bottom_status_bar->update_status(QString("Transparency Scanner: Detected %1 transparent pixels (added to mask).").arg(count));
    }
    else {
        bottom_status_bar->update_status("Transparency Scanner: 0 transparent pixels found.");
    }
}

void axis_cleaner::toggle_ui_panels() {
    m_ui_hidden = !m_ui_hidden;
    custom_top_bar->setVisible(!m_ui_hidden);
    bottom_status_bar->setVisible(!m_ui_hidden);
    left_dock->setVisible(!m_ui_hidden);
    right_dock->setVisible(!m_ui_hidden);
}

// === DIALOG HANDLERS ===

void axis_cleaner::on_about_requested() { about_dialog dialog(this); dialog.exec(); }
void axis_cleaner::on_settings_requested() { settings_dialog dialog(this); dialog.exec(); }
void axis_cleaner::on_help_requested() { help_dialog dialog(this); dialog.exec(); }

void axis_cleaner::load_stylesheet() {
    QFile file(":/studio/style.qss");
    if (file.open(QFile::ReadOnly | QFile::Text)) {
        QTextStream stream(&file);
        setStyleSheet(stream.readAll());
        file.close();
    }
    else {
        setStyleSheet(
            "QMainWindow { background-color: #2b2b2b; }"
            "QWidget#Canvas { background-color: #2b2b2b; }"
            "QWidget#TopBar, QWidget#LeftToolbar, QWidget#RightAIPanel { background-color: #1e1e1e; border: 1px solid #3c3c3c; }"
            "QWidget#StatusBar { background-color: #1e1e1e; border-top: 1px solid #3c3c3c; }"
        );
    }
}