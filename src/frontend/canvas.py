from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsEllipseItem
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QBrush
from PySide6.QtCore import Qt, QPointF
import numpy as np

#////////////////////////#
#  HIGH-PERFORMANCE VIEW #
#////////////////////////#

class MangaCanvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        #////////////////////////#
        #  RENDERING OPTIMIZATION#
        #////////////////////////#
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor(15, 15, 18)))
        self.setFrameShape(QGraphicsView.NoFrame)

        self.image_item = QGraphicsPixmapItem()
        self.mask_item = QGraphicsPixmapItem()
        self.scene.addItem(self.image_item)
        self.scene.addItem(self.mask_item)

        #////////////////////////#
        #   DYNAMIC CURSOR       #
        #////////////////////////#
        self.cursor_item = QGraphicsEllipseItem()
        self.cursor_item.setPen(QPen(QColor(255, 255, 255, 180), 1))
        self.cursor_item.setBrush(QBrush(QColor(255, 255, 255, 30)))
        self.cursor_item.setZValue(1000)
        self.scene.addItem(self.cursor_item)
        
        self.cv_img = None
        self.mask = None
        self.current_tool = "NONE"
        self.brush_size = 40
        self.is_drawing = False
        self.last_point = QPointF()
        self.setMouseTracking(True)

    def set_brush_size(self, size: int):
        self.brush_size = size
        r = size / 2
        self.cursor_item.setRect(-r, -r, size, size)

    def set_image(self, cv_img: np.ndarray):
        #////////////////////////#
        #  4K TEXTURE HANDLING   #
        #////////////////////////#
        self.cv_img = cv_img
        h, w = cv_img.shape[:2]
        
        if len(cv_img.shape) == 2:
            q_img = QImage(cv_img.data, w, h, w, QImage.Format_Grayscale8)
        else:
            q_img = QImage(cv_img.data, w, h, w*3, QImage.Format_RGB888)
            
        self.image_item.setPixmap(QPixmap.fromImage(q_img))
        
        # Initialize transparent mask layer
        self.mask = QImage(w, h, QImage.Format_ARGB32)
        self.mask.fill(Qt.transparent)
        self.update_mask_display()
        self.scene.setSceneRect(0, 0, w, h)

    def update_mask_display(self):
        if self.mask:
            self.mask_item.setPixmap(QPixmap.fromImage(self.mask))

    #////////////////////////#
    #   INTERACTION LOGIC    #
    #////////////////////////#

    def wheelEvent(self, event):
        zoom = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(zoom, zoom)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.current_tool != "NONE":
                self.is_drawing = True
                self.last_point = self.mapToScene(event.pos())
                self.paint_mask(self.last_point)
            else:
                self.setDragMode(QGraphicsView.ScrollHandDrag)
                super().mousePressEvent(event)
        elif event.button() == Qt.RightButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.pos())
        self.cursor_item.setPos(pos)
        
        if self.is_drawing and self.current_tool != "NONE":
            self.paint_mask(pos)
            self.last_point = pos
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_drawing = False
        self.setDragMode(QGraphicsView.NoDrag)
        super().mouseReleaseEvent(event)

    def paint_mask(self, pt: QPointF):
        #////////////////////////#
        # BITMAP MASK MUTATION   #
        #////////////////////////#
        if not self.mask: return
        
        painter = QPainter(self.mask)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self.current_tool == "PAINT":
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            pen = QPen(QColor(255, 0, 0, 180), self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        else:
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            pen = QPen(Qt.transparent, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            
        painter.setPen(pen)
        painter.drawLine(self.last_point, pt)
        painter.end()
        self.update_mask_display()

    def clear_mask(self):
        if self.mask:
            self.mask.fill(Qt.transparent)
            self.update_mask_display()