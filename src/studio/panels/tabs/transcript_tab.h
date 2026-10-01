#ifndef TRANSCRIPT_TAB_H
#define TRANSCRIPT_TAB_H

#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QScrollArea>
#include <QPlainTextEdit>
#include <QEvent>

class TranscriptEditor;

// ==========================================================
// CUSTOM C++ WIDGET: Unselectable Line Number Margin
// ==========================================================
class LineNumberArea : public QWidget {
    Q_OBJECT
public:
    LineNumberArea(TranscriptEditor* editor);
    QSize sizeHint() const override;
protected:
    void paintEvent(QPaintEvent* event) override;
private:
    TranscriptEditor* codeEditor;
};

// ==========================================================
// CUSTOM C++ WIDGET: Code-Editor Style Text Area
// ==========================================================
class TranscriptEditor : public QPlainTextEdit {
    Q_OBJECT
public:
    explicit TranscriptEditor(QWidget* parent = nullptr);
    void lineNumberAreaPaintEvent(QPaintEvent* event);
    int lineNumberAreaWidth();

protected:
    void resizeEvent(QResizeEvent* event) override;

private slots:
    void updateLineNumberAreaWidth(int newBlockCount);
    void updateLineNumberArea(const QRect& rect, int dy);

private:
    QWidget* lineNumberArea;
};

// ==========================================================
// THE MAIN TAB (Easter Egg Edition)
// ==========================================================
class transcript_tab : public QWidget {
    Q_OBJECT

public:
    explicit transcript_tab(QWidget* parent = nullptr);
    ~transcript_tab() = default;

    void append_transcript_text(const QString& text);
    QString get_transcript_text() const;

protected:
    bool eventFilter(QObject* obj, QEvent* event) override;

private slots:
    void on_oracle_clicked();
    void on_clear_clicked();

private:
    void setup_ui();
    QLabel* create_section_header(const QString& title);
    QFrame* create_separator();
    QPixmap recolor_svg(const QString& path, const QString& hex_color);

    QScrollArea* scroll_area;
    QWidget* scroll_content;

    TranscriptEditor* text_area;
    QPushButton* btn_oracle;
    QPushButton* btn_clear;
};

#endif // TRANSCRIPT_TAB_H