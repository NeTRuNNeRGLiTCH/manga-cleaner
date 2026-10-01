#include "settings.h"
#include "src/studio/panels/topbar_actions/settings_controllers/models.h"
#include "src/studio/panels/topbar_actions/settings_controllers/system.h"
#include "src/studio/panels/topbar_actions/settings_controllers/image.h" 
#include "src/studio/panels/topbar_actions/settings_controllers/wizard.h"
#include <QFile>
#include <QLabel>
#include <QPainter>

settings_dialog::settings_dialog(QWidget* parent) : QDialog(parent) {
    this->setWindowTitle("Axis Studio Settings");
    this->setFixedSize(900, 650);
    this->setStyleSheet("QDialog { background-color: #0b0b0e; border: 1px solid #3c3c3c; border-radius: 8px; }");

    setup_ui();
}

void settings_dialog::setup_ui() {
    QHBoxLayout* master_layout = new QHBoxLayout(this);
    master_layout->setContentsMargins(0, 0, 0, 0);
    master_layout->setSpacing(0);

    // ==========================================
    // LEFT PANEL: NAVIGATION
    // ==========================================
    QWidget* left_panel = new QWidget(this);
    left_panel->setFixedWidth(220);
    left_panel->setStyleSheet("background-color: #121217; border-right: 1px solid #3c3c3c; border-top-left-radius: 8px; border-bottom-left-radius: 8px;");

    QVBoxLayout* nav_layout = new QVBoxLayout(left_panel);
    nav_layout->setContentsMargins(12, 24, 12, 24);
    nav_layout->setSpacing(8);

    QLabel* nav_title = new QLabel("SETTINGS", left_panel);
    nav_title->setStyleSheet("color: #6f6f6f; font-size: 11px; font-weight: bold; letter-spacing: 2px; margin-bottom: 12px; border: none; background: transparent;");
    nav_layout->addWidget(nav_title);

    nav_group = new QButtonGroup(this);
    nav_group->setExclusive(true);

    // Create the 5 Nav Buttons
    QPushButton* btn_models = create_nav_button("Models", ":/axis_cleaner/assets/icons/dna.svg");
    QPushButton* btn_system = create_nav_button("System", ":/axis_cleaner/assets/icons/gpu.svg");
    QPushButton* btn_image = create_nav_button("Image", ":/axis_cleaner/assets/icons/images.svg");
    QPushButton* btn_wizard = create_nav_button("Wizard", ":/axis_cleaner/assets/icons/wizard.svg");
    QPushButton* btn_more = create_nav_button("More...", ":/axis_cleaner/assets/icons/folder.svg");

    nav_group->addButton(btn_models, 0);
    nav_group->addButton(btn_system, 1);
    nav_group->addButton(btn_image, 2);
    nav_group->addButton(btn_wizard, 3);
    nav_group->addButton(btn_more, 4);

    nav_layout->addWidget(btn_models);
    nav_layout->addWidget(btn_system);
    nav_layout->addWidget(btn_image);
    nav_layout->addWidget(btn_wizard);
    nav_layout->addWidget(btn_more);
    nav_layout->addStretch();

    // Close Button
    QPushButton* btn_close = new QPushButton("Close Settings", left_panel);
    btn_close->setFixedHeight(36);
    btn_close->setCursor(Qt::PointingHandCursor);
    btn_close->setStyleSheet("QPushButton { background-color: transparent; color: #8f8f8f; border: 1px solid #3c3c3c; border-radius: 4px; font-weight: bold; } QPushButton:hover { background-color: #2b2b2b; color: #e0e0e0; }");
    connect(btn_close, &QPushButton::clicked, this, &QDialog::accept);
    nav_layout->addWidget(btn_close);

    master_layout->addWidget(left_panel);

    // ==========================================
    // RIGHT PANEL: CONTENT STACK
    // ==========================================
    QWidget* right_panel = new QWidget(this);
    right_panel->setStyleSheet("background-color: #1e1e1e; border-top-right-radius: 8px; border-bottom-right-radius: 8px;");

    QVBoxLayout* content_layout = new QVBoxLayout(right_panel);
    content_layout->setContentsMargins(24, 24, 24, 24);

    stacked_content = new QStackedWidget(right_panel);

    // Instantiate and add the real sub-controllers
    ctrl_models = new settings_models(this);
    ctrl_system = new settings_system(this);
    ctrl_image = new settings_image(this);  // Corrected to singular
    ctrl_wizard = new settings_wizard(this);

    stacked_content->addWidget(ctrl_models); // Index 0
    stacked_content->addWidget(ctrl_system); // Index 1
    stacked_content->addWidget(ctrl_image);  // Index 2
    stacked_content->addWidget(ctrl_wizard); // Index 3

    // Index 4: More... (The Easter Egg)
    QWidget* page_more = new QWidget(this);
    QVBoxLayout* lay_more = new QVBoxLayout(page_more);
    QLabel* egg_text = new QLabel(
        "<h2 style='color: #9b59ff;'>Sector Locked</h2>"
        "<p style='color: #8f8f8f; font-size: 13px;'>"
        "The Arcadian Architects are still forging this region of the grid.<br>"
        "New transmutations will manifest soon."
        "</p>", page_more);
    egg_text->setAlignment(Qt::AlignCenter);
    lay_more->addStretch();
    lay_more->addWidget(egg_text);
    lay_more->addStretch();
    stacked_content->addWidget(page_more);

    content_layout->addWidget(stacked_content);
    master_layout->addWidget(right_panel);

    connect(nav_group, &QButtonGroup::idClicked, this, &settings_dialog::on_nav_clicked);
    btn_models->setChecked(true);
}

QPushButton* settings_dialog::create_nav_button(const QString& text, const QString& icon_path) {
    QPushButton* btn = new QPushButton("  " + text, this);
    btn->setCheckable(true);
    btn->setFixedHeight(40);
    btn->setCursor(Qt::PointingHandCursor);
    btn->setStyleSheet(
        "QPushButton { background-color: transparent; color: #8f8f8f; text-align: left; padding-left: 12px; border: none; border-radius: 6px; font-weight: bold; font-size: 13px; }"
        "QPushButton:hover { background-color: #1a1a20; color: #e0e0e0; }"
        "QPushButton:checked { background-color: #2b2b36; color: #9b59ff; border-left: 3px solid #9b59ff; border-radius: 0; }"
    );

    QIcon icon;
    icon.addPixmap(recolor_svg(icon_path, "#8f8f8f"), QIcon::Normal, QIcon::Off);
    icon.addPixmap(recolor_svg(icon_path, "#9b59ff"), QIcon::Normal, QIcon::On);
    btn->setIcon(icon);
    btn->setIconSize(QSize(20, 20));

    return btn;
}

QPixmap settings_dialog::recolor_svg(const QString& path, const QString& hex_color) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) return QPixmap();
    QPixmap original;
    original.loadFromData(file.readAll(), "SVG");
    file.close();

    QPixmap recolored(original.size());
    recolored.fill(Qt::transparent);
    QPainter painter(&recolored);
    painter.drawPixmap(0, 0, original);
    painter.setCompositionMode(QPainter::CompositionMode_SourceIn);
    painter.fillRect(recolored.rect(), QColor(hex_color));
    painter.end();
    return recolored;
}

void settings_dialog::on_nav_clicked(int index) {
    stacked_content->setCurrentIndex(index);
}