#include "gallery_tab.h"
#include <QFile>
#include <QPainter>
#include <QFileInfo>

const QString GAL_SCROLLBAR_STYLE =
"QScrollBar:vertical { border: none; background: #1e1e1e; width: 8px; margin: 0px; }"
"QScrollBar::handle:vertical { background: #3c3c3c; border-radius: 4px; min-height: 20px; }"
"QScrollBar::handle:vertical:hover { background: #4c4c4c; }"
"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }";


gallery_tab::gallery_tab(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);
    this->setStyleSheet("background-color: #1e1e1e;");
    this->installEventFilter(this);

    setup_ui();
}

void gallery_tab::setup_ui() {
    QVBoxLayout* main_layout = new QVBoxLayout(this);
    main_layout->setContentsMargins(0, 0, 0, 0);
    main_layout->setSpacing(0);

    // === SCROLL AREA SETUP ===
    scroll_area = new QScrollArea(this);
    scroll_area->setWidgetResizable(true);
    scroll_area->setFrameShape(QFrame::NoFrame);
    scroll_area->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    scroll_area->setStyleSheet(GAL_SCROLLBAR_STYLE);

    scroll_content = new QWidget(scroll_area);
    scroll_content->setStyleSheet("background-color: #1e1e1e;");

    QVBoxLayout* content_layout = new QVBoxLayout(scroll_content);
    content_layout->setContentsMargins(16, 16, 16, 16);
    content_layout->setSpacing(16);

    // === HEADER: TITLE & TOOLBAR ===
    QHBoxLayout* header_layout = new QHBoxLayout();
    header_layout->setContentsMargins(0, 0, 0, 0);

    header_count_label = new QLabel("Loaded Images (0)", this);
    header_count_label->setStyleSheet("color: #e0e0e0; font-size: 13px; font-weight: bold; background: transparent;");

    // Trash Button (Clears the gallery manually)
    QPushButton* btn_trash = new QPushButton(this);
    btn_trash->setIcon(QIcon(recolor_svg(":/axis_cleaner/assets/icons/trash.svg", "#8f8f8f")));
    btn_trash->setFixedSize(24, 24);
    btn_trash->setCursor(Qt::PointingHandCursor);
    btn_trash->setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: #2b2b2b; }");
    connect(btn_trash, &QPushButton::clicked, this, [this]() {
        // The main window syncs its own file list + session first (via the
        // signal), then this panel wipes its items.
        emit clear_requested();
        clear_gallery();
    });

    header_layout->addWidget(header_count_label);
    header_layout->addStretch();
    header_layout->addWidget(btn_trash);

    content_layout->addLayout(header_layout);

    // === IMAGE LIST ===
    list_layout = new QVBoxLayout();
    list_layout->setSpacing(8);

    empty_state_widget = create_empty_state();
    list_layout->addWidget(empty_state_widget);

    content_layout->addLayout(list_layout);
    content_layout->addWidget(create_separator());

    // === WORKFLOW INFO BOX ===
    QWidget* info_box = new QWidget(this);
    info_box->setStyleSheet("background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 6px;");

    QVBoxLayout* info_layout = new QVBoxLayout(info_box);
    info_layout->setContentsMargins(12, 12, 12, 12);
    info_layout->setSpacing(8);

    QLabel* info_title = new QLabel("Gallery Management", info_box);
    info_title->setStyleSheet("color: #e0e0e0; font-size: 11px; font-weight: bold; border: none; background: transparent;");

    QLabel* info_desc = new QLabel("View and navigate between all currently loaded manga pages. Click an image to set it as the active canvas.", info_box);
    info_desc->setStyleSheet("color: #8f8f8f; font-size: 10px; line-height: 1.5; border: none; background: transparent;");
    info_desc->setWordWrap(true);

    info_layout->addWidget(info_title);
    info_layout->addWidget(info_desc);

    content_layout->addWidget(info_box);

    content_layout->addStretch();
    scroll_area->setWidget(scroll_content);
    main_layout->addWidget(scroll_area);
}

// === SCROLLBAR HOVER LOGIC ===

bool gallery_tab::eventFilter(QObject* obj, QEvent* event) {
    if (obj == this) {
        if (event->type() == QEvent::Enter) {
            scroll_area->setVerticalScrollBarPolicy(Qt::ScrollBarAsNeeded);
        }
        else if (event->type() == QEvent::Leave) {
            scroll_area->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
        }
    }
    return QWidget::eventFilter(obj, event);
}

// === REAL DATA INJECTION ===

void gallery_tab::populate_gallery(const QStringList& file_paths) {
    clear_gallery();
    m_file_paths = file_paths;

    for (int i = 0; i < m_file_paths.size(); ++i) {
        QFileInfo fi(m_file_paths[i]);
        QString name = fi.fileName();

        // Example: "Image 1 of 45 | 4 MB"
        QString info = QString("Page %1 of %2 | %3 MB")
            .arg(i + 1)
            .arg(m_file_paths.size())
            .arg(QString::number(fi.size() / (1024.0 * 1024.0), 'f', 1));

        QPushButton* item = create_gallery_item(i, name, info, ":/axis_cleaner/assets/icons/images.svg", false);

        image_buttons.append(item);
        indicator_dots.append(item->findChildren<QWidget*>().last());

        list_layout->addWidget(item);
    }

    update_image_count(m_file_paths.size());
}

void gallery_tab::clear_gallery() {
    for (auto btn : image_buttons) {
        list_layout->removeWidget(btn);
        delete btn;
    }
    image_buttons.clear();
    indicator_dots.clear();
    m_file_paths.clear();

    update_image_count(0);
}

void gallery_tab::update_image_count(int count) {
    header_count_label->setText(QString("Loaded Images (%1)").arg(count));

    if (count == 0) {
        empty_state_widget->show();
    }
    else {
        empty_state_widget->hide();
    }
}

// === ACTION ROUTING ===

void gallery_tab::highlight_item(int index) {
    QString active_style = "QPushButton#GalleryItem { background-color: #323232; border: 1px solid #9b59ff; border-radius: 6px; text-align: left; }"
        "QPushButton#GalleryItem:hover { background-color: #3c3c3c; }";

    QString inactive_style = "QPushButton#GalleryItem { background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 6px; text-align: left; }"
        "QPushButton#GalleryItem:hover { background-color: #323232; border: 1px solid #4c4c4c; }";

    for (int i = 0; i < image_buttons.size(); ++i) {
        if (i == index) {
            image_buttons[i]->setStyleSheet(active_style);
            indicator_dots[i]->show();
        }
        else {
            image_buttons[i]->setStyleSheet(inactive_style);
            indicator_dots[i]->hide();
        }
    }
}

void gallery_tab::set_active_file(const QString& filepath) {
    const int index = m_file_paths.indexOf(filepath);
    if (index >= 0) highlight_item(index);
}

void gallery_tab::on_image_clicked(int index) {
    if (index < 0 || index >= m_file_paths.size()) return;

    highlight_item(index);

    // Tell the main window to load this specific file into OpenCV!
    emit request_open_image(m_file_paths[index]);
}

// === HELPER METHODS ===

QWidget* gallery_tab::create_empty_state() {
    QWidget* container = new QWidget(this);
    container->setStyleSheet("background: transparent;");
    QVBoxLayout* layout = new QVBoxLayout(container);
    layout->setAlignment(Qt::AlignCenter);
    layout->setContentsMargins(0, 32, 0, 32);
    layout->setSpacing(12);

    QLabel* icon_lbl = new QLabel(container);
    icon_lbl->setPixmap(recolor_svg(":/axis_cleaner/assets/icons/images.svg", "#4c4c4c").scaled(48, 48, Qt::KeepAspectRatio, Qt::SmoothTransformation));
    icon_lbl->setAlignment(Qt::AlignCenter);
    icon_lbl->setStyleSheet("background: transparent;");

    QLabel* text_lbl = new QLabel("No images loaded", container);
    text_lbl->setStyleSheet("color: #8f8f8f; font-size: 12px; font-weight: bold; background: transparent;");
    text_lbl->setAlignment(Qt::AlignCenter);

    QLabel* sub_lbl = new QLabel("Open images from the File menu", container);
    sub_lbl->setStyleSheet("color: #6f6f6f; font-size: 10px; background: transparent;");
    sub_lbl->setAlignment(Qt::AlignCenter);

    layout->addWidget(icon_lbl);
    layout->addWidget(text_lbl);
    layout->addWidget(sub_lbl);

    return container;
}

QPushButton* gallery_tab::create_gallery_item(int index, const QString& name, const QString& info, const QString& thumb_icon, bool is_active) {
    QPushButton* btn = new QPushButton(this);
    btn->setFixedHeight(64);
    btn->setCursor(Qt::PointingHandCursor);
    btn->setObjectName("GalleryItem");

    QString active_style = "QPushButton#GalleryItem { background-color: #323232; border: 1px solid #9b59ff; border-radius: 6px; text-align: left; }"
        "QPushButton#GalleryItem:hover { background-color: #3c3c3c; }";

    QString inactive_style = "QPushButton#GalleryItem { background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 6px; text-align: left; }"
        "QPushButton#GalleryItem:hover { background-color: #323232; border: 1px solid #4c4c4c; }";

    btn->setStyleSheet(is_active ? active_style : inactive_style);

    QHBoxLayout* layout = new QHBoxLayout(btn);
    layout->setContentsMargins(8, 8, 12, 8);
    layout->setSpacing(12);

    QWidget* thumb_box = new QWidget(btn);
    thumb_box->setFixedSize(48, 48);
    thumb_box->setStyleSheet("background-color: #1e1e1e; border-radius: 4px; border: 1px solid #3c3c3c;");
    thumb_box->setAttribute(Qt::WA_TransparentForMouseEvents);

    QVBoxLayout* thumb_layout = new QVBoxLayout(thumb_box);
    thumb_layout->setContentsMargins(0, 0, 0, 0);
    QLabel* img_icon = new QLabel(thumb_box);
    img_icon->setStyleSheet("background: transparent;");
    img_icon->setPixmap(recolor_svg(thumb_icon, "#6f6f6f").scaled(24, 24, Qt::KeepAspectRatio, Qt::SmoothTransformation));
    img_icon->setAlignment(Qt::AlignCenter);
    thumb_layout->addWidget(img_icon);

    QWidget* text_box = new QWidget(btn);
    text_box->setStyleSheet("background-color: transparent; border: none;");
    text_box->setAttribute(Qt::WA_TransparentForMouseEvents);

    QVBoxLayout* text_layout = new QVBoxLayout(text_box);
    text_layout->setContentsMargins(0, 4, 0, 4);
    text_layout->setSpacing(2);

    QLabel* title_lbl = new QLabel(name, text_box);
    // Prevent extremely long filenames from breaking the UI layout
    QFontMetrics metrics(title_lbl->font());
    QString elided_title = metrics.elidedText(name, Qt::ElideRight, 160);
    title_lbl->setText(elided_title);
    title_lbl->setStyleSheet("color: #e0e0e0; font-size: 11px; font-weight: bold; background: transparent; border: none;");

    QLabel* info_lbl = new QLabel(info, text_box);
    info_lbl->setStyleSheet("color: #6f6f6f; font-size: 10px; background: transparent; border: none;");

    text_layout->addWidget(title_lbl);
    text_layout->addWidget(info_lbl);
    text_layout->addStretch();

    QWidget* dot = new QWidget(btn);
    dot->setFixedSize(8, 8);
    dot->setStyleSheet("background-color: #9b59ff; border-radius: 4px; border: none;");
    dot->setAttribute(Qt::WA_TransparentForMouseEvents);
    dot->setVisible(is_active);

    layout->addWidget(thumb_box);
    layout->addWidget(text_box);
    layout->addStretch();
    layout->addWidget(dot, 0, Qt::AlignVCenter);

    connect(btn, &QPushButton::clicked, this, [this, index]() { on_image_clicked(index); });

    return btn;
}

QPixmap gallery_tab::recolor_svg(const QString& path, const QString& hex_color) {
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

QFrame* gallery_tab::create_separator() {
    QFrame* line = new QFrame(this);
    line->setFrameShape(QFrame::HLine);
    line->setFrameShadow(QFrame::Plain);
    line->setStyleSheet("color: #3c3c3c; margin: 4px 0px;");
    return line;
}