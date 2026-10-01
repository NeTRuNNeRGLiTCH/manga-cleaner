#include "top_bar.h"
#include "src/studio/panels/topbar_actions/file.h"
#include "src/studio/panels/topbar_actions/edit.h"
#include "src/studio/panels/topbar_actions/view.h"
#include "src/studio/panels/topbar_actions/folder.h"
#include "src/studio/panels/topbar_actions/export.h"

#include <QSpacerItem>
#include <QIcon>
#include <QPixmap>
#include <QMenu>

top_bar::top_bar(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);

    // Initialize the controllers
    file_ctrl = new file_actions(this);
    edit_ctrl = new edit_actions(this);
    view_ctrl = new view_actions(this);
    folder_ctrl = new folder_actions(this);
    export_ctrl = new export_actions(this);

    setup_ui();
}

// === MAIN UI INITIALIZATION ===

void top_bar::setup_ui() {
    QHBoxLayout* main_layout = new QHBoxLayout(this);
    main_layout->setContentsMargins(16, 0, 16, 0);
    main_layout->setSpacing(0);

    // === LEFT SECTION (Logo & Menus) ===

    QWidget* left_container = new QWidget(this);
    QHBoxLayout* left_layout = new QHBoxLayout(left_container);
    left_layout->setContentsMargins(0, 0, 0, 0);
    left_layout->setSpacing(8);

    QLabel* logo_label = new QLabel(this);
    QPixmap logo_pix(":/axis_cleaner/assets/axis_cleaner.png");
    if (!logo_pix.isNull()) {
        logo_label->setPixmap(logo_pix.scaled(28, 28, Qt::KeepAspectRatio, Qt::SmoothTransformation));
    }
    else {
        logo_label->setText("LOGO");
        logo_label->setStyleSheet("color: #9b59ff; font-weight: bold;");
    }

    QLabel* app_name = new QLabel("Axis studio", this);
    app_name->setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 14px;");

    QFrame* v_line = new QFrame(this);
    v_line->setFrameShape(QFrame::VLine);
    v_line->setFrameShadow(QFrame::Plain);
    v_line->setFixedHeight(24);
    v_line->setStyleSheet("color: #3c3c3c; margin: 0px 8px;");

    left_layout->addWidget(logo_label);
    left_layout->addWidget(app_name);
    left_layout->addWidget(v_line);

    // 1. File Menu
    QPushButton* btn_file = create_menu_button("File");
    btn_file->setMenu(file_ctrl->get_menu());
    left_layout->addWidget(btn_file);

    // 2. Edit Menu
    QPushButton* btn_edit = create_menu_button("Edit");
    btn_edit->setMenu(edit_ctrl->get_menu());
    left_layout->addWidget(btn_edit);

    // 3. View Menu
    QPushButton* btn_view = create_menu_button("View");
    btn_view->setMenu(view_ctrl->get_menu());
    left_layout->addWidget(btn_view);

    // 4. Settings Button (Direct Signal)
    QPushButton* btn_settings = create_menu_button("Settings");
    connect(btn_settings, &QPushButton::clicked, this, &top_bar::settings_requested);
    left_layout->addWidget(btn_settings);

    // 5. More... Menu (Help / About)
    QPushButton* btn_more = create_menu_button("More...");
    QMenu* more_menu = new QMenu(this);
    more_menu->setStyleSheet(
        "QMenu { background-color: #1e1e1e; color: #e0e0e0; border: 1px solid #3c3c3c; border-radius: 4px; padding: 4px 0px; }"
        "QMenu::item { padding: 6px 32px 6px 24px; background-color: transparent; }"
        "QMenu::item:selected { background-color: #3c3c3c; color: #9b59ff; }"
        "QMenu::separator { height: 1px; background: #3c3c3c; margin: 4px 12px; }"
    );

    QAction* act_help = more_menu->addAction("Help");
    QAction* act_feedback = more_menu->addAction("Send Feedback");
    QAction* act_about = more_menu->addAction("About");

    connect(act_help, &QAction::triggered, this, &top_bar::help_requested);
    connect(act_feedback, &QAction::triggered, this, &top_bar::feedback_requested);
    connect(act_about, &QAction::triggered, this, &top_bar::about_requested);

    btn_more->setMenu(more_menu);
    left_layout->addWidget(btn_more);

    // === CENTER SECTION (Resource Badges) ===

    QWidget* center_container = new QWidget(this);
    QHBoxLayout* center_layout = new QHBoxLayout(center_container);
    center_layout->setContentsMargins(0, 0, 0, 0);
    center_layout->setSpacing(16);

    QWidget* ram_badge = create_resource_badge(":/axis_cleaner/assets/icons/ram.svg", "RAM:", ram_value_label);
    QWidget* vram_badge = create_resource_badge(":/axis_cleaner/assets/icons/vram.svg", "VRAM:", vram_value_label);

    processor_badge = new QWidget(this);
    processor_badge->setObjectName("ResourceBadge");
    processor_badge->setStyleSheet("QWidget#ResourceBadge { background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 4px; }");
    processor_badge->setFixedHeight(28);

    QHBoxLayout* proc_layout = new QHBoxLayout(processor_badge);
    proc_layout->setContentsMargins(8, 0, 8, 0);
    proc_layout->setSpacing(6);

    processor_icon_label = new QLabel(this);
    processor_icon_label->setFixedSize(16, 16);
    processor_icon_label->setScaledContents(true);

    processor_text_label = new QLabel("GPU", this);
    processor_text_label->setStyleSheet("font-size: 11px; font-weight: bold; color: #4ade80;");

    proc_layout->addWidget(processor_icon_label);
    proc_layout->addWidget(processor_text_label);

    center_layout->addWidget(ram_badge);
    center_layout->addWidget(vram_badge);
    center_layout->addWidget(processor_badge);

    // === RIGHT SECTION (Actions) ===

    QWidget* right_container = new QWidget(this);
    QHBoxLayout* right_layout = new QHBoxLayout(right_container);
    right_layout->setContentsMargins(0, 0, 0, 0);
    right_layout->setSpacing(12);

    QFrame* v_line_right = new QFrame(this);
    v_line_right->setFrameShape(QFrame::VLine);
    v_line_right->setFrameShadow(QFrame::Plain);
    v_line_right->setFixedHeight(24);
    v_line_right->setStyleSheet("color: #3c3c3c; margin: 0px 8px;");

    // Folder Button (Direct Action)
    btn_folder = new QPushButton(this);
    btn_folder->setIcon(QIcon(":/axis_cleaner/assets/icons/folder.svg"));
    btn_folder->setIconSize(QSize(18, 18));
    btn_folder->setCursor(Qt::PointingHandCursor);
    btn_folder->setFixedSize(32, 32);
    btn_folder->setStyleSheet(
        "QPushButton { background-color: transparent; border-radius: 4px; }"
        "QPushButton:hover { background-color: #2b2b2b; }"
    );
    connect(btn_folder, &QPushButton::clicked, folder_ctrl, &folder_actions::on_folder_button_clicked);

    // Export Button (Direct Action - Arrow removed)
    btn_export = new QPushButton(" Export", this);
    btn_export->setIcon(QIcon(":/axis_cleaner/assets/icons/export.svg"));
    btn_export->setIconSize(QSize(16, 16));
    btn_export->setCursor(Qt::PointingHandCursor);
    btn_export->setFixedHeight(32);
    btn_export->setStyleSheet(
        "QPushButton { background-color: transparent; color: #e0e0e0; font-weight: bold; padding: 0px 8px; border-radius: 4px; border: 1px solid transparent; }"
        "QPushButton:hover { background-color: #2b2b2b; border: 1px solid #3c3c3c; }"
    );
    connect(btn_export, &QPushButton::clicked, export_ctrl, &export_actions::on_export_button_clicked);

    right_layout->addWidget(btn_folder);
    right_layout->addWidget(v_line_right);
    right_layout->addWidget(btn_export);

    // === ASSEMBLY ===
    main_layout->addWidget(left_container);
    main_layout->addStretch(3);
    main_layout->addWidget(center_container);
    main_layout->addStretch(7);
    main_layout->addWidget(right_container);

    // Initial default values
    update_ram(0.0);
    update_vram(0.0);
    set_processor_mode(true);
}

// === HELPER METHODS ===

QPushButton* top_bar::create_menu_button(const QString& text) {
    QPushButton* btn = new QPushButton(text, this);
    btn->setCursor(Qt::PointingHandCursor);
    btn->setFixedHeight(28);
    btn->setStyleSheet(
        "QPushButton { background-color: transparent; color: #e0e0e0; font-size: 12px; padding: 0px 10px; border-radius: 4px; }"
        "QPushButton:hover { background-color: #3c3c3c; }"
        "QPushButton::menu-indicator { image: none; width: 0px; }" // Hides the native Qt arrow
    );
    return btn;
}

QWidget* top_bar::create_resource_badge(const QString& icon_path, const QString& prefix_text, QLabel*& value_label) {
    QWidget* badge = new QWidget(this);
    badge->setObjectName("ResourceBadge");
    badge->setStyleSheet("QWidget#ResourceBadge { background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 4px; }");
    badge->setFixedHeight(28);

    QHBoxLayout* layout = new QHBoxLayout(badge);
    layout->setContentsMargins(8, 0, 8, 0);
    layout->setSpacing(6);

    QLabel* icon_label = new QLabel(this);
    icon_label->setFixedSize(16, 16);
    icon_label->setScaledContents(true);
    icon_label->setPixmap(QPixmap(icon_path));

    QLabel* prefix = new QLabel(prefix_text, this);
    prefix->setStyleSheet("color: #8f8f8f; font-size: 11px;");

    value_label = new QLabel("0.0 GB", this);
    value_label->setStyleSheet("color: #e0e0e0; font-family: monospace; font-size: 11px; font-weight: bold;");

    layout->addWidget(icon_label);
    layout->addWidget(prefix);
    layout->addWidget(value_label);

    return badge;
}

// === PUBLIC SLOTS / UPDATE METHODS ===

void top_bar::update_ram(double gb) {
    ram_value_label->setText(QString::number(gb, 'f', 1) + " GB");
}

void top_bar::update_vram(double gb) {
    vram_value_label->setText(QString::number(gb, 'f', 1) + " GB");
}

void top_bar::set_processor_mode(bool is_gpu) {
    if (is_gpu) {
        processor_icon_label->setPixmap(QPixmap(":/axis_cleaner/assets/icons/gpu.svg"));
        processor_text_label->setText("GPU");
        processor_text_label->setStyleSheet("font-size: 11px; font-weight: bold; color: #4ade80;"); // Emerald
    }
    else {
        processor_icon_label->setPixmap(QPixmap(":/axis_cleaner/assets/icons/cpu.svg"));
        processor_text_label->setText("CPU");
        processor_text_label->setStyleSheet("font-size: 11px; font-weight: bold; color: #fbbf24;"); // Amber
    }
}