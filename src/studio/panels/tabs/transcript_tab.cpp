#include "transcript_tab.h"
#include <QFrame>
#include <QIcon>
#include <QFile>
#include <QApplication>
#include <QTimer>
#include <QPainter>
#include <QTextBlock>
#include <QRandomGenerator>

// ==========================================================
// TranscriptEditor & LineNumberArea Implementation
// ==========================================================

LineNumberArea::LineNumberArea(TranscriptEditor* editor) : QWidget(editor), codeEditor(editor) {}

QSize LineNumberArea::sizeHint() const {
    return QSize(codeEditor->lineNumberAreaWidth(), 0);
}

void LineNumberArea::paintEvent(QPaintEvent* event) {
    codeEditor->lineNumberAreaPaintEvent(event);
}

TranscriptEditor::TranscriptEditor(QWidget* parent) : QPlainTextEdit(parent) {
    lineNumberArea = new LineNumberArea(this);

    connect(this, &TranscriptEditor::blockCountChanged, this, &TranscriptEditor::updateLineNumberAreaWidth);
    connect(this, &TranscriptEditor::updateRequest, this, &TranscriptEditor::updateLineNumberArea);

    updateLineNumberAreaWidth(0);
}

int TranscriptEditor::lineNumberAreaWidth() {
    int digits = 1;
    int max = qMax(1, blockCount());
    while (max >= 10) {
        max /= 10;
        ++digits;
    }
    return 16 + fontMetrics().horizontalAdvance(QLatin1Char('9')) * digits;
}

void TranscriptEditor::updateLineNumberAreaWidth(int) {
    setViewportMargins(lineNumberAreaWidth(), 0, 0, 0);
}

void TranscriptEditor::updateLineNumberArea(const QRect& rect, int dy) {
    if (dy) lineNumberArea->scroll(0, dy);
    else lineNumberArea->update(0, rect.y(), lineNumberArea->width(), rect.height());

    if (rect.contains(viewport()->rect())) updateLineNumberAreaWidth(0);
}

void TranscriptEditor::resizeEvent(QResizeEvent* e) {
    QPlainTextEdit::resizeEvent(e);
    QRect cr = contentsRect();
    lineNumberArea->setGeometry(QRect(cr.left(), cr.top(), lineNumberAreaWidth(), cr.height()));
}

void TranscriptEditor::lineNumberAreaPaintEvent(QPaintEvent* event) {
    QPainter painter(lineNumberArea);
    painter.fillRect(event->rect(), QColor("#242424"));

    QTextBlock block = firstVisibleBlock();
    int blockNumber = block.blockNumber();
    int top = qRound(blockBoundingGeometry(block).translated(contentOffset()).top());
    int bottom = top + qRound(blockBoundingRect(block).height());

    while (block.isValid() && top <= event->rect().bottom()) {
        if (block.isVisible() && bottom >= event->rect().top()) {
            QString number = QString::number(blockNumber + 1) + ".";
            painter.setPen(QColor("#6f6f6f"));
            painter.drawText(0, top, lineNumberArea->width() - 8, fontMetrics().height(), Qt::AlignRight | Qt::AlignVCenter, number);
        }
        block = block.next();
        top = bottom;
        bottom = top + qRound(blockBoundingRect(block).height());
        ++blockNumber;
    }
}

// ==========================================================
// Global Scrollbar Stylesheets
// ==========================================================
const QString TRAN_SCROLLBAR_STYLE =
"QScrollBar:vertical { border: none; background: #1e1e1e; width: 6px; margin: 0px; }"
"QScrollBar::handle:vertical { background: #3c3c3c; border-radius: 3px; min-height: 20px; }"
"QScrollBar::handle:vertical:hover { background: #50fa7b; }"
"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }";

const QString TRAN_HIDDEN_SCROLLBAR =
"QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }"
"QScrollBar::handle:vertical { background: transparent; }";

transcript_tab::transcript_tab(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);
    this->setStyleSheet("background-color: #1e1e1e;");
    this->installEventFilter(this);
    setup_ui();
}

void transcript_tab::setup_ui() {
    QVBoxLayout* main_layout = new QVBoxLayout(this);
    main_layout->setContentsMargins(0, 0, 0, 0);
    main_layout->setSpacing(0);

    scroll_area = new QScrollArea(this);
    scroll_area->setWidgetResizable(true);
    scroll_area->setFrameShape(QFrame::NoFrame);
    scroll_area->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOn);
    scroll_area->setStyleSheet(TRAN_HIDDEN_SCROLLBAR);

    scroll_content = new QWidget(scroll_area);
    scroll_content->setStyleSheet("background-color: #1e1e1e;");

    QVBoxLayout* content_layout = new QVBoxLayout(scroll_content);
    content_layout->setContentsMargins(16, 16, 16, 16);
    content_layout->setSpacing(16);

    // === GROUP 1: TERMINAL & ACTIONS ===
    QVBoxLayout* editor_layout = new QVBoxLayout();
    editor_layout->setSpacing(10);

    editor_layout->addWidget(create_section_header("✨ Easter Egg Terminal (No Purpose)"));

    text_area = new TranscriptEditor(this);
    text_area->setMinimumHeight(300);
    text_area->setStyleSheet(
        "QPlainTextEdit { background-color: #242428; color: #50fa7b; font-family: monospace; border: 1px solid #3c3c3c; border-radius: 6px; font-size: 11px; line-height: 1.4; }"
        "QPlainTextEdit:focus { border: 1px solid #50fa7b; }"
    );

    // Default In-Universe Hacker Easter Egg Message
    QString easter_egg_init =
        "[EASTER EGG TERMINAL: ZERO OPERATIONAL PURPOSE]\n"
        "--------------------------------------------------\n"
        ">> Welcome to the Easter Egg Tab!\n"
        ">> This tab has no function or operational purpose.\n"
        ">> It exists purely for amusement, scanlation lore,\n"
        ">> and consulting the ancient Oracle.\n"
        "\n"
        ">> Current System State:\n"
        ">>  - Dialogue Extraction: Banished to the void.\n"
        ">>  - Background Inpainting: Hyper-optimized (TensorRT).\n"
        ">>  - Scribes: Fueled entirely by iced coffee.\n"
        "--------------------------------------------------\n";
    text_area->setPlainText(easter_egg_init);

    editor_layout->addWidget(text_area);

    // Action Buttons
    QHBoxLayout* actions_layout = new QHBoxLayout();
    actions_layout->setSpacing(8);

    btn_oracle = new QPushButton("  Consult the Oracle  ", this);
    btn_oracle->setIcon(QIcon(recolor_svg(":/axis_cleaner/assets/icons/wand-sparkles.svg", "#50fa7b")));
    btn_oracle->setIconSize(QSize(16, 16));
    btn_oracle->setFixedHeight(38);
    btn_oracle->setCursor(Qt::PointingHandCursor);
    btn_oracle->setStyleSheet(
        "QPushButton { background-color: #103820; color: #50fa7b; font-weight: bold; font-size: 11px; border-radius: 6px; border: 1px solid #50fa7b; }"
        "QPushButton:hover { background-color: #14532d; }"
    );
    connect(btn_oracle, &QPushButton::clicked, this, &transcript_tab::on_oracle_clicked);

    btn_clear = new QPushButton(" Purge ", this);
    btn_clear->setIcon(QIcon(recolor_svg(":/axis_cleaner/assets/icons/trash.svg", "#ff5959")));
    btn_clear->setIconSize(QSize(16, 16));
    btn_clear->setFixedHeight(38);
    btn_clear->setCursor(Qt::PointingHandCursor);
    btn_clear->setStyleSheet(
        "QPushButton { background-color: transparent; color: #ff5959; font-weight: bold; font-size: 11px; border-radius: 6px; border: 1px solid #3c3c3c; }"
        "QPushButton:hover { background-color: #3d1414; border: 1px solid #ff5959; }"
    );
    connect(btn_clear, &QPushButton::clicked, this, &transcript_tab::on_clear_clicked);

    actions_layout->addWidget(btn_oracle, 1);
    actions_layout->addWidget(btn_clear, 0);

    editor_layout->addLayout(actions_layout);
    content_layout->addLayout(editor_layout);
    content_layout->addWidget(create_separator());

    // === GROUP 2: THE SCRIBE'S CREED (Lore Box) ===
    QWidget* info_box = new QWidget(this);
    info_box->setStyleSheet("background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 6px;");
    QVBoxLayout* info_layout = new QVBoxLayout(info_box);
    info_layout->setContentsMargins(12, 12, 12, 12);
    info_layout->setSpacing(6);

    QLabel* info_title = new QLabel("📜 The Scribe's Creed", info_box);
    info_title->setStyleSheet("color: #50fa7b; font-size: 12px; font-weight: bold; border: none; background: transparent;");

    QLabel* info_steps = new QLabel(
        "1. Load raw manga page.\n"
        "2. Let TextBPN++ purge text and SFX.\n"
        "3. Inpaint with Moebius DDIM.\n"
        "4. Make up your own dialogue.\n"
        "5. Become the author.", info_box);
    info_steps->setStyleSheet("color: #8f8f8f; font-size: 11px; line-height: 1.5; border: none; background: transparent;");

    info_layout->addWidget(info_title);
    info_layout->addWidget(info_steps);

    content_layout->addWidget(info_box);
    content_layout->addStretch();
    scroll_area->setWidget(scroll_content);
    main_layout->addWidget(scroll_area);
}

bool transcript_tab::eventFilter(QObject* obj, QEvent* event) {
    if (obj == this) {
        if (event->type() == QEvent::Enter) scroll_area->setStyleSheet(TRAN_SCROLLBAR_STYLE);
        else if (event->type() == QEvent::Leave) scroll_area->setStyleSheet(TRAN_HIDDEN_SCROLLBAR);
    }
    return QWidget::eventFilter(obj, event);
}

// === ORACLE JOKE GENERATOR ===
void transcript_tab::on_oracle_clicked() {
    static const QStringList prophecies = {
        ">> [ORACLE]: \"The raw scan was already clean. You are cleaning thin air.\"",
        ">> [ORACLE]: \"CUDA 13 whispered: 'More VRAM will not fix the plot.'\"",
        ">> [ORACLE]: \"A 4K manga chapter a day keeps the typesetter away.\"",
        ">> [ORACLE]: \"TextBPN++ detected a sound effect: 'ゴゴゴ (MENACING)'.\"",
        ">> [ORACLE]: \"Moebius completed 30 DDIM steps. The void stared back.\"",
        ">> [ORACLE]: \"Error 0xDEADBEEF: Arcadian Architect spilled coffee on the grid.\""
    };

    int idx = QRandomGenerator::global()->bounded(prophecies.size());
    text_area->appendPlainText(prophecies[idx]);
}

void transcript_tab::on_clear_clicked() {
    text_area->clear();
}

void transcript_tab::append_transcript_text(const QString& text) {
    text_area->appendPlainText(text);
}

QString transcript_tab::get_transcript_text() const {
    return text_area->toPlainText();
}

QPixmap transcript_tab::recolor_svg(const QString& path, const QString& hex_color) {
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
    painter.drawPixmap(0, 0, original);
    painter.setCompositionMode(QPainter::CompositionMode_SourceIn);
    painter.fillRect(recolored.rect(), QColor(hex_color));
    painter.end();
    return recolored;
}

QLabel* transcript_tab::create_section_header(const QString& title) {
    QLabel* label = new QLabel(title, this);
    label->setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold; background: transparent;");
    return label;
}

QFrame* transcript_tab::create_separator() {
    QFrame* line = new QFrame(this);
    line->setFrameShape(QFrame::HLine);
    line->setStyleSheet("color: #3c3c3c; margin: 4px 0px;");
    return line;
}