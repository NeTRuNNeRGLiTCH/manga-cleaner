#include "right_ai_panel.h"
#include "src/studio/panels/tabs/studio_tab.h"
#include "src/studio/panels/tabs/wizard_tab.h"
#include "src/studio/panels/tabs/gallery_tab.h"
#include "src/studio/panels/tabs/transcript_tab.h"
#include <QFile>
#include <QSize>
#include <QPainter>

right_ai_panel::right_ai_panel(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);
    current_movie = nullptr;
    setup_ui();
}

void right_ai_panel::setup_ui() {
    QVBoxLayout* main_layout = new QVBoxLayout(this);
    main_layout->setContentsMargins(0, 0, 0, 0);
    main_layout->setSpacing(0);

    // === AI STATUS SECTION ===
    QWidget* status_container = new QWidget(this);
    status_container->setFixedHeight(140);
    status_container->setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #3c3c3c;");

    QVBoxLayout* status_layout = new QVBoxLayout(status_container);
    status_layout->setAlignment(Qt::AlignCenter);
    status_layout->setSpacing(8);

    anim_label = new QLabel(this);
    anim_label->setFixedSize(72, 72);
    anim_label->setAlignment(Qt::AlignCenter);
    anim_label->setStyleSheet("border: none; border-radius: 8px; background-color: transparent;");

    status_text_label = new QLabel("AI Engine Idle", this);
    status_text_label->setStyleSheet("color: #8f8f8f; font-size: 11px; font-weight: bold; border: none;");
    status_text_label->setAlignment(Qt::AlignCenter);

    progress_bar = new QProgressBar(this);
    progress_bar->setFixedHeight(12);
    progress_bar->setRange(0, 100);
    progress_bar->setValue(0);
    progress_bar->setTextVisible(false);
    progress_bar->setStyleSheet(
        "QProgressBar { background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 6px; }"
        "QProgressBar::chunk { background-color: #9b59ff; border-radius: 5px; }"
    );
    progress_bar->hide();

    status_layout->addWidget(anim_label, 0, Qt::AlignHCenter);
    status_layout->addWidget(status_text_label, 0, Qt::AlignHCenter);
    status_layout->addWidget(progress_bar);

    main_layout->addWidget(status_container);

    // === NAVIGATION ROWS ===
    QWidget* nav_container = new QWidget(this);
    nav_container->setStyleSheet("background-color: #242424;");

    QVBoxLayout* nav_layout = new QVBoxLayout(nav_container);
    nav_layout->setContentsMargins(8, 6, 8, 6);
    nav_layout->setSpacing(4);

    nav_group = new QButtonGroup(this);
    nav_group->setExclusive(true);

    QWidget* row1_container = new QWidget(this);
    QHBoxLayout* row1 = new QHBoxLayout(row1_container);
    row1->setContentsMargins(0, 0, 0, 0);
    row1->setSpacing(0);

    btn_studio = create_nav_button("Studio", ":/axis_cleaner/assets/icons/dna.svg", "#9b59ff"); // Violet
    btn_wizard = create_nav_button("Wizard", ":/axis_cleaner/assets/icons/zap.svg", "#4a9eff");  // Blue

    nav_group->addButton(btn_studio, 0);
    nav_group->addButton(btn_wizard, 1);

    row1->addWidget(btn_studio);
    row1->addWidget(btn_wizard);

    QWidget* row2_container = new QWidget(this);
    QHBoxLayout* row2 = new QHBoxLayout(row2_container);
    row2->setContentsMargins(0, 0, 0, 0);
    row2->setSpacing(0);

    btn_gallery = create_nav_button("Gallery", ":/axis_cleaner/assets/icons/images.svg", "#e0e0e0"); // White
    btn_layers = create_nav_button("Layers", ":/axis_cleaner/assets/icons/layers.svg", "#ffb86c"); // Orange
    btn_easter_egg = create_nav_button("Easter Egg", ":/axis_cleaner/assets/icons/wand-sparkles.svg", "#50fa7b"); // Green

    nav_group->addButton(btn_gallery, 2);
    nav_group->addButton(btn_layers, 3);
    nav_group->addButton(btn_easter_egg, 4);

    row2->addWidget(btn_gallery);
    row2->addWidget(btn_layers);
    row2->addWidget(btn_easter_egg);

    nav_layout->addWidget(row1_container);
    nav_layout->addWidget(row2_container);

    main_layout->addWidget(nav_container);

    // === STACKED CONTENT AREA ===
    stacked_content = new QStackedWidget(this);

    // Index 0: Studio Tab
    m_studio_tab = new studio_tab(this);
    stacked_content->addWidget(m_studio_tab);

    // Index 1: Wizard Tab
    m_wizard_tab = new wizard_tab(this);
    stacked_content->addWidget(m_wizard_tab);

    // Index 2: Gallery Tab
    m_gallery_tab = new gallery_tab(this);
    stacked_content->addWidget(m_gallery_tab);

    // Index 3: Layers Tab (Placeholder for now)
    stacked_content->addWidget(create_placeholder_page("Layers Content\n(Mask Management)"));

    // Index 4: Transcript Tab
    m_transcript_tab = new transcript_tab(this);
    stacked_content->addWidget(m_transcript_tab);

    main_layout->addWidget(stacked_content);

    // === CONNECTIONS & INITIAL STATE ===
    connect(nav_group, &QButtonGroup::idClicked, this, &right_ai_panel::on_nav_clicked);
    btn_studio->setChecked(true);

    set_ai_state("idle");
}

// === HELPER METHODS ===

QPixmap right_ai_panel::recolor_svg(const QString& path, const QString& hex_color) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) return QPixmap();
    QPixmap original;
    original.loadFromData(file.readAll(), "SVG");
    file.close();

    if (original.isNull()) return original;

    QPixmap recolored(original.size());
    recolored.fill(Qt::transparent);
    QPainter painter(&recolored);
    painter.setRenderHint(QPainter::Antialiasing);
    painter.setRenderHint(QPainter::SmoothPixmapTransform);
    painter.drawPixmap(0, 0, original);
    painter.setCompositionMode(QPainter::CompositionMode_SourceIn);
    painter.fillRect(recolored.rect(), QColor(hex_color));
    painter.end();
    return recolored;
}

QPushButton* right_ai_panel::create_nav_button(const QString& text, const QString& icon_path, const QString& active_color) {
    QPushButton* btn = new QPushButton(text, this);
    btn->setCheckable(true);
    btn->setFixedHeight(48);
    btn->setCursor(Qt::PointingHandCursor);

    QIcon state_icon;
    state_icon.addPixmap(recolor_svg(icon_path, "#8f8f8f"), QIcon::Normal, QIcon::Off); // Gray when inactive
    state_icon.addPixmap(recolor_svg(icon_path, active_color), QIcon::Normal, QIcon::On); // Custom color when active

    btn->setIcon(state_icon);
    btn->setIconSize(QSize(20, 20));

    btn->setStyleSheet(QString(
        "QPushButton { "
        "   background-color: transparent; "
        "   color: #8f8f8f; "
        "   border: none; "
        "   border-radius: 6px; "
        "   margin: 0px 4px; "
        "   font-weight: bold; "
        "   font-size: 12px; "
        "}"
        "QPushButton:hover { background-color: #323232; color: #e0e0e0; }"
        "QPushButton:checked { "
        "   background-color: #3c3c3c; "
        "   color: %1; "
        "}"
    ).arg(active_color));

    return btn;
}

QWidget* right_ai_panel::create_placeholder_page(const QString& title) {
    QWidget* page = new QWidget(this);
    page->setStyleSheet("background-color: #1e1e1e;");
    QVBoxLayout* layout = new QVBoxLayout(page);

    QLabel* label = new QLabel(title + "\n\n(Coming Soon)", page);
    label->setAlignment(Qt::AlignCenter);
    label->setStyleSheet("color: #6f6f6f; font-size: 14px; font-weight: bold;");

    layout->addWidget(label);
    return page;
}

// === PUBLIC AI METHODS ===

void right_ai_panel::set_ai_state(const QString& state, const QString& message) {
    if (current_movie) {
        current_movie->stop();
        delete current_movie;
        current_movie = nullptr;
    }

    QString gif_path;

    if (state == "working") {
        gif_path = ":/axis_cleaner/assets/animations/hourglass.gif"; // Updated to your filename!
        status_text_label->setText(message.isEmpty() ? "Processing..." : message);
        status_text_label->setStyleSheet("color: #9b59ff; font-size: 11px; font-weight: bold; border: none;");
        progress_bar->show();
    }
    else if (state == "error") {
        gif_path = ":/axis_cleaner/assets/animations/error.gif";
        status_text_label->setText(message.isEmpty() ? "Error Occurred" : message);
        status_text_label->setStyleSheet("color: #ff5959; font-size: 11px; font-weight: bold; border: none;");
        progress_bar->hide();
    }
    else { // "idle"
        gif_path = ":/axis_cleaner/assets/animations/idle.gif";
        status_text_label->setText("AI Engine Idle");
        status_text_label->setStyleSheet("color: #8f8f8f; font-size: 11px; font-weight: bold; border: none;");
        progress_bar->hide();
        progress_bar->setValue(0);
    }

    QFile file(gif_path);
    if (file.exists()) {
        current_movie = new QMovie(gif_path, QByteArray(), this);
        current_movie->setScaledSize(QSize(72, 72));
        anim_label->setMovie(current_movie);
        current_movie->start();
    }
    else {
        anim_label->setText("[ GIF ]");
        anim_label->setStyleSheet("color: #3c3c3c; font-size: 10px; border: 1px solid #3c3c3c; border-radius: 8px;");
    }
}

void right_ai_panel::update_progress(int percentage) {
    progress_bar->setValue(percentage);
}

// === SLOTS ===

void right_ai_panel::on_nav_clicked(int index) {
    stacked_content->setCurrentIndex(index);
}