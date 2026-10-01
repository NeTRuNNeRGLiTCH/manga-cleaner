#ifndef STUDIO_WIDGETS_CANVAS_WIDGET_H
#define STUDIO_WIDGETS_CANVAS_WIDGET_H

#include <QWidget>
#include <QPixmap>
#include <QPainter>
#include <QMouseEvent>
#include <QWheelEvent>
#include <QResizeEvent>
#include <QPoint>
#include <QPolygon>
#include <QColor>
#include <opencv2/opencv.hpp>

class session_data;
class history_stack;
class QColorDialog;
class QPushButton;

enum class CanvasTool {
    Move,
    Brush,
    Rect,
    Lasso,
    Wand,
    Color   // paints real pixels (cleaning touch-up), not the mask
};

class canvas_widget : public QWidget {
    Q_OBJECT

public:
    explicit canvas_widget(QWidget* parent = nullptr);
    ~canvas_widget() = default;

    void set_backend(session_data* session, history_stack* history);

    // === TOOL MODIFIERS ===
    void set_tool(CanvasTool tool);
    void set_erase_mode(bool is_erase);
    void set_brush_size(int size);
    void set_wand_tolerance(int tol);
    void set_draw_color(const QColor& color);
    QColor draw_color() const { return m_brush_color; }

public slots:
    void zoom_in();
    void zoom_out();
    void zoom_fit();

signals:
    // Emitted when user dynamically changes brush size via Alt + RMB drag
    void brush_size_changed(int new_size);

protected:
    void paintEvent(QPaintEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;
    void wheelEvent(QWheelEvent* event) override;
    void resizeEvent(QResizeEvent* event) override;
    void keyPressEvent(QKeyEvent* event) override;
    void keyReleaseEvent(QKeyEvent* event) override;
    bool eventFilter(QObject* watched, QEvent* event) override;

    void update_canvas_cursor();

private:
    session_data* m_session;
    history_stack* m_history;

    QPixmap m_default_background;

    // === CANVAS VIEW STATE ===
    double m_zoom_factor = 1.0;
    QPointF m_offset = QPointF(0, 0);

    // === TOOL STATE ===
    CanvasTool m_current_tool = CanvasTool::Brush;
    bool m_is_erase_mode = false;
    int m_brush_size = 20;
    int m_wand_tolerance = 30;
    QColor m_brush_color = QColor(0, 0, 0); // Color tool fill color

    // Color tool pickers (created lazily on first use)
    QColorDialog* m_color_dialog = nullptr;
    QPushButton* m_color_wheel_button = nullptr;

    // Color tool stroke: paint into a private copy while dragging, commit the
    // whole stroke to the session + history once on release.
    cv::Mat m_paint_img;      // working copy being painted into
    cv::Mat m_paint_before;   // pre-stroke snapshot for undo
    QPoint m_paint_last;      // last dab position (for connected lines)
    int m_paint_min_x = 0, m_paint_max_x = -1, m_paint_min_y = 0, m_paint_max_y = -1;

    void open_color_pickers(const QPoint& global_pos);
    void paint_dab(const QPoint& from, const QPoint& to);
    void commit_color_stroke();

    // === INTERACTION STATE ===
    bool m_is_drawing = false;
    bool m_is_panning = false;
    bool m_space_held = false;

    // Alt+RMB Brush Resizing state
    bool m_is_resizing_brush = false;
    int m_start_brush_size = 20;
    QPoint m_start_resize_pos;

    QPoint m_last_mouse_pos;
    QPoint m_start_mouse_pos;
    QPolygon m_current_polygon;

    cv::Mat m_temp_mask;
    cv::Mat m_mask_before_stroke; // Mask state before the active stroke began (for undo)

    // === MATH HELPERS ===
    QPoint map_to_image(const QPoint& screen_pos);
    void clamp_offset(); // Prevents scrolling to infinity

    // Commits just the painted band of m_temp_mask to the session (see
    // session_data::set_mask_patch) so a brush stroke never copies the whole page.
    void push_mask_patch(const QPoint& from, const QPoint& to);
};

#endif // STUDIO_WIDGETS_CANVAS_WIDGET_H