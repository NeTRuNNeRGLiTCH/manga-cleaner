#include "studio_tab.h"
#include <QFrame>
#include <QIcon>
#include <QFile>
#include <QPainter>


// ==========================================================
// Global Scrollbar Stylesheet
// ==========================================================
const QString STUDIO_SCROLLBAR_STYLE =
"QScrollBar:vertical { border: none; background: #1e1e1e; width: 6px; margin: 0px; }"
"QScrollBar::handle:vertical { background: #3c3c3c; border-radius: 3px; min-height: 20px; }"
"QScrollBar::handle:vertical:hover { background: #4c4c4c; }"
"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }";

const QString STUDIO_HIDDEN_SCROLLBAR =
"QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }"
"QScrollBar::handle:vertical { background: transparent; }";

// ==========================================================
// Studio Tab Controller
// ==========================================================
studio_tab::studio_tab(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);
    this->setStyleSheet("background-color: #1e1e1e;");
    this->installEventFilter(this);
    setup_ui();
}

void studio_tab::setup_ui() {
    QVBoxLayout* main_layout = new QVBoxLayout(this);
    main_layout->setContentsMargins(0, 0, 0, 0);
    main_layout->setSpacing(0);

    scroll_area = new QScrollArea(this);
    scroll_area->setWidgetResizable(true);
    scroll_area->setFrameShape(QFrame::NoFrame);
    scroll_area->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOn);
    scroll_area->setStyleSheet(STUDIO_HIDDEN_SCROLLBAR);

    scroll_content = new QWidget(scroll_area);
    scroll_content->setStyleSheet("background-color: #1e1e1e;");

    QVBoxLayout* content_layout = new QVBoxLayout(scroll_content);
    content_layout->setContentsMargins(16, 16, 16, 16);
    content_layout->setSpacing(20);

    // === 1: OCR DETECTION ===
    QVBoxLayout* ocr_layout = new QVBoxLayout();
    ocr_layout->setSpacing(12);

    ocr_layout->addWidget(create_section_header("OCR Detection"));


    btn_detect = new QPushButton("  Detect  ", this);
    btn_detect->setIcon(QIcon(recolor_svg(":/axis_cleaner/assets/icons/ocr.svg", "#10b981")));
    btn_detect->setIconSize(QSize(20, 20));
    btn_detect->setFixedHeight(48);
    btn_detect->setCursor(Qt::PointingHandCursor);
    btn_detect->setStyleSheet(
        "QPushButton { background-color: #064e3b; color: #10b981; font-weight: bold; font-size: 13px; border-radius: 6px; border: 1px solid #10b981; letter-spacing: 2px; }"
        "QPushButton:hover { background-color: #047857; }"
    );
    connect(btn_detect, &QPushButton::clicked, this, &studio_tab::run_detect_requested);

    ocr_layout->addWidget(btn_detect);
    ocr_layout->addWidget(create_description_text("Automatically detects text regions in manga pages and adds them to the mask."));

    content_layout->addLayout(ocr_layout);
    content_layout->addWidget(create_separator());

    // === 2: TRANSPARENCY SCANNER ===
    QVBoxLayout* transparency_layout = new QVBoxLayout();
    transparency_layout->setSpacing(12);

    transparency_layout->addWidget(create_section_header("Transparency Scanner"));

    btn_scan_transparency = new QPushButton("  Scan Transparent Pixels  ", this);
    btn_scan_transparency->setIcon(QIcon(recolor_svg(":/axis_cleaner/assets/icons/wand-sparkles.svg", "#fbbf24")));
    btn_scan_transparency->setIconSize(QSize(20, 20));
    btn_scan_transparency->setFixedHeight(48);
    btn_scan_transparency->setCursor(Qt::PointingHandCursor);
    btn_scan_transparency->setStyleSheet(
        "QPushButton { background-color: #422006; color: #fbbf24; font-weight: bold; font-size: 12px; border-radius: 6px; border: 1px solid #fbbf24; letter-spacing: 1px; }"
        "QPushButton:hover { background-color: #713f12; }"
    );
    connect(btn_scan_transparency, &QPushButton::clicked, this, &studio_tab::scan_transparency_requested);

    transparency_layout->addWidget(btn_scan_transparency);
    transparency_layout->addWidget(create_description_text("Selects transparent pixels so they can be reviewed, adjusted, and cleaned with the active mask workflow."));

    content_layout->addLayout(transparency_layout);
    content_layout->addWidget(create_separator());

    // === 3: CLEAN MASKED AREA ===
    QVBoxLayout* clean_layout = new QVBoxLayout();
    clean_layout->setSpacing(12);

    clean_layout->addWidget(create_section_header("Clean Masked Area"));

    btn_clean = new QPushButton("  Clean  ", this);
    btn_clean->setIcon(QIcon(recolor_svg(":/axis_cleaner/assets/icons/inpaint.svg", "#ffffff")));
    btn_clean->setIconSize(QSize(20, 20));
    btn_clean->setFixedHeight(48);
    btn_clean->setCursor(Qt::PointingHandCursor);
    btn_clean->setStyleSheet(
        "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f97316, stop:1 #ec4899); color: white; font-weight: bold; font-size: 13px; border-radius: 6px; border: none; letter-spacing: 2px; }"
        "QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fb923c, stop:1 #f472b6); }"
    );
    // Connect Clean Signal
    connect(btn_clean, &QPushButton::clicked, this, &studio_tab::run_clean_requested);

    clean_layout->addWidget(btn_clean);

    // === INPAINTING MODEL SELECTOR (small radio row under the Clean button) ===
    QWidget* engine_row = new QWidget(this);
    engine_row->setAttribute(Qt::WA_StyledBackground, true);
    engine_row->setStyleSheet("background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 6px;");

    QVBoxLayout* engine_layout = new QVBoxLayout(engine_row);
    engine_layout->setContentsMargins(10, 8, 10, 8);
    engine_layout->setSpacing(4);

    QLabel* engine_title = new QLabel("Inpainting Model", engine_row);
    engine_title->setStyleSheet("color: #8f8f8f; font-size: 10px; font-weight: bold; border: none; background: transparent;");
    engine_layout->addWidget(engine_title);

    QHBoxLayout* radio_row = new QHBoxLayout();
    radio_row->setContentsMargins(0, 0, 0, 0);
    radio_row->setSpacing(12);

    const QString radio_style =
        "QRadioButton { color: #e0e0e0; font-size: 11px; font-weight: bold; border: none; background: transparent; }"
        "QRadioButton:checked { color: #f97316; }"
        "QRadioButton::indicator { width: 12px; height: 12px; border-radius: 7px; border: 1px solid #6f6f6f; background: #1e1e1e; }"
        "QRadioButton::indicator:checked { background: #f97316; border: 1px solid #f97316; }";

    inpaint_group = new QButtonGroup(this);
    inpaint_group->setExclusive(true);

    radio_auto = new QRadioButton("Auto", engine_row);
    radio_lama = new QRadioButton("LaMa", engine_row);
    radio_moebius = new QRadioButton("Moebius", engine_row);

    for (QRadioButton* radio : { radio_auto, radio_lama, radio_moebius }) {
        radio->setStyleSheet(radio_style);
        radio->setCursor(Qt::PointingHandCursor);
    }

    radio_auto->setToolTip("Auto: LaMa for clean speech bubbles, Moebius when the mask is hard.");
    radio_lama->setToolTip("LaMa: fast single-pass inpainting. Best for simple speech bubbles.");
    radio_moebius->setToolTip("Moebius: high-quality 30-step latent diffusion. Best for complex masks.");

    inpaint_group->addButton(radio_auto, static_cast<int>(InpaintEngine::Auto));
    inpaint_group->addButton(radio_lama, static_cast<int>(InpaintEngine::LaMa));
    inpaint_group->addButton(radio_moebius, static_cast<int>(InpaintEngine::Moebius));

    radio_row->addWidget(radio_auto);
    radio_row->addWidget(radio_lama);
    radio_row->addWidget(radio_moebius);
    radio_row->addStretch();

    engine_layout->addLayout(radio_row);
    clean_layout->addWidget(engine_row);

    radio_auto->setChecked(true);
    connect(inpaint_group, &QButtonGroup::idClicked, this, &studio_tab::on_inpaint_engine_clicked);

    clean_layout->addWidget(create_description_text("AI fills masked areas with a clean background. Ensure masks are drawn or detected before running."));

    content_layout->addLayout(clean_layout);
    content_layout->addWidget(create_separator());

    // === STOP (kills whatever the pipeline is doing) ===
    btn_stop = new QPushButton("  Stop Current Task  ", this);
    btn_stop->setIcon(QIcon(recolor_svg(":/axis_cleaner/assets/icons/inpaint.svg", "#ffffff")));
    btn_stop->setIconSize(QSize(20, 20));
    btn_stop->setFixedHeight(34);
    btn_stop->setCursor(Qt::PointingHandCursor);
    btn_stop->setStyleSheet(
        "QPushButton { background-color: #ef4444; color: white; font-weight: bold; font-size: 12px; border-radius: 6px; border: none; letter-spacing: 1px; }"
        "QPushButton:hover { background-color: #dc2626; }"
    );
    connect(btn_stop, &QPushButton::clicked, this, &studio_tab::stop_requested);

    content_layout->addWidget(btn_stop);

    // === WORKFLOW INFO BOX ===
    QWidget* info_box = new QWidget(this);
    info_box->setStyleSheet("background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 6px;");
    QVBoxLayout* info_layout = new QVBoxLayout(info_box);
    info_layout->setContentsMargins(12, 12, 12, 12);
    info_layout->setSpacing(8);

    QLabel* info_title = new QLabel("Studio Workflow", info_box);
    info_title->setStyleSheet("color: #4a9eff; font-size: 11px; font-weight: bold; border: none;");

    QLabel* info_steps = new QLabel(
        "1. Load manga page\n"
        "2. Detect text regions or scan transparent pixels\n"
        "3. Review and refine the generated mask\n"
        "4. Clean masked areas with AI\n"
        "5. Export", info_box);
    info_steps->setStyleSheet("color: #8f8f8f; font-size: 10px; line-height: 1.5; border: none;");

    QFrame* info_line = create_separator();
    info_line->setParent(info_box);

    QLabel* info_pros = new QLabel("<span style='color: #9b59ff; font-weight: bold;'>✓ Pros:</span> Full manual control over each step, best quality results, ability to fine-tune generated masks before cleaning.", info_box);
    info_pros->setStyleSheet("color: #6f6f6f; font-size: 10px; border: none;");
    info_pros->setWordWrap(true);

    info_layout->addWidget(info_title);
    info_layout->addWidget(info_steps);
    info_layout->addWidget(info_line);
    info_layout->addWidget(info_pros);

    content_layout->addWidget(info_box);

    content_layout->addStretch();
    scroll_area->setWidget(scroll_content);
    main_layout->addWidget(scroll_area);
}

// === SCROLLBAR HOVER LOGIC ===
bool studio_tab::eventFilter(QObject* obj, QEvent* event) {
    if (obj == this) {
        if (event->type() == QEvent::Enter) scroll_area->setStyleSheet(STUDIO_SCROLLBAR_STYLE);
        else if (event->type() == QEvent::Leave) scroll_area->setStyleSheet(STUDIO_HIDDEN_SCROLLBAR);
    }
    return QWidget::eventFilter(obj, event);
}

// === INPAINTING MODEL SELECTOR ===
int studio_tab::selected_inpaint_engine() const {
    if (!inpaint_group) return static_cast<int>(InpaintEngine::Auto);
    QAbstractButton* checked = inpaint_group->checkedButton();
    if (!checked) return static_cast<int>(InpaintEngine::Auto);
    return inpaint_group->id(checked);
}

void studio_tab::set_inpaint_engine(int engine) {
    if (!inpaint_group) return;
    if (QAbstractButton* btn = inpaint_group->button(engine)) {
        btn->setChecked(true);
    }
}

void studio_tab::on_inpaint_engine_clicked(int id) {
    emit inpaint_engine_changed(id);
}

// === HELPER METHODS ===
QPixmap studio_tab::recolor_svg(const QString& path, const QString& hex_color) {
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

QLabel* studio_tab::create_section_header(const QString& title) {
    QLabel* label = new QLabel(title, this);
    label->setStyleSheet("color: #e0e0e0; font-size: 13px; font-weight: bold;");
    return label;
}

QLabel* studio_tab::create_description_text(const QString& text) {
    QLabel* label = new QLabel(text, this);
    label->setStyleSheet("color: #6f6f6f; font-size: 10px;");
    label->setWordWrap(true);
    return label;
}

QFrame* studio_tab::create_separator() {
    QFrame* line = new QFrame(this);
    line->setFrameShape(QFrame::HLine);
    line->setStyleSheet("color: #3c3c3c; margin: 4px 0px;");
    return line;
}