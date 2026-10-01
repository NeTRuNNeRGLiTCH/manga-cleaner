#include "canvas_widget.h"
#include "src/core/state/session_data.h"
#include "src/core/state/history_stack.h"
#include "src/core/image_ops/cv_painter.h"
#include <algorithm>
#include <cstdlib>
#include <QKeyEvent>
#include <QColorDialog>
#include <QPushButton>
#include <QHBoxLayout>

canvas_widget::canvas_widget(QWidget* parent) : QWidget(parent), m_session(nullptr), m_history(nullptr) {
    m_default_background.load(":/axis_cleaner/assets/main.png");
    this->setStyleSheet("background-color: #2b2b2b;");
    this->setMouseTracking(true);
    this->setFocusPolicy(Qt::StrongFocus);
    if (parent) {
        parent->installEventFilter(this);
    }
}

void canvas_widget::set_backend(session_data* session, history_stack* history) {
    m_session = session;
    m_history = history;
    m_zoom_factor = 1.0;
    m_offset = QPointF(0, 0);
    update();
}

void canvas_widget::set_tool(CanvasTool tool) {
    // Switching tools mid-stroke commits what was painted so far rather than
    // silently discarding the working copy.
    if (m_current_tool == CanvasTool::Color && tool != CanvasTool::Color && !m_paint_img.empty()) {
        commit_color_stroke();
    }
    m_current_tool = tool;
    update_canvas_cursor();
    update();
}

void canvas_widget::set_erase_mode(bool is_erase) {
    m_is_erase_mode = is_erase;
    update();
}

void canvas_widget::set_brush_size(int size) {
    m_brush_size = size;
    update();
}

void canvas_widget::set_wand_tolerance(int tol) {
    m_wand_tolerance = tol;
}

// ==========================================================
// COLOR DRAWING TOOL (real-pixel touch-up, not mask)
// ==========================================================
void canvas_widget::set_draw_color(const QColor& color) {
    if (color.isValid()) m_brush_color = color;
}

void canvas_widget::open_color_pickers(const QPoint& global_pos) {
    if (!m_color_wheel_button) {
        m_color_wheel_button = new QPushButton(nullptr);
        m_color_wheel_button->setWindowFlags(Qt::Popup | Qt::FramelessWindowHint | Qt::NoDropShadowWindowHint);
        m_color_wheel_button->setFixedSize(28, 28);
        m_color_wheel_button->setCursor(Qt::PointingHandCursor);
        m_color_wheel_button->setToolTip("Open color picker");

        // A wheel-of-color icon: a small rainbow ring rendered in-code.
        QPixmap wheel(24, 24);
        wheel.fill(Qt::transparent);
        {
            QPainter p(&wheel);
            p.setRenderHint(QPainter::Antialiasing);
            QConicalGradient grad(12, 12, 0);
            grad.setColorAt(0.00, QColor(255, 0, 0));
            grad.setColorAt(0.16, QColor(255, 255, 0));
            grad.setColorAt(0.33, QColor(0, 255, 0));
            grad.setColorAt(0.50, QColor(0, 255, 255));
            grad.setColorAt(0.66, QColor(0, 0, 255));
            grad.setColorAt(0.83, QColor(255, 0, 255));
            grad.setColorAt(1.00, QColor(255, 0, 0));
            p.setPen(QPen(QBrush(grad), 5));
            p.drawEllipse(4, 4, 16, 16);
        }
        m_color_wheel_button->setIcon(QIcon(wheel));
        m_color_wheel_button->setIconSize(QSize(24, 24));

        connect(m_color_wheel_button, &QPushButton::clicked, this, [this]() {
            const QColor chosen = QColorDialog::getColor(m_brush_color, nullptr, "Pick Draw Color");
            if (chosen.isValid()) set_draw_color(chosen);
            m_color_wheel_button->close();
        });
    }

    m_color_wheel_button->move(global_pos);
    m_color_wheel_button->show();
    m_color_wheel_button->raise();
}

void canvas_widget::paint_dab(const QPoint& from, const QPoint& to) {
    if (m_paint_img.empty()) return;

    // Draw on the session working copy in image space. The session may hold RGB
    // or RGBA (transparent PNGs): keep alpha opaque so dabs don't punch holes.
    const cv::Scalar color = (m_paint_img.channels() == 4)
        ? cv::Scalar(m_brush_color.red(), m_brush_color.green(), m_brush_color.blue(), 255)
        : cv::Scalar(m_brush_color.red(), m_brush_color.green(), m_brush_color.blue());
    const cv::Point from_pt(from.x(), from.y());
    const cv::Point to_pt(to.x(), to.y());
    const int radius = std::max(1, m_brush_size / 2);
    cv::line(m_paint_img, from_pt, to_pt, color, radius * 2, cv::LINE_AA, 0);
    cv::circle(m_paint_img, to_pt, radius, color, -1, cv::LINE_AA);

    m_paint_min_x = std::min(m_paint_min_x, std::min(from.x(), to.x()) - radius - 2);
    m_paint_max_x = std::max(m_paint_max_x, std::max(from.x(), to.x()) + radius + 2);
    m_paint_min_y = std::min(m_paint_min_y, std::min(from.y(), to.y()) - radius - 2);
    m_paint_max_y = std::max(m_paint_max_y, std::max(from.y(), to.y()) + radius + 2);
}

void canvas_widget::commit_color_stroke() {
    if (m_paint_img.empty() || !m_session) return;

    m_paint_min_x = std::max(0, m_paint_min_x);
    m_paint_min_y = std::max(0, m_paint_min_y);
    m_paint_max_x = std::min(m_paint_img.cols - 1, m_paint_max_x);
    m_paint_max_y = std::min(m_paint_img.rows - 1, m_paint_max_y);

    if (m_paint_max_x < m_paint_min_x || m_paint_max_y < m_paint_min_y) {
        m_paint_img.release();
        m_paint_before.release();
        return;
    }

    const cv::Rect dirty(m_paint_min_x, m_paint_min_y,
        m_paint_max_x - m_paint_min_x + 1,
        m_paint_max_y - m_paint_min_y + 1);

    // History first (needs the pre-stroke pixels), then commit to the session.
    // replace_image_keep_mask: painting a touch-up must not wipe the mask.
    if (m_history) {
        m_history->commit_image_patch(dirty, m_paint_before(dirty).clone(), m_paint_img(dirty).clone());
    }
    m_session->replace_image_keep_mask(m_paint_img);

    m_paint_img.release();
    m_paint_before.release();
}

// === INFINITY SCROLL FIX ===
void canvas_widget::clamp_offset() {
    if (!m_session || !m_session->has_active_image()) {
        m_offset = QPointF(0, 0);
        return;
    }

    const cv::Size img_size = m_session->get_image_size();
    double scaled_w = img_size.width * m_zoom_factor;
    double scaled_h = img_size.height * m_zoom_factor;

    // Calculate maximum allowed offset based on window size
    double max_x = std::max(0.0, (scaled_w - this->width()) / 2.0);
    double max_y = std::max(0.0, (scaled_h - this->height()) / 2.0);

    // Lock the camera strictly inside the borders
    m_offset.setX(std::clamp(m_offset.x(), -max_x, max_x));
    m_offset.setY(std::clamp(m_offset.y(), -max_y, max_y));
}

void canvas_widget::resizeEvent(QResizeEvent* event) {
    QWidget::resizeEvent(event);
    clamp_offset();
    update();
}

void canvas_widget::update_canvas_cursor() {
    if (m_space_held) {
        setCursor(m_is_panning ? Qt::ClosedHandCursor : Qt::OpenHandCursor);
    }
    else if (m_is_resizing_brush) {
        setCursor(Qt::SizeHorCursor);
    }
    else if (m_current_tool == CanvasTool::Move) {
        setCursor(m_is_panning ? Qt::ClosedHandCursor : Qt::OpenHandCursor);
    }
    else if (m_current_tool == CanvasTool::Brush) {
        setCursor(Qt::CrossCursor);
    }
    else if (m_current_tool == CanvasTool::Color) {
        setCursor(Qt::CrossCursor);
    }
    else if (m_current_tool == CanvasTool::Rect || m_current_tool == CanvasTool::Lasso || m_current_tool == CanvasTool::Wand) {
        setCursor(Qt::CrossCursor);
    }
    else {
        setCursor(Qt::ArrowCursor);
    }
}

// === RENDERING PIPELINE ===

void canvas_widget::paintEvent(QPaintEvent* event) {
    QPainter painter(this);
    painter.fillRect(rect(), QColor("#2b2b2b"));

    // While Alt+RMB resizing the brush, the size circle IS the cursor.
    if (m_is_resizing_brush) {
        setCursor(Qt::BlankCursor);
    }

    if (m_session && m_session->has_active_image()) {
        painter.save();

        // 1. Move to center of canvas + apply panning offset
        painter.translate(this->width() / 2.0 + m_offset.x(), this->height() / 2.0 + m_offset.y());

        // 2. Scale coordinate system by Zoom Factor
        painter.scale(m_zoom_factor, m_zoom_factor);

        const QImage& img = m_session->get_display_image();
        const QImage& mask = m_session->get_display_mask();

        int img_w = img.width();
        int img_h = img.height();

        // 3. Move image origin to top-left of image space (so (0,0) is centered)
        painter.translate(-img_w / 2.0, -img_h / 2.0);

        // Render base image
        painter.drawImage(0, 0, img);

        // Render mask overlay
        if (!mask.isNull()) {
            painter.drawImage(0, 0, mask);
        }

        // Live preview for active shapes (Rect / Lasso)
        if (m_is_drawing) {
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1, Qt::DashLine));
            painter.setBrush(QColor(155, 89, 255, 40));

            if (m_current_tool == CanvasTool::Rect) {
                QPoint p1 = map_to_image(m_start_mouse_pos);
                QPoint p2 = map_to_image(m_last_mouse_pos);
                painter.drawRect(QRect(p1, p2));
            }
            else if (m_current_tool == CanvasTool::Lasso && !m_current_polygon.isEmpty()) {
                painter.drawPolygon(m_current_polygon);
            }
        }

        painter.restore();
    }
    else {
        if (!m_default_background.isNull()) {
            QPixmap scaled_bg = m_default_background.scaled(this->size(), Qt::KeepAspectRatioByExpanding, Qt::SmoothTransformation);
            painter.setOpacity(0.1);
            painter.drawPixmap((this->width() - scaled_bg.width()) / 2, (this->height() - scaled_bg.height()) / 2, scaled_bg);
        }
    }

    // Draw the Brush Cursor Overlay on top of everything (unscaled by world matrix)
    if ((m_current_tool == CanvasTool::Brush || m_current_tool == CanvasTool::Color || m_is_resizing_brush) && !m_is_panning && this->underMouse()) {
        painter.resetTransform();
        double scaled_radius = (m_brush_size * m_zoom_factor) / 2.0;

        if (m_is_resizing_brush) {
            // Photoshop-style vivid red dynamic brush preview circle
            painter.setPen(QPen(QColor(239, 68, 68, 220), 2));
            painter.setBrush(QBrush(QColor(239, 68, 68, 70)));
            painter.drawEllipse(m_start_resize_pos, static_cast<int>(scaled_radius), static_cast<int>(scaled_radius));
        }
        else {
            QColor cursor_color = (m_current_tool == CanvasTool::Color)
                ? QColor(m_brush_color.red(), m_brush_color.green(), m_brush_color.blue(), 200)
                : (m_is_erase_mode ? QColor(255, 89, 89, 120) : QColor(155, 89, 255, 120));
            painter.setPen(QPen(cursor_color, 1.5));
            painter.setBrush(Qt::NoBrush);
            painter.drawEllipse(m_last_mouse_pos, static_cast<int>(scaled_radius), static_cast<int>(scaled_radius));
        }
    }
}

// === MASK COMMIT (REGION-ONLY) ===
void canvas_widget::push_mask_patch(const QPoint& from, const QPoint& to) {
    if (!m_session || m_temp_mask.empty()) return;

    const int radius = m_brush_size / 2 + 2; // +2 px covers the anti-aliased stroke edge
    const cv::Rect stroke_rect(
        std::min(from.x(), to.x()) - radius,
        std::min(from.y(), to.y()) - radius,
        std::abs(to.x() - from.x()) + radius * 2,
        std::abs(to.y() - from.y()) + radius * 2);

    const cv::Rect safe = stroke_rect & cv::Rect(0, 0, m_temp_mask.cols, m_temp_mask.rows);
    if (safe.width <= 0 || safe.height <= 0) return;

    m_session->set_mask_patch(safe, m_temp_mask(safe));
}

// === MATH: Screen -> Image Coordinates ===
QPoint canvas_widget::map_to_image(const QPoint& screen_pos) {
    if (!m_session || !m_session->has_active_image()) return QPoint(0, 0);

    // Cheap geometry lookup - never deep-copy the page just to map a mouse position.
    const cv::Size img_size = m_session->get_image_size();
    const int img_w = img_size.width;
    const int img_h = img_size.height;

    double x = (screen_pos.x() - this->width() / 2.0 - m_offset.x()) / m_zoom_factor + img_w / 2.0;
    double y = (screen_pos.y() - this->height() / 2.0 - m_offset.y()) / m_zoom_factor + img_h / 2.0;

    return QPoint(static_cast<int>(x), static_cast<int>(y));
}

// === MOUSE INPUT HANDLING ===

void canvas_widget::mousePressEvent(QMouseEvent* event) {
    if (!m_session || !m_session->has_active_image()) return;

    if (event->button() == Qt::RightButton && (event->modifiers() & Qt::AltModifier)) {
        m_is_resizing_brush = true;
        m_start_resize_pos = event->pos();
        m_start_brush_size = m_brush_size;
        setCursor(Qt::SizeHorCursor);
        update();
        return;
    }

    // Right-click with the Color tool opens the quick color picker.
    if (event->button() == Qt::RightButton && m_current_tool == CanvasTool::Color) {
        open_color_pickers(event->globalPosition().toPoint());
        return;
    }

    if (event->button() == Qt::LeftButton && m_current_tool == CanvasTool::Color) {
        // Paint on a private working copy; commit once on release.
        m_paint_img = m_session->get_current_image().clone();
        m_paint_before = m_paint_img.clone();
        m_paint_min_x = m_paint_img.cols; m_paint_max_x = -1;
        m_paint_min_y = m_paint_img.rows; m_paint_max_y = -1;
        m_last_mouse_pos = event->pos(); // keep the brush ring glued to the mouse
        m_paint_last = map_to_image(event->pos());
        paint_dab(m_paint_last, m_paint_last);
        update();
        return;
    }

    if (event->button() == Qt::MiddleButton || m_current_tool == CanvasTool::Move || (m_space_held && event->button() == Qt::LeftButton)) {
        m_is_panning = true;
        m_last_mouse_pos = event->pos();
        setCursor(Qt::ClosedHandCursor);
        return;
    }
    else if (event->button() == Qt::LeftButton) {
        m_is_drawing = true;
        m_start_mouse_pos = event->pos();
        m_last_mouse_pos = event->pos();

        m_temp_mask = m_session->get_current_mask().clone();
        // Snapshot the pre-stroke mask NOW: by release time the session already
        // holds the new mask, so undo must restore this copy, not re-read session.
        m_mask_before_stroke = m_temp_mask.clone();

        if (m_current_tool == CanvasTool::Lasso) {
            m_current_polygon.clear();
            m_current_polygon << map_to_image(event->pos());
        }
        else if (m_current_tool == CanvasTool::Brush) {
            const QPoint p = map_to_image(event->pos());
            cv_painter::draw_brush(m_temp_mask, p, p, m_brush_size, m_is_erase_mode);
            push_mask_patch(p, p);
            update();
        }
        else if (m_current_tool == CanvasTool::Wand) {
            cv_painter::magic_wand(m_session->get_current_image(), m_temp_mask, map_to_image(event->pos()), m_wand_tolerance, m_is_erase_mode);
            m_session->set_mask(m_temp_mask);
            update();
        }
    }
}

void canvas_widget::mouseMoveEvent(QMouseEvent* event) {
    if (!m_session || !m_session->has_active_image()) return;

    if (m_current_tool == CanvasTool::Color && !m_paint_img.empty()) {
        // The Color branch returns early, so without this the brush cursor ring
        // froze at the press position for the whole stroke.
        m_last_mouse_pos = event->pos();
        const QPoint img_pos = map_to_image(event->pos());
        paint_dab(m_paint_last, img_pos);
        m_paint_last = img_pos;
        update();
        return;
    }

    if (m_is_resizing_brush) {
        int delta_x = event->pos().x() - m_start_resize_pos.x();
        m_brush_size = std::max(1, std::min(300, m_start_brush_size + (delta_x / 2)));
        emit brush_size_changed(m_brush_size);
        m_last_mouse_pos = event->pos();
        setCursor(Qt::SizeHorCursor);
        update();
        return;
    }

    if (m_is_panning) {
        QPoint delta = event->pos() - m_last_mouse_pos;
        m_offset += delta;
        clamp_offset(); // Snap to borders while dragging
        m_last_mouse_pos = event->pos();
        update();
    }
    else if (m_is_drawing) {
        if (m_current_tool == CanvasTool::Brush) {
            const QPoint from = map_to_image(m_last_mouse_pos);
            const QPoint to = map_to_image(event->pos());
            cv_painter::draw_brush(m_temp_mask, from, to, m_brush_size, m_is_erase_mode);
            push_mask_patch(from, to);
        }
        else if (m_current_tool == CanvasTool::Lasso) {
            m_current_polygon << map_to_image(event->pos());
        }
        m_last_mouse_pos = event->pos();
        update();
    }
    else {
        m_last_mouse_pos = event->pos();
        update();
    }
}

void canvas_widget::mouseReleaseEvent(QMouseEvent* event) {
    if (m_is_resizing_brush && event->button() == Qt::RightButton) {
        m_is_resizing_brush = false;
        update_canvas_cursor();
        update();
        return;
    }

    if (m_current_tool == CanvasTool::Color && !m_paint_img.empty() && event->button() == Qt::LeftButton) {
        commit_color_stroke();
        update();
        return;
    }

    if (m_is_panning && (event->button() == Qt::MiddleButton || event->button() == Qt::LeftButton)) {
        m_is_panning = false;
        update_canvas_cursor();
        return;
    }
    else if (m_is_drawing && event->button() == Qt::LeftButton) {
        m_is_drawing = false;

        if (m_current_tool == CanvasTool::Rect) {
            cv_painter::draw_rect(m_temp_mask, map_to_image(m_start_mouse_pos), map_to_image(event->pos()), m_is_erase_mode);
        }
        else if (m_current_tool == CanvasTool::Lasso) {
            cv_painter::draw_lasso(m_temp_mask, m_current_polygon, m_is_erase_mode);
            m_current_polygon.clear();
        }

        if (m_current_tool != CanvasTool::Wand && m_current_tool != CanvasTool::Brush) {
            m_session->set_mask(m_temp_mask);
        }

        // Undo must revert to the mask as it was BEFORE the stroke started.
        m_history->commit_mask_state(m_mask_before_stroke, m_temp_mask);
        update();
    }
}

void canvas_widget::wheelEvent(QWheelEvent* event) {
    if (!m_session || !m_session->has_active_image()) return;

    if (event->modifiers() & Qt::AltModifier) {
        // Alt+wheel zooms. Take whichever axis carries the delta: some drivers/
        // devices shift wheel motion to angleDelta().x() (which is why Alt+scroll
        // up appeared dead while scroll down still zoomed out).
        const QPoint delta = event->angleDelta();
        const int steps = (delta.y() != 0) ? delta.y() : delta.x();
        const double new_zoom = std::max(0.1, std::min(m_zoom_factor * ((steps > 0) ? 1.15 : 0.85), 10.0));
        if (new_zoom == m_zoom_factor) { update(); return; }

        // Anchor the zoom at the cursor: the widget keeps the image point under
        // the mouse fixed, so the page never drifts downward while zooming.
        // Widget transform: screen = center + offset + (img - img_center) * zoom.
        const QPointF cur = event->position();
        const double wx = cur.x() - width() / 2.0;
        const double wy = cur.y() - height() / 2.0;
        const double rel_x = (wx - m_offset.x()) / m_zoom_factor; // image px, relative to image center
        const double rel_y = (wy - m_offset.y()) / m_zoom_factor;

        m_zoom_factor = new_zoom;
        m_offset = QPointF(wx - rel_x * m_zoom_factor, wy - rel_y * m_zoom_factor);
        clamp_offset(); // Prevent zooming out of bounds
    }
    else {
        m_offset += QPointF(event->angleDelta().x(), event->angleDelta().y());
        clamp_offset(); // Prevent normal scrolling out of bounds
    }

    update();
}

void canvas_widget::keyPressEvent(QKeyEvent* event) {
    if (event->key() == Qt::Key_Space && !event->isAutoRepeat()) {
        m_space_held = true;
        update_canvas_cursor();
        event->accept();
        return;
    }
    QWidget::keyPressEvent(event);
}

void canvas_widget::keyReleaseEvent(QKeyEvent* event) {
    if (event->key() == Qt::Key_Space && !event->isAutoRepeat()) {
        m_space_held = false;
        if (!m_is_panning) {
            update_canvas_cursor();
        }
        event->accept();
        return;
    }
    QWidget::keyReleaseEvent(event);
}

bool canvas_widget::eventFilter(QObject* watched, QEvent* event) {
    if (event->type() == QEvent::KeyPress) {
        QKeyEvent* keyEvent = static_cast<QKeyEvent*>(event);
        if (keyEvent->key() == Qt::Key_Space && !keyEvent->isAutoRepeat()) {
            m_space_held = true;
            update_canvas_cursor();
            return false;
        }
    }
    else if (event->type() == QEvent::KeyRelease) {
        QKeyEvent* keyEvent = static_cast<QKeyEvent*>(event);
        if (keyEvent->key() == Qt::Key_Space && !keyEvent->isAutoRepeat()) {
            m_space_held = false;
            if (!m_is_panning) {
                update_canvas_cursor();
            }
            return false;
        }
    }
    return QWidget::eventFilter(watched, event);
}

void canvas_widget::zoom_in() {
    m_zoom_factor = std::min(10.0, m_zoom_factor * 1.15);
    clamp_offset();
    update();
}

void canvas_widget::zoom_out() {
    m_zoom_factor = std::max(0.1, m_zoom_factor * 0.85);
    clamp_offset();
    update();
}

void canvas_widget::zoom_fit() {
    m_zoom_factor = 1.0;
    m_offset = QPointF(0, 0);
    clamp_offset();
    update();
}