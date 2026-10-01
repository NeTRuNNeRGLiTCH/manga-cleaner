#include "system.h"
#include "src/storage/config_mgr.h"
#include "src/core/hardware/system_scanner.h"
#include "src/engine/trt_arch_detector.h"
#include <QFrame>

settings_system::settings_system(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);
    this->setStyleSheet("background-color: transparent;");
    setup_ui();
}

void settings_system::setup_ui() {
    QVBoxLayout* master_layout = new QVBoxLayout(this);
    master_layout->setContentsMargins(0, 0, 0, 0);
    master_layout->setSpacing(0);

    QScrollArea* scroll = new QScrollArea(this);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff); // Eliminates horizontal scrollbar
    scroll->setStyleSheet(
        "QScrollArea { background-color: transparent; }"
        "QScrollBar:vertical { border: none; background: #1e1e1e; width: 6px; }"
        "QScrollBar::handle:vertical { background: #3c3c3c; border-radius: 3px; min-height: 30px; }"
        "QScrollBar::handle:vertical:hover { background: #4ade80; }"
    );

    QWidget* content = new QWidget(scroll);
    content->setStyleSheet("background-color: transparent;");
    QVBoxLayout* layout = new QVBoxLayout(content);
    layout->setContentsMargins(0, 0, 12, 24);
    layout->setSpacing(14);

    // === FETCH LIVE SETTINGS & HARDWARE ===
    AppSettings settings = config_mgr::instance().get_settings();
    ComputeDevice gpu = system_scanner::get_best_device();

    // ==========================================
    // GROUP 1: Model Persistence (Keep Alive)
    // ==========================================
    layout->addWidget(create_section_header("Model Persistence (Lifecycle Management)", "#9b59ff"));

    QStringList persist_options = {
        "Keep Loaded (Pinned in VRAM)",
        "Unload Immediately (Saves VRAM)",
        "Dynamic (Unload after 60s)"
    };

    layout->addWidget(create_combo_row(
        "TextBPN++ (Detection)",
        "Keep detector in VRAM between operations.",
        persist_options, settings.persist_bpn, combo_persist_bpn
    ));

    layout->addWidget(create_combo_row(
        "Moebius (Inpainting)",
        "Keep 3-stage latent suite in VRAM between cleanings.",
        persist_options, settings.persist_moebius, combo_persist_moebius
    ));    layout->addWidget(create_combo_row(
        "LaMa (Fast Inpainting)",
        "Single-pass FFC inpainter used for simple bubbles.",
        persist_options, settings.persist_lama, combo_persist_lama
    ));

    layout->addWidget(create_separator());

    // ==========================================
    // GROUP 2: GPU Telemetry & TensorRT Hardware
    // ==========================================
    layout->addWidget(create_section_header("Active GPU & TensorRT Engine Profile", "#4ade80"));

    // Spec Box Card
    QWidget* spec_card = new QWidget(content);
    spec_card->setStyleSheet("background-color: #141418; border: 1px solid #3c3c3c; border-radius: 6px; padding: 6px;");
    QVBoxLayout* spec_layout = new QVBoxLayout(spec_card);
    spec_layout->setContentsMargins(12, 10, 12, 10);
    spec_layout->setSpacing(8);

    spec_layout->addWidget(create_spec_row("Compute Device:", gpu.name, "#4ade80"));

    // Architecture identification comes from the CUDA compute capability, not the
    // marketing name ("RTX 4000" style strings are not reliable).
    const QString arch_name = trt_arch_detector::instance().get_arch_name();
    spec_layout->addWidget(create_spec_row("Microarchitecture:", arch_name, "#9b59ff"));
    spec_layout->addWidget(create_spec_row("Dedicated VRAM:", gpu.get_vram_string(), "#e0e0e0"));
    spec_layout->addWidget(create_spec_row("TensorRT FP16 Support:", gpu.supports_fp16 ? "Hardware Accelerated (Enabled)" : "Emulated (FP32 Fallback)", gpu.supports_fp16 ? "#4ade80" : "#fbbf24"));
    spec_layout->addWidget(create_spec_row("CUDA Core Pipeline:", "CUDA 13.x Runtime Engine Active", "#06b6d4"));

    layout->addWidget(spec_card);

    // Architecture Override Option
    QStringList arch_modes = {
        "Automatic (Detect Compute Capability)",
        "Force Ada Lovelace (Batch 2 UNet / 800px Tiles)",
        "Force Turing (Batch 1 UNet / 512px Tiles - 4GB Safe)"
    };
    layout->addWidget(create_combo_row(
        "Architecture Dispatch",
        "Override compute profile if testing on different GPUs.",
        arch_modes, settings.arch_dispatch_mode, combo_arch_dispatch
    ));

    layout->addStretch();
    scroll->setWidget(content);
    master_layout->addWidget(scroll);

    // ==========================================
    // LIVE SETTINGS BINDING (Auto-save)
    // ==========================================
    auto update_config = []() { return config_mgr::instance().get_settings(); };

    connect(combo_persist_bpn, &QComboBox::currentIndexChanged, this, [=](int index) {
        AppSettings s = update_config(); s.persist_bpn = index; config_mgr::instance().update_settings(s);
        });

    connect(combo_persist_moebius, &QComboBox::currentIndexChanged, this, [=](int index) {
        AppSettings s = update_config(); s.persist_moebius = index; config_mgr::instance().update_settings(s);
        });

    connect(combo_persist_lama, &QComboBox::currentIndexChanged, this, [=](int index) {
        AppSettings s = update_config(); s.persist_lama = index; config_mgr::instance().update_settings(s);
        });

    connect(combo_arch_dispatch, &QComboBox::currentIndexChanged, this, [=](int index) {
        AppSettings s = update_config(); s.arch_dispatch_mode = index; config_mgr::instance().update_settings(s);
        });
}

// === ROW GENERATORS ===

QLabel* settings_system::create_section_header(const QString& title, const QString& hex_color) {
    QLabel* lbl = new QLabel(title, this);
    lbl->setStyleSheet(QString("color: %1; font-size: 13px; font-weight: bold; margin-top: 8px; margin-bottom: 2px;").arg(hex_color));
    return lbl;
}

QFrame* settings_system::create_separator() {
    QFrame* line = new QFrame(this);
    line->setFrameShape(QFrame::HLine);
    line->setStyleSheet("color: #3c3c3c; margin: 4px 0px;");
    return line;
}

QWidget* settings_system::create_combo_row(const QString& label_text, const QString& desc_text, const QStringList& options, int default_index, QComboBox*& combo_ptr) {
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

    combo_ptr = new QComboBox(row);
    combo_ptr->addItems(options);
    combo_ptr->setCurrentIndex(default_index);
    combo_ptr->setFixedWidth(205); // Compact width to prevent horizontal overflow
    combo_ptr->setCursor(Qt::PointingHandCursor);
    combo_ptr->setStyleSheet(
        "QComboBox { background-color: #1e1e1e; color: #e0e0e0; border: 1px solid #3c3c3c; border-radius: 4px; padding: 5px 8px; font-size: 11px; }"
        "QComboBox::drop-down { border: none; width: 18px; }"
        "QComboBox QAbstractItemView { background-color: #1e1e1e; color: #e0e0e0; border: 1px solid #3c3c3c; selection-background-color: #3c3c3c; }"
    );

    layout->addLayout(text_layout, 1);
    layout->addWidget(combo_ptr, 0, Qt::AlignVCenter);

    return row;
}

QWidget* settings_system::create_spec_row(const QString& label, const QString& value, const QString& val_color) {
    QWidget* row = new QWidget(this);
    QHBoxLayout* layout = new QHBoxLayout(row);
    layout->setContentsMargins(0, 2, 0, 2);

    QLabel* lbl = new QLabel(label, row);
    lbl->setStyleSheet("color: #8f8f8f; font-size: 11px; font-weight: bold; border: none; background: transparent;");

    QLabel* val = new QLabel(value, row);
    val->setStyleSheet(QString("color: %1; font-size: 11px; font-weight: bold; font-family: monospace; border: none; background: transparent;").arg(val_color));

    layout->addWidget(lbl);
    layout->addStretch();
    layout->addWidget(val);

    return row;
}