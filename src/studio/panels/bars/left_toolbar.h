#ifndef LEFT_TOOLBAR_H
#define LEFT_TOOLBAR_H

#include <QWidget>
#include <QPushButton>
#include <QVBoxLayout>
#include <QSlider>
#include <QLabel>
#include <QButtonGroup>
#include <QFrame>

class left_toolbar : public QWidget {
    Q_OBJECT

public:
    explicit left_toolbar(QWidget* parent = nullptr);
    ~left_toolbar() = default;

public slots:
    // This allows the canvas (Alt+RMB) to update the slider visually
    void set_brush_size(int size);
    void adjust_brush_size(int delta);
    void set_mode(const QString& mode);
    void set_tool(const QString& tool);

signals:
    // === OUTGOING SIGNALS ===
    void mode_changed(const QString& mode);
    void tool_changed(const QString& tool);
    void brush_size_changed(int size);
    void wand_tolerance_changed(int tolerance);

private slots:
    // === INTERNAL LOGIC SLOTS ===
    void on_mode_clicked(int id);
    void on_tool_clicked(int id);
    void update_slider_visibility();
    void update_brush_label(int value);
    void update_wand_label(int value);

private:
    // === UI SETUP ===
    void setup_ui();
    QPushButton* create_tool_button(const QString& icon_path, const QString& tooltip, const QString& active_color);
    QFrame* create_separator();

    // Photoshop-style tool memory (restore the tool used before Hand mode)
    void remember_active_tool();
    void clear_tool_selection();
    void restore_last_tool();

    QString m_last_tool = "Brush";

    // === WIDGETS ===
    QButtonGroup* mode_group;
    QButtonGroup* tool_group;

    QPushButton* btn_move;
    QPushButton* btn_paint;
    QPushButton* btn_erase;

    QPushButton* btn_brush;
    QPushButton* btn_rect;
    QPushButton* btn_lasso;
    QPushButton* btn_wand;
    QPushButton* btn_color; // paints real pixels (cleaning touch-up)

    QWidget* brush_slider_container;
    QSlider* brush_slider;
    QLabel* brush_label;

    QWidget* wand_slider_container;
    QSlider* wand_slider;
    QLabel* wand_label;
};

#endif // LEFT_TOOLBAR_H