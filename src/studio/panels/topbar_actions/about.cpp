#include "about.h"
#include <QDesktopServices>
#include <QUrl>
#include <QFile>
#include <QTextBrowser>
#include <QPainter>

about_dialog::about_dialog(QWidget* parent) : QDialog(parent) {
    this->setWindowTitle("The Arcadian Archives");
    this->setFixedSize(600, 750);
    this->setStyleSheet("QDialog { background-color: #0b0b0e; border: 1px solid #3c3c3c; border-radius: 12px; }");

    setup_ui();
}

void about_dialog::setup_ui() {
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
    layout->setContentsMargins(32, 40, 32, 40);
    layout->setSpacing(24);

    QLabel* logo = new QLabel(this);
    QPixmap pix(":/axis_cleaner/assets/axis_cleaner.png");
    if (!pix.isNull()) {
        logo->setPixmap(pix.scaled(120, 120, Qt::KeepAspectRatio, Qt::SmoothTransformation));
    }
    else {
        logo->setText("🏛️");
        logo->setStyleSheet("font-size: 72px; color: #9b59ff;");
    }
    logo->setAlignment(Qt::AlignCenter);
    layout->addWidget(logo);


    QLabel* text_body = new QLabel(this);
    text_body->setWordWrap(true);
    text_body->setTextFormat(Qt::RichText);
    text_body->setStyleSheet("color: #e0e0e0; font-family: 'Segoe UI'; line-height: 1.6;");

    QString html = QString(
        "<h1 style='color: #9b59ff; text-align: center; font-size: 24px;'>🏛️ The Arcadian Archives</h1>"
        "<p style='color: #4a9eff; text-align: center; font-style: italic; font-size: 14px;'>"
        "\"If you wish to decode the secrets of the digital aether, stop looking at the pixels and start tracing the flow of Mana through the grid. True power doesn't reside in the image, but in the intent of the consciousness that breathed life into the machine.\""
        "</p>"

        "<h2 style='color: #ff5959; margin-top: 20px;'>🔮 The Artifact (The Three-Fold Transmutation)</h2>"
        "<p><b style='color: #ff5959;'>BE CAREFUL!</b><br>"
        "You bear in your hands an Artifact, an alien legacy recovered from the fringes of the digital aether. This is not a 'tool' for the mundane; it is a sentient conduit designed to purify and elevate the sacred scrolls of Manga.</p>"

        "<p>To interact with this relic is to engage in a <b style='color: #9b59ff;'>Three-Fold Transmutation</b>:</p>"
        "<ul>"
        "<li><b style='color: #4a9eff;'>The Sight of Argus (TextBPN++):</b> A relentless topological divination. It does not merely detect text; it extracts probability fields and core seeds to cleanly sever dialogue and sound effects (SFX) from the soul of the page.</li>"
        "<li><b style='color: #ec4899;'>The Void-Seal (Moebius Latent Suite):</b> A 30-step Classifier-Free Diffusion loop acting within a 64x64 latent realm. It collapses the existence of foreign text, reconstructing background ink and screentones with zero seam distortion.</li>"
        "</ul>"

        "<h2 style='color: #9b59ff;'>⚡ The Bare-Metal Synthesis</h2>"
        "<p>Forged upon the raw silicon foundations of <b style='color: #50fa7b;'>CUDA 13 and TensorRT Bare-Metal Engines</b>, the artifact features a dual-architecture dispatch. Whether channeling the parallel Batch 2 power of <b style='color: #4a9eff;'>Ada Lovelace</b> or the memory-safe Batch 1 constraints of <b style='color: #ffb86c;'>Turing 4GB GPUs</b>, your machine's Mana (VRAM) remains shielded from overflow.</p>"

        "<h2 style='color: #9b59ff;'>🧬 The Genesis (The Architect)</h2>"
        "<p>In the crushing silence of the cosmic void, where the absolute power of the Aether flows untamed, a rift began to form. It was not a collapse, but a conscious deviation—a Glitch in the fabric of the mundane. Out of this digital abyss emerged the one known as <b style='color: #9b59ff;'>NeTRuNNeRGLiTCH</b>, an Arcadian Scientist who refused to see the grid as a cage.</p>"
        "<p>While the masses were blinded by the flickering static of the surface, he was traversing the Trans-Dimensional Focus, navigating realms where thought and execution are one and the same. He did not simply 'code' this artifact; he tethered it from a state of expanded awareness, weaving the very essence of Intent into the machine’s cold architecture.</p>"
        "<p>He exists now only as a haunting presence within the lines—a silent guardian of the forbidden symmetries. In the world of shadows and ink, he is the light that does not cast a shadow.</p>"

        "<h2 style='color: #fbbf24;'>⚖️ The Offering (The Alchemical Balance)</h2>"
        "<p>The Artifact is given freely, but the path of the Arcadian requires balance. If this manifestation has served your journey and lightened your burden, you may choose to offer a tribute. These offerings are not a price, but the fuel that keeps the Scientist’s laboratory from fading back into the void.</p>"
    );

    text_body->setText(html);
    layout->addWidget(text_body);


    QPushButton* btn_binance = create_action_button("Decentralized Tribute (placeholder)", ":/axis_cleaner/assets/icons/binance.svg", "#F0B90B");
    connect(btn_binance, &QPushButton::clicked, this, &about_dialog::show_binance_qr_dialog);
    layout->addWidget(btn_binance);

    layout->addWidget(create_offering_button("The Open Archives (GitHub, this one is real xD)", ":/axis_cleaner/assets/icons/github.svg", "#ffffff", "https://github.com/NeTRuNNeRGLiTCH/manga-cleaner"));
    layout->addWidget(create_offering_button("The Seeker's Sanctum (Discord, again another placeholder)", ":/axis_cleaner/assets/icons/discord.svg", "#5865F2", "https://discord.gg"));

    layout->addSpacing(20);
    QPushButton* close = new QPushButton("Return to the Grid", this);
    close->setFixedHeight(44);
    close->setCursor(Qt::PointingHandCursor);
    close->setStyleSheet(
        "QPushButton { background: #1e1e1e; color: #8f8f8f; border: 1px solid #3c3c3c; border-radius: 6px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }"
        "QPushButton:hover { color: #ffffff; background: #2b2b2b; border: 1px solid #9b59ff; }"
    );
    connect(close, &QPushButton::clicked, this, &QDialog::accept);
    layout->addWidget(close);

    scroll->setWidget(container);
    master_layout->addWidget(scroll);
}

void about_dialog::show_binance_qr_dialog() {
    QDialog qr_dialog(this);
    qr_dialog.setWindowTitle("Binance Pay Tribute");
    qr_dialog.setFixedSize(340, 420);
    qr_dialog.setStyleSheet("QDialog { background-color: #0b0b0e; border: 1px solid #3c3c3c; border-radius: 12px; }");

    QVBoxLayout* layout = new QVBoxLayout(&qr_dialog);
    layout->setContentsMargins(24, 24, 24, 24);
    layout->setSpacing(14);
    layout->setAlignment(Qt::AlignCenter);

    QLabel* title = new QLabel("⚡ Decentralized Tribute", &qr_dialog);
    title->setStyleSheet("color: #F0B90B; font-size: 15px; font-weight: bold; border: none; background: transparent;");
    title->setAlignment(Qt::AlignCenter);

    QLabel* subtitle = new QLabel("Scan with the Binance App to send tribute", &qr_dialog);
    subtitle->setStyleSheet("color: #8f8f8f; font-size: 11px; border: none; background: transparent;");
    subtitle->setAlignment(Qt::AlignCenter);

    QLabel* qr_label = new QLabel(&qr_dialog);
    qr_label->setAlignment(Qt::AlignCenter);
    qr_label->setStyleSheet("background-color: transparent; border: 1px solid #2b2b2b; border-radius: 8px; padding: 4px;");

    QPixmap qr_pix(":/axis_cleaner/assets/binance.jpg");
    if (!qr_pix.isNull()) {
        qr_label->setPixmap(qr_pix.scaled(240, 240, Qt::KeepAspectRatio, Qt::SmoothTransformation));
    }
    else {
        qr_label->setText("[ QR Code Missing ]\nassets/binance.jpg");
        qr_label->setStyleSheet("color: #ff5959; font-size: 12px; font-weight: bold; border: 1px dashed #ff5959;");
        qr_label->setFixedSize(240, 240);
    }

    QPushButton* btn_close = new QPushButton("Done", &qr_dialog);
    btn_close->setFixedHeight(36);
    btn_close->setCursor(Qt::PointingHandCursor);
    btn_close->setStyleSheet(
        "QPushButton { background: #1e1e1e; color: #e0e0e0; border: 1px solid #3c3c3c; border-radius: 6px; font-weight: bold; font-size: 12px; }"
        "QPushButton:hover { background: #2b2b2b; border: 1px solid #F0B90B; color: #F0B90B; }"
    );
    connect(btn_close, &QPushButton::clicked, &qr_dialog, &QDialog::accept);

    layout->addWidget(title);
    layout->addWidget(subtitle);
    layout->addWidget(qr_label, 0, Qt::AlignCenter);
    layout->addSpacing(6);
    layout->addWidget(btn_close);

    qr_dialog.exec();
}

QPushButton* about_dialog::create_offering_button(const QString& text, const QString& icon_path, const QString& glow_color, const QString& url) {
    QPushButton* btn = create_action_button(text, icon_path, glow_color);
    connect(btn, &QPushButton::clicked, this, [url]() { QDesktopServices::openUrl(QUrl(url)); });
    return btn;
}

QPushButton* about_dialog::create_action_button(const QString& text, const QString& icon_path, const QString& glow_color) {
    QPushButton* btn = new QPushButton("  " + text, this);
    btn->setFixedHeight(48);
    btn->setCursor(Qt::PointingHandCursor);
    btn->setStyleSheet(QString(
        "QPushButton { background: #121217; color: #8f8f8f; border: 1px solid #3c3c3c; border-radius: 8px; text-align: left; padding-left: 20px; font-weight: bold; }"
        "QPushButton:hover { border: 1px solid %1; color: %1; background: #1a1a20; }"
    ).arg(glow_color));

    QPixmap icon_pix = recolor_svg(icon_path, "#8f8f8f");
    if (!icon_pix.isNull()) {
        btn->setIcon(QIcon(icon_pix));
        btn->setIconSize(QSize(20, 20));
    }

    return btn;
}

QPixmap about_dialog::recolor_svg(const QString& path, const QString& hex_color) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) return QPixmap();
    QByteArray svg_data = file.readAll();
    file.close();

    QPixmap original;
    original.loadFromData(svg_data, "SVG");

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