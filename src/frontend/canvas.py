import os
import math
import cv2
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, 
                             QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsTextItem,
                             QLabel, QStyle)
from PySide6.QtGui import (QPixmap, QImage, QPainter, QPen, QColor, QBrush, 
                         QPainterPath, QIcon, QCursor, QFont, QTextOption, QTextCursor)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
import numpy as np
from src.utils.paths import Paths

#/////////////////////////////////#
#    INTERACTIVE TEXT ITEM        #
#/////////////////////////////////#

class MangaTextItem(QGraphicsTextItem):
    HANDLE_SIZE = 8.0
    ROTATE_OFFSET = 26.0

    def __init__(self, text="Text", font_family="Arial", font_size=32, 
                 text_color=QColor(0, 0, 0), stroke_enabled=False,
                 stroke_color=QColor(255, 255, 255), stroke_width=3, stroke_opacity=100,
                 bold=False, italic=False, align_center=True,
                 box_width=-1.0, rotation_angle=0.0):
        super().__init__(text)
        self.font_family = font_family
        self.font_size = int(font_size)
        self.text_color = QColor(text_color)
        self.stroke_enabled = bool(stroke_enabled)
        self.stroke_color = QColor(stroke_color)
        self.stroke_width = int(stroke_width)
        self.stroke_opacity = int(stroke_opacity)
        self.is_bold = bool(bold)
        self.is_italic = bool(italic)
        self.align_center = bool(align_center)
        self.box_width = float(box_width)

        self.setFlags(
            QGraphicsTextItem.ItemIsMovable |
            QGraphicsTextItem.ItemIsSelectable |
            QGraphicsTextItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(500)

        self.document().contentsChanged.connect(self._on_contents_changed)
        self.update_style()
        if rotation_angle != 0.0:
            self.set_rotation_angle(rotation_angle)

    def _on_contents_changed(self):
        self.prepareGeometryChange()
        if self.box_width <= 0:
            self.document().adjustSize()
        self.update_transform_origin()
        self.update()
        self._notify_modified()
        self._notify_list_updated()

    def _notify_modified(self):
        if self.scene():
            views = self.scene().views()
            if views and hasattr(views[0], "text_modified"):
                views[0].text_modified.emit()

    def _notify_style_synced(self):
        if self.scene():
            views = self.scene().views()
            if views and hasattr(views[0], "text_selected"):
                views[0].text_selected.emit(self)

    def _notify_list_updated(self):
        if self.scene():
            views = self.scene().views()
            if views and hasattr(views[0], "texts_list_changed"):
                views[0].texts_list_changed.emit()

    def update_transform_origin(self):
        rect = super().boundingRect()
        self.setTransformOriginPoint(rect.center())

    def set_rotation_angle(self, angle: float):
        norm = ((angle + 180.0) % 360.0) - 180.0
        self.update_transform_origin()
        self.setRotation(norm)
        self.update()
        self._notify_modified()

    def reset_box_width(self):
        self.prepareGeometryChange()
        self.box_width = -1.0
        self.setTextWidth(-1.0)
        self.document().adjustSize()
        self.update_transform_origin()
        self.update()
        self._notify_modified()

    def update_style(self):
        self.prepareGeometryChange()
        font = QFont(self.font_family, max(6, int(self.font_size)))
        font.setBold(self.is_bold)
        font.setItalic(self.is_italic)
        self.setFont(font)
        self.setDefaultTextColor(self.text_color)

        opt = self.document().defaultTextOption()
        opt.setAlignment(Qt.AlignCenter if self.align_center else Qt.AlignLeft)
        opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(opt)

        if self.box_width > 20.0:
            self.setTextWidth(self.box_width)
        else:
            self.setTextWidth(-1.0)
            self.document().adjustSize()

        self.update_transform_origin()
        self.update()

    def boundingRect(self):
        rect = super().boundingRect()
        sw = self.stroke_width if self.stroke_enabled else 0
        pad = max(sw * 2 + 8, 16)
        return rect.adjusted(-pad, -(pad + self.ROTATE_OFFSET + 6), pad, pad)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def _text_rect(self):
        return super().boundingRect()

    def _get_handles(self):
        r = self._text_rect()
        hs = self.HANDLE_SIZE
        half = hs / 2.0

        cx, cy = r.center().x(), r.center().y()
        rot_pt = QPointF(cx, r.top() - self.ROTATE_OFFSET)

        return {
            "ROTATE": QRectF(rot_pt.x() - half - 2, rot_pt.y() - half - 2, hs + 4, hs + 4),
            "TL": QRectF(r.left() - half, r.top() - half, hs, hs),
            "TR": QRectF(r.right() - half, r.top() - half, hs, hs),
            "BL": QRectF(r.left() - half, r.bottom() - half, hs, hs),
            "BR": QRectF(r.right() - half, r.bottom() - half, hs, hs),
            "L": QRectF(r.left() - half, cy - half, hs, hs),
            "R": QRectF(r.right() - half, cy - half, hs, hs),
        }

    def hit_test_handle(self, local_pos: QPointF):
        if not self.isSelected() or (self.textInteractionFlags() & Qt.TextEditorInteraction):
            return None
        for name, rect in self._get_handles().items():
            if rect.adjusted(-6, -6, 6, 6).contains(local_pos):
                return name
        return None

    def enter_edit_mode(self):
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFocus(Qt.MouseFocusReason)
        cursor = self.textCursor()
        cursor.select(QTextCursor.Document)
        self.setTextCursor(cursor)
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.enter_edit_mode()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        if self.box_width <= 0:
            self.document().adjustSize()
        self.update_transform_origin()
        super().focusOutEvent(event)
        if not self.toPlainText().strip() and self.scene():
            views = self.scene().views()
            if views and hasattr(views[0], "remove_text_item"):
                views[0].remove_text_item(self)
        else:
            self._notify_list_updated()

    def itemChange(self, change, value):
        if change == QGraphicsTextItem.ItemPositionHasChanged and self.scene():
            self._notify_modified()
        return super().itemChange(change, value)

    def _build_text_vector_path(self) -> QPainterPath:
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        doc = self.document()
        margin = doc.documentMargin()
        
        block = doc.begin()
        while block.isValid():
            layout = block.layout()
            if layout:
                block_pos = layout.position()
                for i in range(layout.lineCount()):
                    line = layout.lineAt(i)
                    line_text = block.text()[line.textStart():line.textStart() + line.textLength()]
                    if line_text.strip():
                        x = margin + block_pos.x() + line.naturalTextRect().x()
                        y = margin + block_pos.y() + line.y() + line.ascent()
                        path.addText(QPointF(x, y), self.font(), line_text)
            block = block.next()
        return path

    def paint(self, painter, option, widget):
        opt = option
        opt.state &= ~QStyle.State_Selected
        opt.state &= ~QStyle.State_HasFocus

        is_editing = bool(self.textInteractionFlags() & Qt.TextEditorInteraction)
        has_text = bool(self.toPlainText().strip())

        if self.stroke_enabled and self.stroke_width > 0 and has_text:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            
            text_path = self._build_text_vector_path()
            s_color = QColor(self.stroke_color)
            s_color.setAlphaF(max(0.0, min(1.0, self.stroke_opacity / 100.0)))

            pen = QPen(s_color, self.stroke_width * 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(text_path)

            if not is_editing:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(self.text_color))
                painter.drawPath(text_path)
            painter.restore()

            if is_editing:
                super().paint(painter, opt, widget)
        else:
            super().paint(painter, opt, widget)

        if widget is not None:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            r = self._text_rect()
            accent = QColor(0, 212, 255, 220)

            if self.isSelected():
                border_pen = QPen(accent, 1.5, Qt.DashLine if is_editing else Qt.SolidLine)
                painter.setPen(border_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(r)

                if not is_editing:
                    handles = self._get_handles()
                    rot_rect = handles["ROTATE"]
                    painter.drawLine(QPointF(r.center().x(), r.top()), rot_rect.center())

                    painter.setPen(QPen(QColor(15, 15, 20), 1.5))
                    painter.setBrush(QBrush(accent))
                    painter.drawEllipse(rot_rect)

                    painter.setPen(QPen(accent, 1.5))
                    painter.setBrush(QBrush(QColor(255, 255, 255)))
                    for k in ("TL", "TR", "BL", "BR"):
                        painter.drawRect(handles[k])

                    painter.setBrush(QBrush(accent))
                    for k in ("L", "R"):
                        painter.drawRect(handles[k])
            else:
                views = self.scene().views() if self.scene() else []
                if views and getattr(views[0], "current_tool", "") == "TEXT":
                    guide_pen = QPen(QColor(0, 212, 255, 110), 1.0, Qt.DotLine)
                    painter.setPen(guide_pen)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(r)

            painter.restore()

    def to_dict(self):
        return {
            "text": self.toPlainText(),
            "x": self.pos().x(),
            "y": self.pos().y(),
            "font_family": self.font_family,
            "font_size": self.font_size,
            "text_color": self.text_color.name(QColor.HexArgb),
            "stroke_enabled": self.stroke_enabled,
            "stroke_color": self.stroke_color.name(QColor.HexArgb),
            "stroke_width": self.stroke_width,
            "stroke_opacity": self.stroke_opacity,
            "bold": self.is_bold,
            "italic": self.is_italic,
            "align_center": self.align_center,
            "box_width": self.box_width,
            "rotation": self.rotation()
        }

    @classmethod
    def from_dict(cls, data):
        item = cls(
            text=data.get("text", "Text"),
            font_family=data.get("font_family", "Arial"),
            font_size=data.get("font_size", 32),
            text_color=QColor(data.get("text_color", "#000000")),
            stroke_enabled=data.get("stroke_enabled", data.get("stroke_width", 0) > 0),
            stroke_color=QColor(data.get("stroke_color", "#ffffff")),
            stroke_width=data.get("stroke_width", 3),
            stroke_opacity=data.get("stroke_opacity", 100),
            bold=data.get("bold", False),
            italic=data.get("italic", False),
            align_center=data.get("align_center", True),
            box_width=data.get("box_width", -1.0),
            rotation_angle=data.get("rotation", 0.0)
        )
        item.setPos(data.get("x", 0), data.get("y", 0))
        item.update_transform_origin()
        return item


#/////////////////////////////////#
#   MULTI-TOOL CANVAS ENGINE      #
#/////////////////////////////////#

class MangaCanvas(QGraphicsView):
    mask_changed = Signal()
    brush_size_changed = Signal(int)
    text_selected = Signal(object)
    text_modified = Signal()
    texts_list_changed = Signal()
    image_patch_created = Signal(int, int, object)
    clean_color_picked = Signal(QColor)

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        grid_size = 10
        checkerboard = QPixmap(grid_size * 2, grid_size * 2)
        checkerboard.fill(QColor(255, 255, 255))
        painter = QPainter(checkerboard)
        painter.fillRect(0, 0, grid_size, grid_size, QColor(200, 200, 200))
        painter.fillRect(grid_size, grid_size, grid_size, grid_size, QColor(200, 200, 200))
        painter.end()
        self.setBackgroundBrush(QBrush(checkerboard))

        self.image_item = QGraphicsPixmapItem()
        self.mask_item = QGraphicsPixmapItem()
        self.mask_item.setOpacity(60 / 100.0)
        self.scene.addItem(self.image_item)
        self.scene.addItem(self.mask_item)

        self.cursor_item = QGraphicsEllipseItem()
        self.cursor_item.setZValue(1000)
        self.cursor_item.hide()
        self.scene.addItem(self.cursor_item)

        self.current_tool = "NONE"
        self.brush_size = 40
        self.is_drawing = False
        self.is_locked = False  
        self.is_resizing_brush = False
        self.resize_start_pos = None
        self.resize_start_size = 40
        self.resize_start_cursor_pos = None

        self.manual_clean_color = QColor(255, 255, 255)
        self._stroke_pre_img = None
        self._stroke_min_x = 0
        self._stroke_min_y = 0
        self._stroke_max_x = 0
        self._stroke_max_y = 0
        
        # Default text configuration
        self.text_items = []
        self.pending_texts = []  # Unplaced dialogue strings from .txt script
        self.default_font_family = "Arial"
        self.default_font_size = 32
        self.default_text_color = QColor(0, 0, 0)
        self.default_stroke_enabled = False
        self.default_stroke_color = QColor(255, 255, 255)
        self.default_stroke_width = 3
        self.default_stroke_opacity = 100
        self.default_bold = False
        self.default_italic = False
        self.default_align_center = True

        self._active_gizmo_item = None
        self._active_gizmo_mode = None
        self._gizmo_start_font_size = 32
        self._gizmo_start_box_width = -1.0
        self._gizmo_start_dist = 1.0

        self.last_pt = QPointF()
        self.start_pt = QPointF()
        self.last_drawn_pt = None
        self.lasso_path = QPainterPath()
        self.poly_points = []
        self.preview_item = QGraphicsPathItem()
        self.preview_item.setPen(QPen(QColor(255, 0, 0, 200), 2, Qt.DashLine))
        self.scene.addItem(self.preview_item)

        self.lock_overlay = QLabel(self)
        lock_path = os.path.join(Paths.BUNDLE_DIR, "assets", "icon_lock.svg")
        if os.path.exists(lock_path):
            self.lock_overlay.setPixmap(QIcon(lock_path).pixmap(48, 48))
        self.lock_overlay.setStyleSheet("background: transparent;")
        self.lock_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.lock_overlay.hide()

        self.cv_img = None
        self.mask = None
        self.setMouseTracking(True)
        self.update_cursor_visuals()

    # --- TEXT MANAGEMENT METHODS ---
    def is_editing_text(self):
        focus_item = self.scene.focusItem()
        return isinstance(focus_item, MangaTextItem) and bool(focus_item.textInteractionFlags() & Qt.TextEditorInteraction)

    def on_scene_selection_changed(self):
        selected = [it for it in self.scene.selectedItems() if isinstance(it, MangaTextItem)]
        if selected:
            self.text_selected.emit(selected[0])

    def add_text_item(self, scene_pos, initial_text="Text", enter_edit=True):
        item = MangaTextItem(
            text=initial_text,
            font_family=self.default_font_family,
            font_size=self.default_font_size,
            text_color=self.default_text_color,
            stroke_enabled=self.default_stroke_enabled,
            stroke_color=self.default_stroke_color,
            stroke_width=self.default_stroke_width,
            stroke_opacity=self.default_stroke_opacity,
            bold=self.default_bold,
            italic=self.default_italic,
            align_center=self.default_align_center
        )
        self.scene.addItem(item)
        rect = item._text_rect()
        item.setPos(scene_pos.x() - rect.width() / 2, scene_pos.y() - rect.height() / 2)
        item.update_transform_origin()
        self.text_items.append(item)
        
        self.scene.clearSelection()
        item.setSelected(True)
        if enter_edit:
            item.enter_edit_mode()
        self.text_modified.emit()
        self.texts_list_changed.emit()
        return item

    def remove_text_item(self, item):
        if item in self.text_items:
            self.text_items.remove(item)
        if item.scene() == self.scene:
            self.scene.removeItem(item)
        self.text_modified.emit()
        self.texts_list_changed.emit()

    def delete_selected_texts(self):
        for item in list(self.text_items):
            if item.isSelected():
                self.remove_text_item(item)

    def clear_texts(self):
        for item in list(self.text_items):
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        self.text_items.clear()
        self.pending_texts.clear()
        self.texts_list_changed.emit()

    def get_texts_data(self):
        return [item.to_dict() for item in self.text_items if item.toPlainText().strip()]

    def load_texts_data(self, texts_list):
        for item in list(self.text_items):
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        self.text_items.clear()

        if texts_list:
            for data in texts_list:
                item = MangaTextItem.from_dict(data)
                self.scene.addItem(item)
                self.text_items.append(item)
        self.texts_list_changed.emit()

    @staticmethod
    def render_texts_onto_cv_img(cv_img, texts_data):
        if cv_img is None or not texts_data:
            return cv_img

        img_copy = cv_img.copy()
        h, w = img_copy.shape[:2]
        has_alpha = (len(img_copy.shape) == 3 and img_copy.shape[2] == 4)

        if has_alpha:
            q_img = QImage(img_copy.data, w, h, w * 4, QImage.Format_RGBA8888).copy()
        else:
            q_img = QImage(img_copy.data, w, h, w * 3, QImage.Format_RGB888).copy()

        temp_scene = QGraphicsScene(0, 0, w, h)
        for data in texts_data:
            if data.get("text", "").strip():
                item = MangaTextItem.from_dict(data)
                item.setSelected(False)
                temp_scene.addItem(item)

        painter = QPainter(q_img)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        temp_scene.render(painter, QRectF(0, 0, w, h), QRectF(0, 0, w, h))
        painter.end()

        ptr = q_img.bits()
        if has_alpha:
            res = np.frombuffer(ptr, np.uint8).reshape((h, w, 4)).copy()
        else:
            bpl = q_img.bytesPerLine()
            raw = np.frombuffer(ptr, np.uint8).reshape((h, bpl))
            res = raw[:, :w * 3].reshape((h, w, 3)).copy()
        return res

    def get_composited_image(self):
        return self.render_texts_onto_cv_img(self.cv_img, self.get_texts_data())

    # --- MANUAL CLEANER (DIRECT IMAGE BRUSH & COLOR PICKER) ---
    def refresh_image_pixmap(self):
        if self.cv_img is None:
            return
        h, w = self.cv_img.shape[:2]
        if len(self.cv_img.shape) == 3 and self.cv_img.shape[2] == 4:
            q_img = QImage(self.cv_img.data, w, h, w * 4, QImage.Format_RGBA8888)
        else:
            q_img = QImage(self.cv_img.data, w, h, w * 3, QImage.Format_RGB888)
        self.image_item.setPixmap(QPixmap.fromImage(q_img))

    def pick_color_at(self, pt: QPointF):
        if self.cv_img is None:
            return
        x, y = int(pt.x()), int(pt.y())
        h, w = self.cv_img.shape[:2]
        if 0 <= x < w and 0 <= y < h:
            px = self.cv_img[y, x]
            c = QColor(int(px[0]), int(px[1]), int(px[2]))
            self.manual_clean_color = c
            self.update_cursor_visuals()
            self.clean_color_picked.emit(c)

    def paint_image_stroke(self, p1: QPointF, p2: QPointF):
        if self.cv_img is None:
            return
        h, w = self.cv_img.shape[:2]
        rad = max(1, int(round(self.brush_size / 2.0)))
        x1, y1 = int(round(p1.x())), int(round(p1.y()))
        x2, y2 = int(round(p2.x())), int(round(p2.y()))

        pad = rad + 4
        self._stroke_min_x = max(0, min(self._stroke_min_x, x1 - pad, x2 - pad))
        self._stroke_min_y = max(0, min(self._stroke_min_y, y1 - pad, y2 - pad))
        self._stroke_max_x = min(w, max(self._stroke_max_x, x1 + pad, x2 + pad))
        self._stroke_max_y = min(h, max(self._stroke_max_y, y1 + pad, y2 + pad))

        c = self.manual_clean_color
        if len(self.cv_img.shape) == 3 and self.cv_img.shape[2] == 4:
            color_val = (c.red(), c.green(), c.blue(), 255)
        else:
            color_val = (c.red(), c.green(), c.blue())

        if x1 == x2 and y1 == y2:
            cv2.circle(self.cv_img, (x1, y1), rad, color_val, -1, lineType=cv2.LINE_AA)
        else:
            cv2.line(self.cv_img, (x1, y1), (x2, y2), color_val, self.brush_size, lineType=cv2.LINE_AA)

        self.refresh_image_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.lock_overlay.move(self.width() - self.lock_overlay.width() - 20, 20)

    def set_locked(self, locked: bool):
        self.is_locked = locked
        if locked:
            self.cursor_item.hide()
            self.lock_overlay.show()
            self.viewport().unsetCursor()
        else:
            self.lock_overlay.hide()
            if self.current_tool in ["BRUSH", "ERASER", "PAINT"]:
                self.viewport().setCursor(Qt.BlankCursor)
                self.cursor_item.show()
            elif self.current_tool in ["RECT", "LASSO", "POLY", "BUCKET", "PICKER"]:
                self.viewport().setCursor(Qt.CrossCursor)
            elif self.current_tool == "TEXT":
                self.viewport().setCursor(Qt.IBeamCursor)
            else:
                self.viewport().unsetCursor()

    def drawBackground(self, painter, rect):
        painter.save()
        painter.resetTransform()
        painter.fillRect(self.viewport().rect(), QColor(11, 11, 14))
        painter.restore()

        if self.cv_img is not None:
            painter.save()
            painter.setClipRect(self.sceneRect())
            painter.resetTransform()
            painter.fillRect(self.viewport().rect(), self.backgroundBrush())
            painter.restore()

    def update_cursor_visuals(self):
        if self.current_tool == "ERASER":
            self.cursor_item.setPen(QPen(QColor(0, 212, 255, 200), 1))
            self.cursor_item.setBrush(QBrush(QColor(0, 212, 255, 60)))
        elif self.current_tool == "PAINT":
            c = QColor(self.manual_clean_color)
            c.setAlpha(110)
            self.cursor_item.setPen(QPen(QColor(0, 255, 140, 230), 1.5))
            self.cursor_item.setBrush(QBrush(c))
        else:
            self.cursor_item.setPen(QPen(QColor(255, 0, 0, 200), 1))
            self.cursor_item.setBrush(QBrush(QColor(255, 0, 0, 60)))
        
        r = self.brush_size / 2
        self.cursor_item.setRect(-r, -r, self.brush_size, self.brush_size)

    def set_brush_size(self, size):
        if self.brush_size != size:
            self.brush_size = size
            self.update_cursor_visuals()
            self.brush_size_changed.emit(self.brush_size)

    def set_image(self, cv_img):
        self.cv_img = cv_img
        self.last_drawn_pt = None
        self.poly_points.clear()
        self.preview_item.setPath(QPainterPath())
        
        h, w = cv_img.shape[:2]
        self.refresh_image_pixmap()
        self.mask = QImage(w, h, QImage.Format_ARGB32)
        self.mask.fill(Qt.transparent)
        self.update_mask_display()
        self.scene.setSceneRect(0, 0, w, h)

    def update_mask_display(self):
        if self.mask: self.mask_item.setPixmap(QPixmap.fromImage(self.mask))

    def apply_bucket_fill(self, pt, is_erasing):
        x, y = int(pt.x()), int(pt.y())
        h, w = self.mask.height(), self.mask.width()
        
        if not (0 <= x < w and 0 <= y < h): return
        
        ptr = self.mask.bits()
        mask_np = np.frombuffer(ptr, np.uint8).reshape((h, w, 4)).copy()
        alpha = mask_np[:, :, 3].copy() 
        
        fill_val = 0 if is_erasing else 255
        target_val = int(alpha[y, x])
        
        if target_val == fill_val:
            return
            
        ff_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
        if is_erasing:
            ff_mask[1:-1, 1:-1] = (alpha == 0).astype(np.uint8)
        else:
            ff_mask[1:-1, 1:-1] = (alpha == 255).astype(np.uint8)
            
        flags = 4 | (255 << 8)
        cv2.floodFill(alpha, ff_mask, (x, y), fill_val, loDiff=255, upDiff=255, flags=flags)
        mask_np[:, :, 3] = alpha
        
        if not is_erasing:
            mask_np[:, :, 0] = 0
            mask_np[:, :, 1] = 0
            mask_np[:, :, 2] = 255
            
        self.mask = QImage(mask_np.data, w, h, w * 4, QImage.Format_ARGB32).copy()
        self.update_mask_display()

    def wheelEvent(self, event):
        modifiers = event.modifiers()
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.angleDelta().x()
        if delta == 0:
            return

        if modifiers & Qt.ControlModifier:
            selected_texts = [it for it in self.scene.selectedItems() if isinstance(it, MangaTextItem)]
            if selected_texts:
                step = 1 if delta > 0 else -1
                for it in selected_texts:
                    if modifiers & Qt.ShiftModifier:
                        it.set_rotation_angle(it.rotation() + step * 5.0)
                    else:
                        it.font_size = max(6, min(300, it.font_size + step * 2))
                        it.update_style()
                    it._notify_style_synced()
                    it._notify_modified()
                event.accept()
                return

        if modifiers & Qt.AltModifier:
            zoom = 1.25 if delta > 0 else 0.8
            self.scale(zoom, zoom)
            event.accept()
        elif modifiers & Qt.ShiftModifier:
            h_bar = self.horizontalScrollBar()
            h_bar.setValue(h_bar.value() - delta)
            event.accept()
        else:
            super().wheelEvent(event)

    def _find_gizmo_handle_at(self, scene_pt: QPointF):
        for item in self.scene.selectedItems():
            if isinstance(item, MangaTextItem):
                local_pt = item.mapFromScene(scene_pt)
                handle = item.hit_test_handle(local_pt)
                if handle:
                    return item, handle
        return None, None

    def mousePressEvent(self, event):
        if (event.modifiers() & Qt.AltModifier) and event.button() == Qt.RightButton and self.current_tool in ["BRUSH", "ERASER", "PAINT"]:
            self.is_resizing_brush = True
            self.resize_start_pos = event.pos()
            self.resize_start_size = self.brush_size
            self.resize_start_cursor_pos = QCursor.pos()
            event.accept()
            return

        curr_pt = self.mapToScene(event.pos())

        if event.button() == Qt.LeftButton and not self.is_locked and self.current_tool in ["TEXT", "NONE"]:
            gizmo_item, handle = self._find_gizmo_handle_at(curr_pt)
            if gizmo_item and handle:
                self._active_gizmo_item = gizmo_item
                self._active_gizmo_mode = handle
                self._gizmo_start_font_size = gizmo_item.font_size
                self._gizmo_start_box_width = gizmo_item._text_rect().width()
                center_scene = gizmo_item.mapToScene(gizmo_item._text_rect().center())
                self._gizmo_start_dist = max(10.0, math.hypot(
                    curr_pt.x() - center_scene.x(),
                    curr_pt.y() - center_scene.y()
                ))
                event.accept()
                return

        if self.current_tool == "TEXT" and not self.is_locked and self.cv_img is not None:
            item_under_mouse = self.itemAt(event.pos())

            if event.button() == Qt.RightButton:
                if isinstance(item_under_mouse, MangaTextItem):
                    self.remove_text_item(item_under_mouse)
                    event.accept()
                    return
            elif event.button() == Qt.LeftButton:
                if isinstance(item_under_mouse, MangaTextItem):
                    super().mousePressEvent(event)
                    return
                else:
                    if self.is_editing_text() or self.scene.selectedItems():
                        focus_item = self.scene.focusItem()
                        if focus_item:
                            focus_item.clearFocus()
                        self.scene.clearSelection()
                        event.accept()
                        return
                    if 0 <= curr_pt.x() <= self.scene.width() and 0 <= curr_pt.y() <= self.scene.height():
                        self.add_text_item(curr_pt)
                        event.accept()
                        return

        if self.current_tool == "NONE" or event.button() == Qt.RightButton:
            if event.button() == Qt.RightButton and self.current_tool == "POLY":
                self.poly_points.clear()
                self.preview_item.setPath(QPainterPath())
            super().mousePressEvent(event)
            
        elif self.is_locked:
            return
            
        elif event.button() == Qt.LeftButton and self.mask:
            if self.is_editing_text():
                self.scene.focusItem().clearFocus()
            self.scene.clearSelection()

            if self.current_tool == "PICKER" or (self.current_tool == "PAINT" and (event.modifiers() & Qt.AltModifier)):
                self.pick_color_at(curr_pt)
                event.accept()
                return

            if self.current_tool == "PAINT" and self.cv_img is not None:
                h, w = self.cv_img.shape[:2]
                self._stroke_pre_img = self.cv_img.copy()
                self._stroke_min_x, self._stroke_min_y = w, h
                self._stroke_max_x, self._stroke_max_y = 0, 0
                self.is_drawing = True
                if (event.modifiers() & Qt.ShiftModifier) and self.last_drawn_pt is not None:
                    self.paint_image_stroke(self.last_drawn_pt, curr_pt)
                else:
                    self.paint_image_stroke(curr_pt, curr_pt)
                self.last_pt = curr_pt
                self.last_drawn_pt = curr_pt
                event.accept()
                return

            if self.current_tool == "BUCKET":
                self.mask_changed.emit()
                is_erasing = bool(event.modifiers() & Qt.AltModifier)
                self.apply_bucket_fill(curr_pt, is_erasing)
                return
            
            if self.current_tool == "POLY":
                if not self.poly_points:
                    self.mask_changed.emit()
                self.poly_points.append(curr_pt)
                self.mouseMoveEvent(event)
                return
            
            self.mask_changed.emit()
            self.is_drawing = True
            
            is_brush_tool = self.current_tool in ["BRUSH", "ERASER"]
            
            if is_brush_tool and (event.modifiers() & Qt.ShiftModifier) and self.last_drawn_pt is not None:
                self.paint_mask_stroke(self.last_drawn_pt, curr_pt)
                self.last_pt = curr_pt
                self.last_drawn_pt = curr_pt
            else:
                self.start_pt = curr_pt
                self.last_pt = curr_pt
                
                if self.current_tool == "LASSO": 
                    self.lasso_path = QPainterPath(self.start_pt)
                elif is_brush_tool:
                    self.paint_mask_stroke(curr_pt, curr_pt)
                    self.last_drawn_pt = curr_pt

    def mouseMoveEvent(self, event):
        if self.is_resizing_brush:
            delta_x = event.pos().x() - self.resize_start_pos.x()
            new_size = int(self.resize_start_size + delta_x * 0.5)
            new_size = max(1, min(300, new_size))
            self.set_brush_size(new_size)
            event.accept()
            return

        curr_pt = self.mapToScene(event.pos())
        self.cursor_item.setPos(curr_pt)

        if self._active_gizmo_item is not None and self._active_gizmo_mode is not None:
            it = self._active_gizmo_item
            r = it._text_rect()
            center_local = r.center()
            center_scene = it.mapToScene(center_local)

            if self._active_gizmo_mode == "ROTATE":
                dx = curr_pt.x() - center_scene.x()
                dy = curr_pt.y() - center_scene.y()
                angle = math.degrees(math.atan2(dy, dx)) + 90.0
                if event.modifiers() & Qt.ShiftModifier:
                    angle = round(angle / 15.0) * 15.0
                it.set_rotation_angle(angle)
                it._notify_style_synced()

            elif self._active_gizmo_mode in ("TL", "TR", "BL", "BR"):
                curr_dist = max(10.0, math.hypot(
                    curr_pt.x() - center_scene.x(),
                    curr_pt.y() - center_scene.y()
                ))
                ratio = curr_dist / self._gizmo_start_dist
                new_size = max(6, min(300, int(round(self._gizmo_start_font_size * ratio))))
                if new_size != it.font_size:
                    it.font_size = new_size
                    if it.box_width > 20.0:
                        it.box_width = max(40.0, self._gizmo_start_box_width * ratio)
                    it.update_style()
                    it._notify_style_synced()
                    it._notify_modified()

            elif self._active_gizmo_mode in ("L", "R"):
                old_center_scene = center_scene
                local_pt = it.mapFromScene(curr_pt)
                half_w = abs(local_pt.x() - center_local.x())
                it.box_width = max(40.0, half_w * 2.0)
                it.update_style()
                new_center_scene = it.mapToScene(it._text_rect().center())
                it.moveBy(
                    old_center_scene.x() - new_center_scene.x(),
                    old_center_scene.y() - new_center_scene.y()
                )
                it._notify_style_synced()
                it._notify_modified()

            event.accept()
            return

        if self.current_tool == "TEXT" and not self.is_locked:
            _, handle = self._find_gizmo_handle_at(curr_pt)
            if handle == "ROTATE":
                self.viewport().setCursor(Qt.CrossCursor)
            elif handle in ("TL", "BR"):
                self.viewport().setCursor(Qt.SizeFDiagCursor)
            elif handle in ("TR", "BL"):
                self.viewport().setCursor(Qt.SizeBDiagCursor)
            elif handle in ("L", "R"):
                self.viewport().setCursor(Qt.SizeHorCursor)
            else:
                item_under = self.itemAt(event.pos())
                if isinstance(item_under, MangaTextItem):
                    if item_under.textInteractionFlags() & Qt.TextEditorInteraction:
                        self.viewport().setCursor(Qt.IBeamCursor)
                    else:
                        self.viewport().setCursor(Qt.SizeAllCursor)
                else:
                    self.viewport().setCursor(Qt.IBeamCursor)
        
        if self.current_tool == "POLY" and self.poly_points:
            is_erasing = bool(event.modifiers() & Qt.AltModifier)
            p_color = QColor(0, 212, 255, 200) if is_erasing else QColor(255, 0, 0, 200)
            self.preview_item.setPen(QPen(p_color, 2, Qt.DashLine))

            path = QPainterPath()
            path.moveTo(self.poly_points[0])
            for pt in self.poly_points[1:]:
                path.lineTo(pt)
            path.lineTo(curr_pt)
            self.preview_item.setPath(path)

        if self.is_drawing:
            if self.current_tool == "PAINT":
                self.paint_image_stroke(self.last_pt, curr_pt)
                self.last_pt = curr_pt
                self.last_drawn_pt = curr_pt
            elif self.current_tool in ["BRUSH", "ERASER"]:
                self.paint_mask_stroke(self.last_pt, curr_pt)
                self.last_pt = curr_pt
                self.last_drawn_pt = curr_pt
            elif self.current_tool in ["RECT", "LASSO"]:
                is_erasing = bool(event.modifiers() & Qt.AltModifier)
                p_color = QColor(0, 212, 255, 200) if is_erasing else QColor(255, 0, 0, 200)
                self.preview_item.setPen(QPen(p_color, 2, Qt.DashLine))

                if self.current_tool == "RECT":
                    path = QPainterPath()
                    path.addRect(QRectF(self.start_pt, curr_pt).normalized())
                    self.preview_item.setPath(path)
                elif self.current_tool == "LASSO":
                    self.lasso_path.lineTo(curr_pt)
                    self.preview_item.setPath(self.lasso_path)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._active_gizmo_item is not None:
            self._active_gizmo_item.update_transform_origin()
            self._active_gizmo_item = None
            self._active_gizmo_mode = None
            event.accept()
            return

        if self.is_resizing_brush and event.button() == Qt.RightButton:
            self.is_resizing_brush = False
            if self.resize_start_cursor_pos:
                QCursor.setPos(self.resize_start_cursor_pos)
            event.accept()
            return

        if self.is_drawing:
            curr_pt = self.mapToScene(event.pos())
            is_erasing = bool(event.modifiers() & Qt.AltModifier)
            if self.current_tool == "PAINT":
                if (self._stroke_pre_img is not None and 
                    self._stroke_max_x > self._stroke_min_x and 
                    self._stroke_max_y > self._stroke_min_y):
                    x, y = self._stroke_min_x, self._stroke_min_y
                    old_patch = self._stroke_pre_img[y:self._stroke_max_y, x:self._stroke_max_x].copy()
                    self.image_patch_created.emit(x, y, old_patch)
                self._stroke_pre_img = None
            elif self.current_tool == "RECT":
                self.paint_mask_rect(self.start_pt, curr_pt, is_erasing)
            elif self.current_tool == "LASSO":
                self.paint_mask_lasso(is_erasing)
            self.is_drawing = False
            self.preview_item.setPath(QPainterPath())
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.current_tool == "POLY":
            if len(self.poly_points) >= 3:
                is_erasing = bool(event.modifiers() & Qt.AltModifier)
                
                path = QPainterPath()
                path.moveTo(self.poly_points[0])
                for pt in self.poly_points[1:]:
                    path.lineTo(pt)
                path.closeSubpath()
                
                painter, color = self.get_painter(is_erasing)
                painter.fillPath(path, QBrush(color))
                painter.end()
                self.update_mask_display()
                
            self.poly_points.clear()
            self.preview_item.setPath(QPainterPath())
            return
        super().mouseDoubleClickEvent(event)

    def get_painter(self, force_erase=False):
        painter = QPainter(self.mask)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self.current_tool == "ERASER" or force_erase:
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            color = Qt.transparent
        else:
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            color = QColor(255, 0, 0, 255)
            
        return painter, color

    def paint_mask_stroke(self, p1, p2):
        painter, color = self.get_painter()
        painter.setPen(QPen(color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if p1 == p2:
            painter.drawPoint(p1)
        else:
            painter.drawLine(p1, p2)
        painter.end()
        self.update_mask_display()

    def paint_mask_rect(self, p1, p2, is_erasing=False):
        painter, color = self.get_painter(is_erasing)
        painter.fillRect(QRectF(p1, p2).normalized(), QBrush(color))
        painter.end()
        self.update_mask_display()

    def paint_mask_lasso(self, is_erasing=False):
        painter, color = self.get_painter(is_erasing)
        painter.fillPath(self.lasso_path, QBrush(color))
        painter.end()
        self.update_mask_display()

    def set_mask_opacity(self, opacity_percent):
        if self.mask_item:
            self.mask_item.setOpacity(opacity_percent / 100.0)

    def clear_mask(self):
        if self.is_locked: return
        self.poly_points.clear()
        self.preview_item.setPath(QPainterPath())
        if self.mask:
            self.mask_changed.emit()
            self.mask.fill(Qt.transparent)
            self.update_mask_display()
            self.last_drawn_pt = None