#ifndef WIZARD_TAB_H
#define WIZARD_TAB_H

#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QScrollArea>
#include <QEvent>
#include <QPainter>
#include <QMouseEvent>

// ================================================================
// CUSTOM C++ WIDGET: WizardToggle
// ================================================================
class WizardToggle : public QWidget {
    Q_OBJECT
public:
    explicit WizardToggle(bool default_state = false, QWidget* parent = nullptr);
    bool isChecked() const;

signals:
    void toggled(bool checked);

protected:
    void mouseReleaseEvent(QMouseEvent* event) override;
    void paintEvent(QPaintEvent* event) override;

private:
    bool m_checked;
};

// ==========================================================
// Wizard Right-Panel Tab
// ==========================================================
class wizard_tab : public QWidget {
    Q_OBJECT

public:
    explicit wizard_tab(QWidget* parent = nullptr);
    ~wizard_tab() = default;

    // Public methods to update the detailed status box from the backend
    void update_status_total(int total);
    void update_status_processed(int processed);
    void update_status_failed(int failed);
    void update_status_task(const QString& task);

signals:
    // === OUTGOING ACTION SIGNALS ===
    void run_wizard_requested(bool scan_transparency);
    void stop_wizard_requested();

protected:
    // === EVENT FILTER FOR SCROLLBAR (Jiggle Effect) ===
    bool eventFilter(QObject* obj, QEvent* event) override;

private slots:
    void on_scan_transparency_toggled(bool checked);

private:
    // === UI SETUP ===
    void setup_ui();
    QLabel* create_section_header(const QString& title);
    QFrame* create_separator();
    QPixmap recolor_svg(const QString& path, const QString& hex_color);
    QWidget* create_status_row(const QString& label, QLabel*& value_ptr);

    // === WIDGETS ===
    QScrollArea* scroll_area;
    QWidget* scroll_content;

    WizardToggle* toggle_scan_transparency;

    QPushButton* btn_run;
    QPushButton* btn_stop;

    QLabel* val_total;
    QLabel* val_processed;
    QLabel* val_failed;
    QLabel* val_remaining;
    QLabel* val_task;
    QLabel* val_transparency_scan;
};

#endif // WIZARD_TAB_H