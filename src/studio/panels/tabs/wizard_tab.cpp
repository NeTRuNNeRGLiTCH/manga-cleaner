#include "wizard_tab.h"
#include <QFrame>
#include <QIcon>
#include <QFile>
#include <QTimer>

// ==========================================================
// WizardToggle Implementation 
// ==========================================================
WizardToggle::WizardToggle(bool default_state, QWidget* parent) : QWidget(parent), m_checked(default_state) {
    setFixedSize(36, 20);
    setCursor(Qt::PointingHandCursor);
}

bool WizardToggle::isChecked() const { return m_checked; }

void WizardToggle::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::LeftButton) {
        m_checked = !m_checked;
        update();
        emit toggled(m_checked);
    }
}

void WizardToggle::paintEvent(QPaintEvent*) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);

    QRectF rect(1, 1, width() - 2, height() - 2);

    if (m_checked) {
        p.setBrush(QColor("#9b59ff"));
        p.setPen(Qt::NoPen);
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2);
        p.setBrush(Qt::white);
        p.drawEllipse(rect.right() - rect.height() + 2, rect.y() + 2, rect.height() - 4, rect.height() - 4);
    }
    else {
        p.setBrush(QColor("#1e1e1e"));
        p.setPen(QPen(QColor("#3c3c3c"), 1.5));
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2);
        p.setBrush(QColor("#8f8f8f"));
        p.setPen(Qt::NoPen);
        p.drawEllipse(rect.x() + 2, rect.y() + 2, rect.height() - 4, rect.height() - 4);
    }
}

// ==========================================================
// Global Scrollbar Stylesheet
// ==========================================================
const QString WIZ_SCROLLBAR_STYLE =
"QScrollBar:vertical { border: none; background: #1e1e1e; width: 8px; margin: 0px; }"
"QScrollBar::handle:vertical { background: #3c3c3c; border-radius: 4px; min-height: 20px; }"
"QScrollBar::handle:vertical:hover { background: #4c4c4c; }"
"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }";

wizard_tab::wizard_tab(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);
    this->setStyleSheet("background-color: #1e1e1e;");
    this->installEventFilter(this);
    setup_ui();
}

void wizard_tab::setup_ui() {
    QVBoxLayout* main_layout = new QVBoxLayout(this);
    main_layout->setContentsMargins(0, 0, 0, 0);
    main_layout->setSpacing(0);

    scroll_area = new QScrollArea(this);
    scroll_area->setWidgetResizable(true);
    scroll_area->setFrameShape(QFrame::NoFrame);
    scroll_area->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    scroll_area->setStyleSheet(WIZ_SCROLLBAR_STYLE);

    scroll_content = new QWidget(scroll_area);
    scroll_content->setStyleSheet("background-color: #1e1e1e;");

    QVBoxLayout* content_layout = new QVBoxLayout(scroll_content);
    content_layout->setContentsMargins(16, 16, 16, 16);
    content_layout->setSpacing(20);

    // === GROUP 1: WIZARD SETTINGS ===
    QVBoxLayout* settings_layout = new QVBoxLayout();
    settings_layout->setSpacing(8);
    settings_layout->addWidget(create_section_header("Wizard Settings"));

    // Transparency Scanner Switch Container
    QWidget* transparency_container = new QWidget(this);
    transparency_container->setStyleSheet("background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 6px;");
    transparency_container->setFixedHeight(44);
    QHBoxLayout* trans_layout = new QHBoxLayout(transparency_container);
    trans_layout->setContentsMargins(12, 0, 12, 0);
    QLabel* trans_label = new QLabel("Scan Transparency", transparency_container);
    trans_label->setStyleSheet("color: #e0e0e0; font-size: 11px; font-weight: bold; border: none;");
    toggle_scan_transparency = new WizardToggle(false, transparency_container);
    trans_layout->addWidget(trans_label);
    trans_layout->addStretch();
    trans_layout->addWidget(toggle_scan_transparency);

    // Connect Toggles
    connect(toggle_scan_transparency, &WizardToggle::toggled, this, &wizard_tab::on_scan_transparency_toggled);

    settings_layout->addWidget(transparency_container);

    content_layout->addLayout(settings_layout);
    content_layout->addWidget(create_separator());

    // === GROUP 2: ACTIONS ===
    QVBoxLayout* actions_layout = new QVBoxLayout();
    actions_layout->setSpacing(12);

    btn_run = new QPushButton("  Run Wizard  ", this);
    btn_run->setIcon(QIcon(recolor_svg(":/axis_cleaner/assets/icons/wizard.svg", "#ffffff")));
    btn_run->setIconSize(QSize(20, 20));
    btn_run->setFixedHeight(48);
    btn_run->setCursor(Qt::PointingHandCursor);
    btn_run->setStyleSheet(
        "QPushButton { "
        "   background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgb(22, 166, 214), stop:1 rgb(151, 53, 252)); "
        "   color: #ffffff; font-weight: bold; font-size: 14px; border-radius: 6px; border: none; letter-spacing: 1px; "
        "}"
        "QPushButton:hover { "
        "   background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgb(42, 186, 234), stop:1 rgb(171, 73, 255)); "
        "}"
    );
    // Link Run Button
    connect(btn_run, &QPushButton::clicked, this, [this]() {
        emit run_wizard_requested(toggle_scan_transparency->isChecked());
    });

    btn_stop = new QPushButton("  Stop Wizard  ", this);
    btn_stop->setIcon(QIcon(recolor_svg(":/axis_cleaner/assets/icons/square.svg", "#ffffff")));
    btn_stop->setIconSize(QSize(18, 18));
    btn_stop->setFixedHeight(40);
    btn_stop->setCursor(Qt::PointingHandCursor);
    btn_stop->setStyleSheet(
        "QPushButton { background-color: #ef4444; color: #ffffff; font-weight: bold; font-size: 12px; border-radius: 6px; border: none; letter-spacing: 1px; }"
        "QPushButton:hover { background-color: #dc2626; }"
    );
    // Link Stop Button
    connect(btn_stop, &QPushButton::clicked, this, &wizard_tab::stop_wizard_requested);

    actions_layout->addWidget(btn_run);
    actions_layout->addWidget(btn_stop);

    content_layout->addLayout(actions_layout);
    content_layout->addWidget(create_separator());

    // === GROUP 3: STATUS & WORKFLOW BOXES ===
    QWidget* status_box = new QWidget(this);
    status_box->setStyleSheet("background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 6px;");
    QVBoxLayout* status_layout = new QVBoxLayout(status_box);
    status_layout->setContentsMargins(12, 12, 12, 12);
    status_layout->setSpacing(8);

    QLabel* status_title = new QLabel("Wizard Status", status_box);
    status_title->setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold; border: none;");
    status_layout->addWidget(status_title);

    status_layout->addWidget(create_status_row("Total Images:", val_total));
    status_layout->addWidget(create_status_row("Processed:", val_processed));
    status_layout->addWidget(create_status_row("Failed:", val_failed));
    status_layout->addWidget(create_status_row("Remaining:", val_remaining));
    status_layout->addWidget(create_status_row("Current Task:", val_task));
    status_layout->addWidget(create_status_row("Transparency Scan:", val_transparency_scan));

    val_total->setText("0");
    val_processed->setText("0");
    val_failed->setText("0");
    val_remaining->setText("0");
    val_task->setText("Idle");
    val_transparency_scan->setText("No");

    // Workflow Info Box
    QWidget* info_box = new QWidget(this);
    info_box->setStyleSheet("background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 6px;");
    QVBoxLayout* info_layout = new QVBoxLayout(info_box);
    info_layout->setContentsMargins(12, 12, 12, 12);
    info_layout->setSpacing(8);

    QLabel* info_title = new QLabel("Wizard Workflow", info_box);
    info_title->setStyleSheet("color: #4a9eff; font-size: 12px; font-weight: bold; border: none;");

    QLabel* info_steps = new QLabel(
        "1. Load multiple manga pages\n"
        "2. Configure wizard settings\n"
        "3. Run automated processing\n"
        "4. All images cleaned automatically\n"
        "5. Export all results at once", info_box);
    info_steps->setStyleSheet("color: #8f8f8f; font-size: 11px; line-height: 1.5; border: none;");

    QFrame* info_line = create_separator();
    info_line->setParent(info_box);

    QLabel* info_pros = new QLabel("<span style='color: #4a9eff; font-weight: bold;'>✓ Pros:</span> Extremely fast for large volumes, consistent results across all pages, hands-free automation, ideal for full manga chapters.", info_box);
    info_pros->setStyleSheet("color: #6f6f6f; font-size: 11px; border: none;");
    info_pros->setWordWrap(true);

    info_layout->addWidget(info_title);
    info_layout->addWidget(info_steps);
    info_layout->addWidget(info_line);
    info_layout->addWidget(info_pros);

    content_layout->addWidget(status_box);
    content_layout->addWidget(info_box);

    content_layout->addStretch();
    scroll_area->setWidget(scroll_content);
    main_layout->addWidget(scroll_area);
}

// === EVENT FILTERS ===
bool wizard_tab::eventFilter(QObject* obj, QEvent* event) {
    if (obj == this) {
        if (event->type() == QEvent::Enter) scroll_area->setVerticalScrollBarPolicy(Qt::ScrollBarAsNeeded);
        else if (event->type() == QEvent::Leave) scroll_area->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    }
    return QWidget::eventFilter(obj, event);
}

// === SLOTS ===
void wizard_tab::on_scan_transparency_toggled(bool checked) {
    if (val_transparency_scan) {
        val_transparency_scan->setText(checked ? "Yes" : "No");
    }
}

// === PUBLIC DATA UPDATERS ===
void wizard_tab::update_status_total(int total) { val_total->setText(QString::number(total)); }
void wizard_tab::update_status_processed(int processed) {
    val_processed->setText(QString::number(processed));
    const int total = val_total->text().toInt();
    val_remaining->setText(QString::number(qMax(0, total - processed)));
}
void wizard_tab::update_status_failed(int failed) { val_failed->setText(QString::number(failed)); }
void wizard_tab::update_status_task(const QString& task) { val_task->setText(task); }

// === HELPER METHODS ===
QWidget* wizard_tab::create_status_row(const QString& label_text, QLabel*& value_ptr) {
    QWidget* row = new QWidget(this);
    row->setStyleSheet("border: none; background: transparent;");
    QHBoxLayout* layout = new QHBoxLayout(row);
    layout->setContentsMargins(0, 0, 0, 0);

    QLabel* title = new QLabel(label_text, row);
    title->setStyleSheet("color: #8f8f8f; font-size: 11px;");

    value_ptr = new QLabel("", row);
    value_ptr->setStyleSheet("color: #e0e0e0; font-size: 11px; font-weight: bold;");

    layout->addWidget(title);
    layout->addStretch();
    layout->addWidget(value_ptr);
    return row;
}

QPixmap wizard_tab::recolor_svg(const QString& path, const QString& hex_color) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) return QPixmap();
    QString svg_content = file.readAll();
    file.close();
    svg_content.replace("\"currentColor\"", QString("\"%1\"").arg(hex_color));
    svg_content.replace("\"#e0e0e0\"", QString("\"%1\"").arg(hex_color));
    svg_content.replace("\"#000000\"", QString("\"%1\"").arg(hex_color));
    QPixmap pixmap;
    pixmap.loadFromData(svg_content.toUtf8(), "SVG");
    return pixmap;
}

QLabel* wizard_tab::create_section_header(const QString& title) {
    QLabel* label = new QLabel(title, this);
    label->setStyleSheet("color: #e0e0e0; font-size: 13px; font-weight: bold;");
    return label;
}

QFrame* wizard_tab::create_separator() {
    QFrame* line = new QFrame(this);
    line->setFrameShape(QFrame::HLine);
    line->setStyleSheet("color: #3c3c3c; margin: 4px 0px;");
    return line;
}