#include "help.h"

help_dialog::help_dialog(QWidget* parent) : QDialog(parent) {
    this->setWindowTitle("Axis Studio - User Manual & Shortcuts");
    this->setFixedSize(650, 720);
    this->setStyleSheet("QDialog { background-color: #0b0b0e; border: 1px solid #3c3c3c; border-radius: 12px; }");

    setup_ui();
}

void help_dialog::setup_ui() {
    QVBoxLayout* master_layout = new QVBoxLayout(this);
    master_layout->setContentsMargins(0, 0, 0, 0);

    QScrollArea* scroll = new QScrollArea(this);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setStyleSheet(
        "QScrollArea { background-color: transparent; }"
        "QScrollBar:vertical { border: none; background: #0b0b0e; width: 6px; }"
        "QScrollBar::handle:vertical { background: #3c3c3c; border-radius: 3px; }"
    );

    QWidget* container = new QWidget();
    container->setStyleSheet("background-color: #0b0b0e;");
    QVBoxLayout* layout = new QVBoxLayout(container);
    layout->setContentsMargins(32, 32, 32, 32);
    layout->setSpacing(16);

    // === TITLE ===
    QLabel* title = new QLabel("The Runes of Control", this);
    title->setStyleSheet("color: #9b59ff; font-size: 24px; font-weight: bold; text-align: center;");
    title->setAlignment(Qt::AlignCenter);
    layout->addWidget(title);

    QLabel* subtitle = new QLabel("Mastering Axis Studio's Photoshop controls and AI workflow.", this);
    subtitle->setStyleSheet("color: #8f8f8f; font-size: 13px; font-style: italic; margin-bottom: 16px;");
    subtitle->setAlignment(Qt::AlignCenter);
    layout->addWidget(subtitle);

    // === SECTION 1: KEYBOARD SHORTCUTS ===
    layout->addWidget(create_section_header("I. Hotkeys & Controls (Photoshop Parity)", "#4a9eff"));

    layout->addWidget(create_shortcut_row("Space (Hold) + Drag", "Pan around the canvas."));
    layout->addWidget(create_shortcut_row("H", "Hand Tool (pan mode; returns to the previous tool)."));
    layout->addWidget(create_shortcut_row("B", "Paint Mode (Brush Tool)."));
    layout->addWidget(create_shortcut_row("E", "Erase Mode (Remove Mask)."));
    layout->addWidget(create_shortcut_row("M", "Rectangular Marquee Selection."));
    layout->addWidget(create_shortcut_row("L", "Lasso Selection Tool."));
    layout->addWidget(create_shortcut_row("W", "Magic Wand Selection Tool."));
    layout->addWidget(create_shortcut_row("Alt + RMB (Drag)", "Dynamically resize active brush diameter."));
    layout->addWidget(create_shortcut_row("Ctrl + Z", "Undo last Selection / Mask stroke."));
    layout->addWidget(create_shortcut_row("Ctrl + Q", "Redo last Selection / Mask stroke."));
    layout->addWidget(create_shortcut_row("Shift + Z", "Undo last AI Inpainting pass."));
    layout->addWidget(create_shortcut_row("Shift + Q", "Redo last AI Inpainting pass."));
    layout->addWidget(create_shortcut_row("[ / ]", "Decrease / Increase Brush Size or Wand Tolerance."));
    layout->addWidget(create_shortcut_row("Ctrl + Mouse Wheel", "Zoom in and out of the canvas."));
    layout->addWidget(create_shortcut_row("1 / 2", "Quick AI Triggers: 1 (Detect), 2 (Clean)."));
    layout->addWidget(create_shortcut_row("Tab", "Toggle UI visibility to focus strictly on the canvas."));
    layout->addWidget(create_shortcut_row("PageDown", "Gallery: load the NEXT page (edits are kept per page)."));
    layout->addWidget(create_shortcut_row("PageUp", "Gallery: load the PREVIOUS page (edits are kept per page)."));

    // === SECTION 2: BATCH WORKFLOW ===
    layout->addWidget(create_section_header("II. Batch Chapter Automation (Wizard Engine)", "#10b981"));
    QLabel* batch_text = new QLabel(
        "<p style='color: #e0e0e0; font-size: 12px; line-height: 1.5;'>"
        "1. Open the <b>Settings</b> dialog and configure your preferred model and export parameters.<br>"
        "2. Ensure you have set a valid <i>Batch Output Destination</i>.<br>"
        "3. Click <b>Import Folder</b> from the Top Bar to load an entire manga chapter into the Gallery.<br>"
        "4. Switch to the <b>Wizard</b> tab on the right panel and configure <i>Scan Transparency</i>.<br>"
        "5. Click <b>Run Wizard</b> to process all pages in parallel with TensorRT acceleration."
        "</p>", this);
    batch_text->setWordWrap(true);
    batch_text->setTextFormat(Qt::RichText);
    layout->addWidget(batch_text);

    // === SECTION 3: FILE MENU & WORKSPACE ===
    layout->addWidget(create_section_header("III. File Menu & Page Workflow", "#f472b6"));
    QLabel* file_text = new QLabel(
        "<p style='color: #e0e0e0; font-size: 12px; line-height: 1.5;'>"
        "- <b>Save / Ctrl+S</b> exports ONLY the page currently open on the canvas; <b>Save All</b> exports every Gallery page.<br>"
        "- Pages you clean or mask in the Studio are remembered per page; <b>Export / Save All</b> skips pages you never touched.<br>"
        "- <b>Remove Image</b> drops the page you are looking at from the Gallery.<br>"
        "- Page edits are cached on disk and auto-pruned after <b>30 days</b>; <b>File &gt; Clear Cached Page Edits</b> wipes the cache immediately."
        "</p>", this);
    file_text->setWordWrap(true);
    file_text->setTextFormat(Qt::RichText);
    layout->addWidget(file_text);

    // === SECTION 4: VRAM & SYSTEM PERFORMANCE ===
    layout->addWidget(create_section_header("IV. Hardware Acceleration & VRAM Optimization", "#fbbf24"));
    QLabel* vram_text = new QLabel(
        "<p style='color: #e0e0e0; font-size: 12px; line-height: 1.5;'>"
        "Axis Studio utilizes bare-metal TensorRT inference optimized for Ada Lovelace, Turing, Ampere, and Blackwell architectures.<br><br>"
        "<b>Performance & Stability Tips:</b><br>"
        "- <b>Transparency Scanner:</b> Quickly detects cut-out bubble transparency (alpha == 0) and creates ready-to-inpaint masks in one click.<br>"
        "- <b>Tiling & Out-Of-Memory Prevention:</b> Configure tile sizes in <i>Settings > Models</i> for seamless inpainting on low-VRAM GPUs.<br>"
        "- <b>Model Scanner:</b> Navigate to <i>Settings > Models</i> and click <i>Scan Models</i> to check the availability and GPU residency of all installed AI engines."
        "</p>", this);
    vram_text->setWordWrap(true);
    vram_text->setTextFormat(Qt::RichText);
    layout->addWidget(vram_text);

    layout->addSpacing(20);

    // === CLOSE BUTTON ===
    QPushButton* close = new QPushButton("Close Manual", this);
    close->setFixedHeight(44);
    close->setStyleSheet("QPushButton { background: #1e1e1e; color: #8f8f8f; border: 1px solid #3c3c3c; border-radius: 6px; font-weight: bold; text-transform: uppercase; } QPushButton:hover { color: #ffffff; background: #2b2b2b; border: 1px solid #4a9eff;}");
    connect(close, &QPushButton::clicked, this, &QDialog::accept);
    layout->addWidget(close);

    scroll->setWidget(container);
    master_layout->addWidget(scroll);
}

QLabel* help_dialog::create_section_header(const QString& title, const QString& hex_color) {
    QLabel* lbl = new QLabel(title, this);
    lbl->setStyleSheet(QString("color: %1; font-size: 16px; font-weight: bold; margin-top: 16px; margin-bottom: 8px;").arg(hex_color));
    return lbl;
}

QWidget* help_dialog::create_shortcut_row(const QString& keys, const QString& description) {
    QWidget* row = new QWidget(this);
    QHBoxLayout* layout = new QHBoxLayout(row);
    layout->setContentsMargins(8, 4, 8, 4);

    QLabel* key_lbl = new QLabel(keys, row);
    key_lbl->setStyleSheet("color: #e0e0e0; font-family: monospace; font-size: 13px; font-weight: bold; background: #1e1e1e; padding: 4px 8px; border-radius: 4px; border: 1px solid #3c3c3c;");
    key_lbl->setFixedWidth(190);
    key_lbl->setAlignment(Qt::AlignCenter);

    QLabel* desc_lbl = new QLabel(description, row);
    desc_lbl->setStyleSheet("color: #8f8f8f; font-size: 12px;");
    desc_lbl->setWordWrap(true);

    layout->addWidget(key_lbl);
    layout->addWidget(desc_lbl, 1);

    return row;
}