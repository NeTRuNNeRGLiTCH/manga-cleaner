#include "models.h"
#include "src/storage/config_mgr.h"
#include "src/engine/trt_arch_detector.h"
#include <QFrame>
#include <QFileInfo>
#include <QCoreApplication>
#include <iterator>

settings_models::settings_models(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);
    this->setStyleSheet("background-color: transparent;");
    setup_ui();
}

void settings_models::setup_ui() {
    QVBoxLayout* master_layout = new QVBoxLayout(this);
    master_layout->setContentsMargins(0, 0, 0, 0);
    master_layout->setSpacing(0);

    QScrollArea* scroll = new QScrollArea(this);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    scroll->setStyleSheet(
        "QScrollArea { background-color: transparent; }"
        "QScrollBar:vertical { border: none; background: #1e1e1e; width: 6px; }"
        "QScrollBar::handle:vertical { background: #3c3c3c; border-radius: 3px; min-height: 30px; }"
        "QScrollBar::handle:vertical:hover { background: #6f6f6f; }"
    );

    QWidget* content = new QWidget(scroll);
    content->setStyleSheet("background-color: transparent;");
    QVBoxLayout* layout = new QVBoxLayout(content);
    layout->setContentsMargins(0, 0, 12, 24);
    layout->setSpacing(14);

    // === FETCH LIVE SETTINGS FROM BACKEND ===
    AppSettings settings = config_mgr::instance().get_settings();

    // ==========================================
    // GROUP 1: MODEL DISCOVERY & ENGINE SCANNER
    // ==========================================
    layout->addWidget(create_section_header("Engine Model Scanner (Hardware Scan)", "#10b981"));

    // Header container with Scan button & Architecture Info
    QWidget* scan_box = new QWidget(this);
    scan_box->setStyleSheet("background-color: #242424; border: 1px solid #3c3c3c; border-radius: 6px; padding: 6px;");
    QVBoxLayout* scan_box_layout = new QVBoxLayout(scan_box);
    scan_box_layout->setContentsMargins(10, 10, 10, 10);
    scan_box_layout->setSpacing(8);

    QHBoxLayout* btn_row = new QHBoxLayout();
    btn_scan_models = new QPushButton("  Scan Models  ", scan_box);
    btn_scan_models->setFixedHeight(36);
    btn_scan_models->setCursor(Qt::PointingHandCursor);
    btn_scan_models->setStyleSheet(
        "QPushButton { background-color: #064e3b; color: #10b981; font-weight: bold; font-size: 12px; border-radius: 6px; border: 1px solid #10b981; padding: 4px 16px; }"
        "QPushButton:hover { background-color: #047857; }"
    );
    connect(btn_scan_models, &QPushButton::clicked, this, &settings_models::scan_model_availability);

    lbl_availability_arch = new QLabel("Scanning microarchitecture...", scan_box);
    lbl_availability_arch->setStyleSheet("color: #e0e0e0; font-size: 11px; font-weight: bold; border: none;");

    btn_row->addWidget(btn_scan_models);
    btn_row->addSpacing(10);
    btn_row->addWidget(lbl_availability_arch, 1);
    scan_box_layout->addLayout(btn_row);

    lbl_availability_summary = new QLabel("Ready to scan models.", scan_box);
    lbl_availability_summary->setStyleSheet("color: #8f8f8f; font-size: 10px; border: none;");
    scan_box_layout->addWidget(lbl_availability_summary);

    layout->addWidget(scan_box);

    // --- PART A: SEGMENTATION MODELS (1 Model) ---
    layout->addWidget(create_section_header("1. Segmentation Models (1 Model)", "#4a9eff"));
    layout->addWidget(create_model_card("TextBPN++ TensorRT", "Full-image text & SFX detection with vertical slicing.", lbl_segmentation_status));

    // --- PART B: INPAINTING MODELS (2 Models) ---
    layout->addWidget(create_section_header("2. Inpainting Models (2 Models)", "#ec4899"));
    layout->addWidget(create_model_card("Moebius Latent Suite", "High-fidelity DDIM latent diffusion inpainting (512x512).", lbl_moebius_status));
    layout->addWidget(create_model_card("LaMa Fast Inpainter", "Lightweight large-mask inpainting for rapid chapter passes.", lbl_lama_status));

    layout->addWidget(create_separator());

    // ==========================================
    // GROUP 2: TextBPN++ Fine-Tuning
    // ==========================================
    layout->addWidget(create_section_header("TextBPN++ Parameters", "#4a9eff"));

    layout->addWidget(create_slider_row(
        "Candidate Threshold (cls)",
        "Primary confidence required to flag potential text or sound effects.",
        10, 99, settings.bpn_prob, "%", lbl_bpn_prob, sldr_bpn_prob
    ));

    layout->addWidget(create_slider_row(
        "Core Seed Threshold (dis)",
        "Topological seed threshold to filter out background false positives.",
        10, 99, settings.bpn_core, "%", lbl_bpn_core, sldr_bpn_core
    ));

    layout->addWidget(create_spinbox_row(
        "Extra Mask Padding",
        "Additional dilation on top of the guaranteed 8px text coverage (0 = default).",
        0, 32, settings.bpn_expand, " px", spin_bpn_expand
    ));

    layout->addWidget(create_separator());

    // ==========================================
    // GROUP 3: Moebius Latent Inpainting Suite
    // ==========================================
    layout->addWidget(create_section_header("Moebius Latent Inpainting (512x512 DDIM)", "#ec4899"));

    layout->addWidget(create_spinbox_row(
        "DDIM Sampling Steps",
        "Diffusion iterations per 512x512 tile (Cheatsheet baseline: 30).",
        10, 50, settings.moebius_steps, " steps", spin_moebius_steps
    ));

    layout->addStretch();
    scroll->setWidget(content);
    master_layout->addWidget(scroll);

    // ==========================================
    // LIVE SETTINGS BINDING (Auto-save)
    // ==========================================
    connect(sldr_bpn_prob, &QSlider::valueChanged, this, [](int val) {
        AppSettings s = config_mgr::instance().get_settings();
        s.bpn_prob = val;
        config_mgr::instance().update_settings(s);
    });

    connect(sldr_bpn_core, &QSlider::valueChanged, this, [](int val) {
        AppSettings s = config_mgr::instance().get_settings();
        s.bpn_core = val;
        config_mgr::instance().update_settings(s);
    });

    connect(spin_bpn_expand, &QSpinBox::valueChanged, this, [](int val) {
        AppSettings s = config_mgr::instance().get_settings();
        s.bpn_expand = val;
        config_mgr::instance().update_settings(s);
    });

    connect(spin_moebius_steps, &QSpinBox::valueChanged, this, [](int val) {
        AppSettings s = config_mgr::instance().get_settings();
        s.moebius_steps = val;
        config_mgr::instance().update_settings(s);
    });

    // Populate initial model status
    scan_model_availability();
}

void settings_models::scan_model_availability() {
    trt_arch_detector::instance().refresh();
    QString arch_name = trt_arch_detector::instance().get_arch_name();
    int sm = trt_arch_detector::instance().get_compute_capability();

    lbl_availability_arch->setText(QString("GPU Microarchitecture: %1 (SM %2)").arg(arch_name).arg(sm));

    // "Ready" only when the pack for this GPU's own folder is present; a hit from a
    // different pack is a fallback and is reported as such instead of a green light.
    auto check_engine = [](const QString& base, bool& fallback) -> bool {
        const QString path = trt_arch_detector::instance().get_engine_path(base);
        if (!QFileInfo::exists(path)) return false;
        fallback = !path.contains("/" + trt_arch_detector::instance().get_arch_folder() + "/");
        return true;
    };

    auto set_status = [](QLabel* label, bool ok, bool fallback, const QString& name) {
        if (!label) return;
        if (ok && !fallback) {
            label->setText("🟢 " + name + " - Ready");
            label->setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold; border: none; background: transparent;");
        } else if (ok) {
            label->setText("🟡 " + name + " - Fallback pack");
            label->setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: bold; border: none; background: transparent;");
        } else {
            label->setText("🔴 " + name + " - Missing");
            label->setStyleSheet("color: #f87171; font-size: 11px; font-weight: bold; border: none; background: transparent;");
        }
    };

    struct EngineCheck { QLabel* label; QString base; QString name; };
    const EngineCheck checks[] = {
        { lbl_segmentation_status, "segmentation",  "TextBPN++" },
        { lbl_moebius_status,     "moebius_unet",  "Moebius Latent DDIM" },
        { lbl_lama_status,        "lama",          "LaMa Engine" },
    };

    int ready_count = 0;
    const int model_count = static_cast<int>(std::size(checks));
    for (const EngineCheck& check : checks) {
        bool fallback = false;
        const bool ok = check_engine(check.base, fallback);
        if (ok && !fallback) ++ready_count;
        set_status(check.label, ok, fallback, check.name);
    }

    lbl_availability_summary->setText(QString("Hardware Scan: %1/%2 models ready for the %3 pack.")
        .arg(ready_count)
        .arg(model_count)
        .arg(trt_arch_detector::instance().get_arch_folder()));
}

QWidget* settings_models::create_model_card(const QString& title, const QString& desc, QLabel*& status_label) {
    QWidget* card = new QWidget(this);
    card->setStyleSheet("background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 6px;");
    QHBoxLayout* layout = new QHBoxLayout(card);
    layout->setContentsMargins(12, 10, 12, 10);
    layout->setSpacing(8);

    QVBoxLayout* text_layout = new QVBoxLayout();
    text_layout->setSpacing(2);

    QLabel* title_lbl = new QLabel(title, card);
    title_lbl->setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold; border: none; background: transparent;");

    QLabel* desc_lbl = new QLabel(desc, card);
    desc_lbl->setStyleSheet("color: #8f8f8f; font-size: 10px; border: none; background: transparent;");
    desc_lbl->setWordWrap(true);

    text_layout->addWidget(title_lbl);
    text_layout->addWidget(desc_lbl);

    status_label = new QLabel("Scanning...", card);
    status_label->setStyleSheet("color: #8f8f8f; font-size: 11px; font-weight: bold; border: none; background: transparent;");
    status_label->setAlignment(Qt::AlignRight | Qt::AlignVCenter);

    layout->addLayout(text_layout, 1);
    layout->addWidget(status_label, 0, Qt::AlignVCenter);

    return card;
}

QLabel* settings_models::create_section_header(const QString& title, const QString& hex_color) {
    QLabel* lbl = new QLabel(title, this);
    lbl->setStyleSheet(QString("color: %1; font-size: 13px; font-weight: bold; margin-top: 8px; margin-bottom: 2px;").arg(hex_color));
    return lbl;
}

QFrame* settings_models::create_separator() {
    QFrame* line = new QFrame(this);
    line->setFrameShape(QFrame::HLine);
    line->setStyleSheet("color: #3c3c3c; margin: 4px 0px;");
    return line;
}

QWidget* settings_models::create_slider_row(const QString& label_text, const QString& desc_text, int min, int max, int default_val, const QString& suffix, QLabel*& val_label_ptr, QSlider*& slider_ptr) {
    QWidget* row = new QWidget(this);
    QHBoxLayout* layout = new QHBoxLayout(row);
    layout->setContentsMargins(6, 4, 6, 4);

    QVBoxLayout* text_layout = new QVBoxLayout();
    text_layout->setSpacing(2);

    QLabel* title = new QLabel(label_text, row);
    title->setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold;");

    QLabel* desc = new QLabel(desc_text, row);
    desc->setStyleSheet("color: #8f8f8f; font-size: 10px;");
    desc->setWordWrap(true);

    text_layout->addWidget(title);
    text_layout->addWidget(desc);

    slider_ptr = new QSlider(Qt::Horizontal, row);
    slider_ptr->setRange(min, max);
    slider_ptr->setValue(default_val);
    slider_ptr->setFixedWidth(110);
    slider_ptr->setCursor(Qt::PointingHandCursor);
    slider_ptr->setStyleSheet(
        "QSlider::groove:horizontal { background: #1e1e1e; height: 6px; border-radius: 3px; }"
        "QSlider::handle:horizontal { background: #e0e0e0; width: 14px; margin: -4px 0; border-radius: 7px; }"
        "QSlider::handle:horizontal:hover { background: #ffffff; }"
    );

    val_label_ptr = new QLabel(QString::number(default_val) + suffix, row);
    val_label_ptr->setStyleSheet("color: #e0e0e0; font-weight: bold; font-family: monospace; font-size: 11px;");
    val_label_ptr->setFixedWidth(40);
    val_label_ptr->setAlignment(Qt::AlignRight | Qt::AlignVCenter);

    connect(slider_ptr, &QSlider::valueChanged, this, [=](int val) {
        val_label_ptr->setText(QString::number(val) + suffix);
    });

    layout->addLayout(text_layout, 1);
    layout->addWidget(slider_ptr, 0, Qt::AlignVCenter);
    layout->addWidget(val_label_ptr, 0, Qt::AlignVCenter);

    return row;
}

QWidget* settings_models::create_spinbox_row(const QString& label_text, const QString& desc_text, int min, int max, int default_val, const QString& suffix, QSpinBox*& spin_ptr) {
    QWidget* row = new QWidget(this);
    QHBoxLayout* layout = new QHBoxLayout(row);
    layout->setContentsMargins(6, 4, 6, 4);

    QVBoxLayout* text_layout = new QVBoxLayout();
    text_layout->setSpacing(2);

    QLabel* title = new QLabel(label_text, row);
    title->setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold;");

    QLabel* desc = new QLabel(desc_text, row);
    desc->setStyleSheet("color: #8f8f8f; font-size: 10px;");
    desc->setWordWrap(true);

    text_layout->addWidget(title);
    text_layout->addWidget(desc);

    spin_ptr = new QSpinBox(row);
    spin_ptr->setRange(min, max);
    spin_ptr->setValue(default_val);
    spin_ptr->setSuffix(suffix);
    spin_ptr->setFixedWidth(110);
    spin_ptr->setCursor(Qt::PointingHandCursor);
    spin_ptr->setStyleSheet(
        "QSpinBox { background-color: #1e1e1e; color: #e0e0e0; border: 1px solid #3c3c3c; border-radius: 4px; padding: 5px 8px; font-size: 11px; }"
        "QSpinBox::up-button, QSpinBox::down-button { background: #2b2b2b; width: 18px; border-left: 1px solid #3c3c3c; }"
        "QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #3c3c3c; }"
    );

    layout->addLayout(text_layout, 1);
    layout->addWidget(spin_ptr, 0, Qt::AlignVCenter);

    return row;
}