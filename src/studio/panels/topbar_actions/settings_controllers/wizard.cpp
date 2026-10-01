#include "wizard.h"
#include "src/storage/config_mgr.h"
#include <QFrame>
#include <QFileDialog>
#include <QStandardPaths>

// ==========================================================
// WizSetToggle Implementation
// ==========================================================
WizSetToggle::WizSetToggle(bool default_state, QWidget* parent) : QWidget(parent), m_checked(default_state) {
    setFixedSize(40, 22);
    setCursor(Qt::PointingHandCursor);
}

bool WizSetToggle::isChecked() const { return m_checked; }

void WizSetToggle::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::LeftButton) {
        m_checked = !m_checked;
        update();
        emit toggled(m_checked);
    }
}

void WizSetToggle::paintEvent(QPaintEvent*) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    QRectF rect(1, 1, width() - 2, height() - 2);

    if (m_checked) {
        p.setBrush(QColor("#8b5cf6")); // Violet-Indigo
        p.setPen(Qt::NoPen);
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2);
        p.setBrush(Qt::white);
        p.drawEllipse(rect.right() - rect.height() + 2, rect.y() + 2, rect.height() - 4, rect.height() - 4);
    }
    else {
        p.setBrush(QColor("#1e1e1e"));
        p.setPen(QPen(QColor("#3c3c3c"), 1.5));
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2);
        p.setBrush(QColor("#6f6f6f"));
        p.setPen(Qt::NoPen);
        p.drawEllipse(rect.x() + 2, rect.y() + 2, rect.height() - 4, rect.height() - 4);
    }
}

// ==========================================================
// Wizard Settings Controller Implementation
// ==========================================================
settings_wizard::settings_wizard(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);
    setup_ui();
}

void settings_wizard::setup_ui() {
    QVBoxLayout* master_layout = new QVBoxLayout(this);
    master_layout->setContentsMargins(0, 0, 0, 0);

    QScrollArea* scroll = new QScrollArea(this);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff); // No horizontal scroll
    scroll->setStyleSheet(
        "QScrollArea { background: transparent; }"
        "QScrollBar:vertical { border: none; background: #1e1e1e; width: 6px; }"
        "QScrollBar::handle:vertical { background: #3c3c3c; border-radius: 3px; }"
        "QScrollBar::handle:vertical:hover { background: #8b5cf6; }"
    );

    QWidget* content = new QWidget(scroll);
    QVBoxLayout* layout = new QVBoxLayout(content);
    layout->setContentsMargins(0, 0, 12, 24);
    layout->setSpacing(14);

    // === FETCH LIVE SETTINGS ===
    AppSettings settings = config_mgr::instance().get_settings();

    // --- SECTION 1: PIPELINE ---
    layout->addWidget(create_section_header("Batch Pipeline Modules", "#8b5cf6"));

    layout->addWidget(create_toggle_row(
        "1. Detect Text & SFX",
        "Use TextBPN++ to detect dialogue and sound effect runes automatically.",
        settings.wiz_run_bpn, toggle_run_bpn
    ));

    layout->addWidget(create_toggle_row(
        "2. AI Inpainting",
        "Clean the masked areas using Moebius Latent Suite.",
        settings.wiz_run_moebius, toggle_run_moebius
    ));

    layout->addWidget(create_separator());

    // --- SECTION 2: EXPORT & FORMATTING ---
    layout->addWidget(create_section_header("Export & Formatting", "#f43f5e"));

    layout->addWidget(create_path_row(
        "Batch Output Destination",
        "Where cleaned chapters will be saved.",
        settings.wiz_batch_export_path, line_batch_export, btn_batch_browse
    ));

    QStringList formats = { "JPG (Lossy)", "PNG (Lossless)", "WEBP (Optimized)", "PSD (Layered: Orig + Clean)" };
    layout->addWidget(create_combo_row(
        "Image Extension",
        "The file format for exported pages (PSD is default).",
        formats, settings.wiz_batch_format_idx, combo_batch_format
    ));

    QStringList error_handling = { "Skip Page & Continue", "Halt Entire Batch" };
    layout->addWidget(create_combo_row(
        "Error Handling",
        "Behavior if an image fails during batch execution.",
        error_handling, settings.wiz_error_handling_idx, combo_error_handling
    ));

    layout->addWidget(create_separator());

    // --- SECTION 3: ARCHIVING ---
    layout->addWidget(create_section_header("Post-Processing", "#10b981"));
    layout->addWidget(create_toggle_row(
        "Package to Archive",
        "Compress the cleaned chapter folder into a .zip archive automatically.",
        settings.wiz_create_zip, toggle_zip_archive
    ));

    layout->addStretch();
    scroll->setWidget(content);
    master_layout->addWidget(scroll);

    // ==========================================
    // LIVE SETTINGS BINDING (Auto-save)
    // ==========================================
    auto update_config = []() { return config_mgr::instance().get_settings(); };

    connect(toggle_run_bpn, &WizSetToggle::toggled, this, [=](bool checked) {
        AppSettings s = update_config(); s.wiz_run_bpn = checked; config_mgr::instance().update_settings(s);
        });

    connect(toggle_run_moebius, &WizSetToggle::toggled, this, [=](bool checked) {
        AppSettings s = update_config(); s.wiz_run_moebius = checked; config_mgr::instance().update_settings(s);
        });

    connect(combo_batch_format, &QComboBox::currentIndexChanged, this, [=](int idx) {
        AppSettings s = update_config(); s.wiz_batch_format_idx = idx; config_mgr::instance().update_settings(s);
        });

    connect(combo_error_handling, &QComboBox::currentIndexChanged, this, [=](int idx) {
        AppSettings s = update_config(); s.wiz_error_handling_idx = idx; config_mgr::instance().update_settings(s);
        });

    connect(toggle_zip_archive, &WizSetToggle::toggled, this, [=](bool checked) {
        AppSettings s = update_config(); s.wiz_create_zip = checked; config_mgr::instance().update_settings(s);
        });

    connect(line_batch_export, &QLineEdit::textChanged, this, [=](const QString& text) {
        AppSettings s = update_config(); s.wiz_batch_export_path = text; config_mgr::instance().update_settings(s);
        });

    connect(btn_batch_browse, &QPushButton::clicked, this, [this]() {
        QString dir = QFileDialog::getExistingDirectory(this, "Select Batch Output", line_batch_export->text());
        if (!dir.isEmpty()) line_batch_export->setText(dir);
        });
}

// === ROW GENERATORS ===

QLabel* settings_wizard::create_section_header(const QString& title, const QString& hex_color) {
    QLabel* lbl = new QLabel(title, this);
    lbl->setStyleSheet(QString("color: %1; font-size: 13px; font-weight: bold; margin-top: 8px; margin-bottom: 2px;").arg(hex_color));
    return lbl;
}

QFrame* settings_wizard::create_separator() {
    QFrame* line = new QFrame(this);
    line->setFrameShape(QFrame::HLine);
    line->setStyleSheet("color: #3c3c3c; margin: 4px 0px;");
    return line;
}

QWidget* settings_wizard::create_toggle_row(const QString& label_text, const QString& desc_text, bool is_checked, WizSetToggle*& toggle_ptr) {
    QWidget* row = new QWidget(this);
    QHBoxLayout* layout = new QHBoxLayout(row);
    layout->setContentsMargins(6, 4, 6, 4);

    QVBoxLayout* text_lay = new QVBoxLayout();
    text_lay->setSpacing(2);

    QLabel* title = new QLabel(label_text, row);
    title->setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold;");

    QLabel* desc = new QLabel(desc_text, row);
    desc->setStyleSheet("color: #8f8f8f; font-size: 10px;");
    desc->setWordWrap(true);

    text_lay->addWidget(title);
    text_lay->addWidget(desc);

    toggle_ptr = new WizSetToggle(is_checked, row);

    layout->addLayout(text_lay, 1);
    layout->addWidget(toggle_ptr, 0, Qt::AlignVCenter);
    return row;
}

QWidget* settings_wizard::create_combo_row(const QString& label_text, const QString& desc_text, const QStringList& options, int default_index, QComboBox*& combo_ptr) {
    QWidget* row = new QWidget(this);
    QHBoxLayout* layout = new QHBoxLayout(row);
    layout->setContentsMargins(6, 4, 6, 4);

    QVBoxLayout* text_lay = new QVBoxLayout();
    text_lay->setSpacing(2);

    QLabel* title = new QLabel(label_text, row);
    title->setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold;");

    QLabel* desc = new QLabel(desc_text, row);
    desc->setStyleSheet("color: #8f8f8f; font-size: 10px;");
    desc->setWordWrap(true);

    text_lay->addWidget(title);
    text_lay->addWidget(desc);

    combo_ptr = new QComboBox(row);
    combo_ptr->addItems(options);
    combo_ptr->setCurrentIndex(default_index);
    combo_ptr->setFixedWidth(205);
    combo_ptr->setStyleSheet(
        "QComboBox { background: #1e1e1e; color: #e0e0e0; border: 1px solid #3c3c3c; border-radius: 4px; padding: 5px 8px; font-size: 11px; }"
        "QComboBox::drop-down { border: none; width: 18px; }"
        "QComboBox QAbstractItemView { background-color: #1e1e1e; color: #e0e0e0; border: 1px solid #3c3c3c; selection-background-color: #3c3c3c; }"
    );

    layout->addLayout(text_lay, 1);
    layout->addWidget(combo_ptr, 0, Qt::AlignVCenter);
    return row;
}

QWidget* settings_wizard::create_path_row(const QString& label_text, const QString& desc_text, const QString& default_path, QLineEdit*& line_ptr, QPushButton*& btn_ptr) {
    QWidget* row = new QWidget(this);
    QHBoxLayout* layout = new QHBoxLayout(row);
    layout->setContentsMargins(6, 4, 6, 4);

    QVBoxLayout* text_lay = new QVBoxLayout();
    text_lay->setSpacing(2);

    QLabel* title = new QLabel(label_text, row);
    title->setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold;");

    QLabel* desc = new QLabel(desc_text, row);
    desc->setStyleSheet("color: #8f8f8f; font-size: 10px;");
    desc->setWordWrap(true);

    text_lay->addWidget(title);
    text_lay->addWidget(desc);

    line_ptr = new QLineEdit(default_path, row);
    line_ptr->setFixedWidth(150);
    line_ptr->setStyleSheet("background: #1e1e1e; color: #8f8f8f; border: 1px solid #3c3c3c; border-radius: 4px; padding: 5px; font-size: 11px;");

    btn_ptr = new QPushButton("Browse", row);
    btn_ptr->setCursor(Qt::PointingHandCursor);
    btn_ptr->setStyleSheet("QPushButton { background: #2b2b2b; color: #e0e0e0; border: 1px solid #3c3c3c; border-radius: 4px; padding: 5px 10px; font-size: 11px; } QPushButton:hover { background: #3c3c3c; }");

    layout->addLayout(text_lay, 1);
    layout->addWidget(line_ptr, 0, Qt::AlignVCenter);
    layout->addWidget(btn_ptr, 0, Qt::AlignVCenter);
    return row;
}