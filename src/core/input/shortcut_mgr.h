#ifndef CORE_INPUT_SHORTCUT_MGR_H
#define CORE_INPUT_SHORTCUT_MGR_H

#include <QObject>
#include <QWidget>
#include <QShortcut>
#include <QPointer>

class shortcut_mgr : public QObject {
    Q_OBJECT

public:
    explicit shortcut_mgr(QWidget* main_window);
    ~shortcut_mgr() override;

signals:
    // === HISTORY SIGNALS ===
    void sig_undo_image();
    void sig_redo_image();
    void sig_undo_mask();
    void sig_redo_mask();

    // === AI EXECUTION SIGNALS ===
    void sig_run_ocr();
    void sig_run_inpaint();

    // === TOOL SELECTION SIGNALS ===
    void sig_tool_move();
    void sig_tool_brush();
    void sig_tool_rect();
    void sig_tool_lasso();
    void sig_tool_wand();

    // === MODE SIGNALS ===
    void sig_mode_paint();
    void sig_mode_erase();

    // === MODIFIER SIGNALS ===
    void sig_decrease_value();
    void sig_increase_value();
    void sig_pan_started();
    void sig_pan_ended();

    // === SYSTEM SIGNALS ===
    void sig_export();
    void sig_open();
    void sig_open_folder();
    void sig_zoom_in();
    void sig_zoom_out();
    void sig_zoom_fit();
    void sig_toggle_ui();

    // === GALLERY PAGE NAVIGATION ===
    void sig_page_next(); // PageDown: next page in the gallery
    void sig_page_prev(); // PageUp: previous page in the gallery

protected:
    bool eventFilter(QObject* watched, QEvent* event) override;

private:
    void register_shortcuts(QWidget* parent);
    QShortcut* create_shortcut(const QString& sequence, QWidget* parent,
        Qt::ShortcutContext context = Qt::WindowShortcut);
    bool is_editable_control(QWidget* widget) const;
    bool is_in_main_window(QWidget* widget) const;
    void end_space_pan();

    QPointer<QWidget> m_main_window;
    bool m_space_pressed = false;
};

#endif // CORE_INPUT_SHORTCUT_MGR_H