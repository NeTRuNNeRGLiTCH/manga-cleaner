import os
from PySide6.QtWidgets import (QListWidget, QListWidgetItem, QWidget, QVBoxLayout, 
                             QPushButton, QLabel, QFrame, QSlider)
from PySide6.QtCore import Qt, Signal

#////////////////////////#
#   UI COMPONENT LIBRARY #
#////////////////////////#

class FileListWidget(QListWidget):
    def __init__(self):
        super().__init__()
        
    def add_file(self, full_path: str):
        filename = os.path.basename(full_path)
        item = QListWidgetItem(filename)
        item.setData(Qt.UserRole, full_path)
        self.addItem(item)

class ToolGroup(QFrame):
    def __init__(self, title: str, button_configs: list):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(5, 10, 5, 10)
        
        header = QLabel(title.upper())
        header.setStyleSheet("color: #555; font-size: 10px; font-weight: bold;")
        lay.addWidget(header)
        
        self.buttons = {}
        for btn_name in button_configs:
            btn = QPushButton(btn_name)
            if btn_name in ["MOVE SCREEN", "PAINT MASK", "ERASE MASK"]:
                btn.setCheckable(True)
            self.buttons[btn_name] = btn
            lay.addWidget(btn)

class BrushSlider(QWidget):
    def __init__(self, label, default=40, minimum=1, maximum=200, callback=None, is_tile=False):
        super().__init__()
        self.is_tile = is_tile
        self.base_label = label
        
        lay = QVBoxLayout(self)
        self.label_display = QLabel("")
        self.label_display.setStyleSheet("color: #888; font-size: 10px;")
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(default)
        
        self.update_text(default)
        self.slider.valueChanged.connect(self.update_text)
        
        if callback:
            self.slider.valueChanged.connect(callback)
            
        lay.addWidget(self.label_display)
        lay.addWidget(self.slider)

    def update_text(self, val: int):
        if self.is_tile:
            txt = "Full Image" if val == 1 else f"{val} Vertical Tiles"
            self.label_display.setText(f"{self.base_label}: {txt}")
        else:
            self.label_display.setText(f"{self.base_label}: {val}px")