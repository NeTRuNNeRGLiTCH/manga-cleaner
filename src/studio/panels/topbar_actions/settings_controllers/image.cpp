#include "image.h"
#include "src/storage/config_mgr.h"
#include <QFrame>
#include <QFileDialog>
#include <QStandardPaths>

// ==========================================================
// ImageToggle Implementation
// ==========================================================
ImageToggle::ImageToggle(bool default_state, QWidget* parent) : QWidget(parent), m_checked(default_state) {
    setFixedSize(40, 22);
    setCursor(Qt::PointingHandCursor);
}
bool ImageToggle::isChecked() const { return m_checked; }
void ImageToggle::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::LeftButton) {
        m_checked = !m_checked;
        update();
        emit toggled(m_checked);
    }
}
void ImageToggle::paintEvent(QPaintEvent*) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    QRectF rect(1, 1, width() - 2, height() - 2);
    if (m_checked) {
        p.setBrush(QColor("#06b6d4"));
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
// Image Controller Implementation
// ==========================================================
settings_image::settings_image(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);
    setup_ui();
}

void settings_image::setup_ui() {
    QVBoxLayout* master_layout = new QVBoxLayout(this);
    master_layout->setContentsMargins(0, 0, 0, 0);

    QScrollArea* scroll = new QScrollArea(this);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff); // Eliminates horizontal scrollbar
    scroll->setStyleSheet(
        "QScrollArea { background: transparent; }"
        "QScrollBar:vertical { border: none; background: #1e1e1e; width: 6px; }"
        "QScrollBar::handle:vertical { background: #3c3c3c; border-radius: 3px; }"
        "QScrollBar::handle:vertical:hover { background: #06b6d4; }"
    );

    QWidget* content = new QWidget(scroll);
    QVBoxLayout* layout = new QVBoxLayout(content);
    layout->setContentsMargins(0, 0, 12, 24);
    layout->setSpacing(14);

    // === FETCH LIVE SETTINGS ===
    AppSettings settings = config_mgr::instance().get_settings();

    // --- SECTION 1: EXPORT ---
    layout->addWidget(create_section_header("Export Configuration", "#06b6d4"));

    QStringList formats = { "JPG (Lossy)", "PNG (Lossless)", "WEBP (Optimized)", "PSD (Layered: Orig + Clean)" };
    layout->addWidget(create_combo_row("Format", "Standard extension for saved images.", formats, settings.export_format_idx, combo_export_format));

    layout->addWidget(create_slider_row("Output Quality", "Controls compression for JPG/WEBP. Higher is better.", 10, 100, settings.jpg_quality, "%", lbl_jpg_quality, sldr_jpg_quality));

    layout->addWidget(create_separator());

    // --- SECTION 2: WORKSPACE ---
    layout->addWidget(create_section_header("Workspace Directories", "#3b82f6"));

    layout->addWidget(create_path_row("Import Root", "Initial folder for finding manga scans.", settings.import_path, line_import_path, btn_import_browse));
    layout->addWidget(create_path_row("Export Root", "Default location for cleaned pages.", settings.export_path, line_export_path, btn_export_browse));

    layout->addWidget(create_toggle_row("Relative Saving", "Saves cleaned files in a subfolder next to original source.", settings.save_in_src, toggle_save_in_src));

    layout->addStretch();
    scroll->setWidget(content);
    master_layout->addWidget(scroll);

    // ==========================================
    // LIVE SETTINGS BINDING
    // ==========================================
    auto update_config = []() { return config_mgr::instance().get_settings(); };

    connect(combo_export_format, &QComboBox::currentIndexChanged, this, [=](int idx) {
        AppSettings s = update_config(); s.export_format_idx = idx; config_mgr::instance().update_settings(s);
        });

    connect(sldr_jpg_quality, &QSlider::valueChanged, this, [=](int val) {
        AppSettings s = update_config(); s.jpg_quality = val; config_mgr::instance().update_settings(s);
        });

    connect(toggle_save_in_src, &ImageToggle::toggled, this, [=](bool checked) {
        AppSettings s = update_config(); s.save_in_src = checked; config_mgr::instance().update_settings(s);
        });

    connect(line_import_path, &QLineEdit::textChanged, this, [=](const QString& text) {
        AppSettings s = update_config(); s.import_path = text; config_mgr::instance().update_settings(s);
        });

    connect(line_export_path, &QLineEdit::textChanged, this, [=](const QString& text) {
        AppSettings s = update_config(); s.export_path = text; config_mgr::instance().update_settings(s);
        });

    connect(btn_import_browse, &QPushButton::clicked, this, [this]() {
        QString dir = QFileDialog::getExistingDirectory(this, "Import Root", line_import_path->text());
        if (!dir.isEmpty()) line_import_path->setText(dir);
        });

    connect(btn_export_browse, &QPushButton::clicked, this, [this]() {
        QString dir = QFileDialog::getExistingDirectory(this, "Export Root", line_export_path->text());
        if (!dir.isEmpty()) line_export_path->setText(dir);
        });
}

// === ROW GENERATORS ===

QLabel* settings_image::create_section_header(const QString& title, const QString& hex_color) {
    QLabel* lbl = new QLabel(title, this);
    lbl->setStyleSheet(QString("color: %1; font-size: 13px; font-weight: bold; margin-top: 8px; margin-bottom: 2px;").arg(hex_color));
    return lbl;
}

QFrame* settings_image::create_separator() {
    QFrame* line = new QFrame(this);
    line->setFrameShape(QFrame::HLine);
    line->setStyleSheet("color: #3c3c3c; margin: 4px 0px;");
    return line;
}

QWidget* settings_image::create_toggle_row(const QString& label_text, const QString& desc_text, bool is_checked, ImageToggle*& toggle_ptr) {
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

    toggle_ptr = new ImageToggle(is_checked, row);

    layout->addLayout(text_lay, 1);
    layout->addWidget(toggle_ptr, 0, Qt::AlignVCenter);
    return row;
}

QWidget* settings_image::create_combo_row(const QString& label_text, const QString& desc_text, const QStringList& options, int default_index, QComboBox*& combo_ptr) {
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

QWidget* settings_image::create_slider_row(const QString& label_text, const QString& desc_text, int min, int max, int default_val, const QString& suffix, QLabel*& val_label_ptr, QSlider*& slider_ptr) {
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

    slider_ptr = new QSlider(Qt::Horizontal, row);
    slider_ptr->setRange(min, max);
    slider_ptr->setValue(default_val);
    slider_ptr->setFixedWidth(110);
    slider_ptr->setCursor(Qt::PointingHandCursor);
    slider_ptr->setStyleSheet("QSlider::groove:horizontal { background: #1e1e1e; height: 6px; border-radius: 3px; } QSlider::handle:horizontal { background: #06b6d4; width: 14px; margin: -4px 0; border-radius: 7px; }");

    val_label_ptr = new QLabel(QString::number(default_val) + suffix, row);
    val_label_ptr->setStyleSheet("color: #e0e0e0; font-weight: bold; font-family: monospace; font-size: 11px;");
    val_label_ptr->setFixedWidth(40);
    val_label_ptr->setAlignment(Qt::AlignRight | Qt::AlignVCenter);

    connect(slider_ptr, &QSlider::valueChanged, this, [=](int val) { val_label_ptr->setText(QString::number(val) + suffix); });

    layout->addLayout(text_lay, 1);
    layout->addWidget(slider_ptr, 0, Qt::AlignVCenter);
    layout->addWidget(val_label_ptr, 0, Qt::AlignVCenter);
    return row;
}

QWidget* settings_image::create_path_row(const QString& label_text, const QString& desc_text, const QString& default_path, QLineEdit*& line_ptr, QPushButton*& btn_ptr) {
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