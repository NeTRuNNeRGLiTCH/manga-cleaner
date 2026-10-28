import os
import PySide6.QtSvg 
from PySide6.QtWidgets import (QListWidget, QListWidgetItem, QWidget, QVBoxLayout, 
                             QPushButton, QLabel, QFrame, QSlider, QHBoxLayout,
                             QStyledItemDelegate, QGridLayout)
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QIcon, QColor
from src.utils.config import Config
from src.utils.paths import Paths
from src.utils.i18n import tr_label
from src.utils.i18n import tr

#/////////////////////////////////#
#    STUDIO COMPONENT LIBRARY     #
#/////////////////////////////////#

class FileListDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.icons = {}

    def _get_icon(self, state_name: str) -> QIcon:
        """Caches and returns the SVG icon for the given state"""
        if state_name not in self.icons:
            icon_path = os.path.join(Paths.BUNDLE_DIR, "assets", f"icon_{state_name}.svg")
            if os.path.exists(icon_path):
                self.icons[state_name] = QIcon(icon_path)
            else:
                self.icons[state_name] = QIcon() 
        return self.icons[state_name]

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        
        state_name = index.data(Qt.UserRole + 1)
        is_locked = index.data(Qt.UserRole + 2)
        
        icon_size = 18
        offset_x = 4
        
        if state_name:
            icon = self._get_icon(state_name)
            if not icon.isNull():
                x = option.rect.right() - icon_size - offset_x
                y = option.rect.top() + (option.rect.height() - icon_size) // 2
                rect = QRect(x, y, icon_size, icon_size)
                icon.paint(painter, rect, Qt.AlignCenter, QIcon.Normal, QIcon.On)
                offset_x += icon_size + 4
                
        if is_locked:
            lock_icon = self._get_icon("lock")
            if not lock_icon.isNull():
                x = option.rect.right() - icon_size - offset_x
                y = option.rect.top() + (option.rect.height() - icon_size) // 2
                rect = QRect(x, y, icon_size, icon_size)
                lock_icon.paint(painter, rect, Qt.AlignCenter, QIcon.Normal, QIcon.On)

class FileListWidget(QListWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background: {Config.COLOR_PANEL}; border: none;")
        self.setItemDelegate(FileListDelegate(self))

    def add_file(self, full_path: str):
        item = QListWidgetItem(os.path.basename(full_path))
        item.setData(Qt.UserRole, full_path)
        item.setData(Qt.UserRole + 1, "unmodified")  
        item.setData(Qt.UserRole + 2, False)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Unchecked)
        self.addItem(item)

    def update_item_state(self, full_path: str, state_name: str):
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.UserRole) == full_path:
                item.setData(Qt.UserRole + 1, state_name)
                break

class ColorSwatchButton(QPushButton):
    """Photoshop-style pure color rectangle button without internal text."""
    def __init__(self, initial_color=QColor(255, 255, 255), width=38, height=24, tooltip=""):
        super().__init__("")
        self._color = QColor(initial_color)
        self.setFixedSize(width, height)
        self.setCursor(Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)
        self.set_color(self._color)

    def set_color(self, color: QColor):
        self._color = QColor(color)
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self._color.name()}; "
            f"border: 2px solid #5a5a66; border-radius: 2px; }}"
            f"QPushButton:hover {{ border: 2px solid {Config.COLOR_ACCENT}; }}"
        )

    def get_color(self) -> QColor:
        return QColor(self._color)

class CategorySelector(QFrame):
    """Top workspace/category switcher for the right sidebar (2x2 Grid)"""
    category_changed = Signal(str)

    def __init__(self, categories):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 4)
        lay.setSpacing(4)

        grid = QGridLayout()
        grid.setSpacing(4)
        self.buttons = {}

        for i, name in enumerate(categories):
            btn = QPushButton(tr_label(name))   # visible label; `name` stays the internal ID
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, n=name: self.category_changed.emit(n))
            self.buttons[name] = btn
            grid.addWidget(btn, i // 2, i % 2)

        if categories:
            self.buttons[categories[0]].setChecked(True)

        lay.addLayout(grid)

class ToolGroup(QFrame):
    def __init__(self, title, button_configs, full_width_buttons=None):
        super().__init__()
        full_width_buttons = set(full_width_buttons or [])
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(5, 5, 5, 5)
        main_lay.setSpacing(4)
        
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold;")
        main_lay.addWidget(lbl)
        
        grid_lay = QGridLayout()
        grid_lay.setSpacing(4)
        
        self.buttons = {}
        checkable = ["MOVE", "BRUSH", "ERASER", "RECT", "LASSO", "POLY", "BUCKET", "MANUAL", "PICKER", "TEXT"]
        
        row = 0
        col = 0
        for name in button_configs:
            btn = QPushButton(tr_label(name))   # visible label; `name` stays the internal ID
            if name in checkable: 
                btn.setCheckable(True)
                btn.setAutoExclusive(True) 
            self.buttons[name] = btn
            
            if name in full_width_buttons:
                if col != 0:
                    row += 1
                    col = 0
                btn.setFixedHeight(32)
                grid_lay.addWidget(btn, row, 0, 1, 2)
                row += 1
            else:
                grid_lay.addWidget(btn, row, col)
                col += 1
                if col >= 2:
                    col = 0
                    row += 1
            
        main_lay.addLayout(grid_lay)

class HardwareMonitor(QFrame):
    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        
        self.lbl = QLabel(tr("widgets.system_idle"))
        self.lbl.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold; font-size: 10px;")
        
        self.bar = QSlider(Qt.Horizontal)
        self.bar.setRange(0, 100)
        self.bar.setFixedWidth(100)
        self.bar.setEnabled(False)
        
        lay.addWidget(self.lbl)
        lay.addWidget(self.bar)

class LabeledSlider(QWidget):
    def __init__(self, label, default, minimum, maximum, callback=None, is_tile=False, suffix="px"):
        super().__init__()
        self.is_tile = is_tile
        self.suffix = suffix
        self.base_label = label
        lay = QVBoxLayout(self)
        
        self.display = QLabel("")
        self.display.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        
        self.slider = QSlider(Qt.Horizontal)
        if is_tile:
            self.slider.setRange(1, 8) 
            self.slider.setValue(default // 512)
        else:
            self.slider.setRange(minimum, maximum)
            self.slider.setValue(default)
            
        self.slider.valueChanged.connect(self.update_text)
        if callback: self.slider.valueChanged.connect(callback)
            
        lay.addWidget(self.display)
        lay.addWidget(self.slider)
        self.update_text(self.slider.value())

    def update_text(self, val):
        if self.is_tile:
            self.display.setText(tr("widgets.base_label_value_px", base_label=self.base_label, value=val * 512))
        else:
            self.display.setText(f"{self.base_label}: {val}{self.suffix}")