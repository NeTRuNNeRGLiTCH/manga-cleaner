import os
import cv2
import numpy as np
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QProgressBar, QFrame, 
                             QSplitter, QFileDialog, QMenu, QComboBox, QMessageBox)
from PySide6.QtGui import QImage, QShortcut, QKeySequence
from PySide6.QtCore import Qt, QTimer, QThread
from src.frontend.widgets import FileListWidget, ToolGroup, BrushSlider
from src.frontend.canvas import MangaCanvas
from src.utils.system_info import SystemMonitor
from src.backend.workers import AIWorker
from src.backend.photoshop import PhotoshopBridge

#////////////////////////#
#   MAIN UI CONTROLLER   #
#////////////////////////#

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MANGA CLEANER STUDIO")
        self.resize(1500, 900)
        
        self.monitor = SystemMonitor()
        self.worker_thread = None
        self.undo_stack = []
        
        self.init_ui()
        self.setup_shortcuts()
        
        #////////////////////////#
        #  SYSTEM TELEMETRY      #
        #////////////////////////#
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_system_stats)
        self.stats_timer.start(2000)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.on_undo)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        #////////////////////////#
        #       NAVIGATION       #
        #////////////////////////#
        self.nav_bar = QFrame()
        self.nav_bar.setObjectName("NavBar")
        self.nav_bar.setFixedHeight(60)
        nav_lay = QHBoxLayout(self.nav_bar)
        
        title = QLabel("TITAN // MANGA CLEANER")
        title.setObjectName("TitleLabel")
        
        self.vram_label = QLabel("VRAM 0%")
        self.vram_bar = QProgressBar()
        self.vram_bar.setFixedWidth(100)
        self.vram_bar.setFixedHeight(12)
        
        btn_open = QPushButton("📁 OPEN FOLDER")
        btn_open.clicked.connect(self.on_open_folder)
        
        btn_ps = QPushButton("🎨 PHOTOSHOP BRIDGE")
        btn_ps.clicked.connect(self.on_photoshop_bridge)
        
        self.btn_export = QPushButton("💾 EXPORT RESULT ▼")
        self.btn_export.setObjectName("PrimaryBtn")
        exp_menu = QMenu(self)
        exp_menu.addAction("Export as JPG").triggered.connect(lambda: self.on_export("jpg"))
        exp_menu.addAction("Export as PNG").triggered.connect(lambda: self.on_export("png"))
        self.btn_export.setMenu(exp_menu)
        
        nav_lay.addWidget(title)
        nav_lay.addStretch()
        nav_lay.addWidget(self.vram_label)
        nav_lay.addWidget(self.vram_bar)
        nav_lay.addSpacing(20)
        nav_lay.addWidget(btn_open)
        nav_lay.addWidget(btn_ps)
        nav_lay.addWidget(self.btn_export)
        lay.addWidget(self.nav_bar)

        #////////////////////////#
        #      WORK STUDIO       #
        #////////////////////////#
        splitter = QSplitter(Qt.Horizontal)
        
        self.left_panel = QFrame()
        self.left_panel.setObjectName("SidePanel")
        left_lay = QVBoxLayout(self.left_panel)
        left_lay.addWidget(QLabel("ASSETS / PAGES"))
        self.file_list = FileListWidget()
        self.file_list.itemClicked.connect(self.on_file_clicked)
        left_lay.addWidget(self.file_list)
        
        self.canvas = MangaCanvas()
        
        self.right_panel = QFrame()
        self.right_panel.setObjectName("SidePanel")
        right_lay = QVBoxLayout(self.right_panel)
        
        self.mask_tools = ToolGroup("Manual Tools", ["MOVE SCREEN", "PAINT MASK", "ERASE MASK", "CLEAR ALL"])
        self.mask_tools.buttons["MOVE SCREEN"].clicked.connect(lambda: self.set_tool("NONE"))
        self.mask_tools.buttons["PAINT MASK"].clicked.connect(lambda: self.set_tool("PAINT"))
        self.mask_tools.buttons["ERASE MASK"].clicked.connect(lambda: self.set_tool("ERASE"))
        self.mask_tools.buttons["CLEAR ALL"].clicked.connect(self.canvas.clear_mask)
        
        self.brush_slider = BrushSlider("BRUSH SIZE", default=40, callback=self.canvas.set_brush_size)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Arabic", "English", "Korean", "Japanese", "Chinese"])
        
        self.detect_tools = ToolGroup("Detection", ["AUTO-SCAN TEXT"])
        self.detect_tools.buttons["AUTO-SCAN TEXT"].clicked.connect(self.on_auto_scan)
        
        self.ai_tools = ToolGroup("AI Core", ["LAUNCH LAMA CLEAN"])
        self.tile_slider = BrushSlider("AI TILING", default=1, minimum=1, maximum=10, is_tile=True)
        self.ai_tools.buttons["LAUNCH LAMA CLEAN"].clicked.connect(self.on_lama_clean)
        
        right_lay.addWidget(self.mask_tools)
        right_lay.addWidget(self.brush_slider)
        right_lay.addWidget(QLabel("OCR LANGUAGE:"))
        right_lay.addWidget(self.lang_combo)
        right_lay.addSpacing(15)
        right_lay.addWidget(self.detect_tools)
        right_lay.addWidget(self.tile_slider)
        right_lay.addWidget(self.ai_tools)
        right_lay.addStretch()
        
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.canvas)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([220, 1000, 240])
        lay.addWidget(splitter, 1)
        
        self.set_tool("NONE")

    def set_tool(self, tool):
        self.canvas.current_tool = tool
        for name, btn in self.mask_tools.buttons.items(): 
            btn.setChecked(False)
        if tool == "NONE": self.mask_tools.buttons["MOVE SCREEN"].setChecked(True)
        elif tool == "PAINT": self.mask_tools.buttons["PAINT MASK"].setChecked(True)
        elif tool == "ERASE": self.mask_tools.buttons["ERASE MASK"].setChecked(True)

    def on_undo(self):
        if not self.undo_stack: return
        patches = self.undo_stack.pop()
        for y1, y2, pix in patches: 
            self.canvas.cv_img[y1:y2, :] = pix
        self.canvas.set_image(self.canvas.cv_img)

    #////////////////////////#
    #   THREADED OPERATIONS  #
    #////////////////////////#

    def on_auto_scan(self):
        if self.canvas.cv_img is None or self.worker_thread: return
        
        m = {"Arabic":['ar'], "English":['en'], "Korean":['ko'], "Japanese":['ja'], "Chinese":['ch_sim']}
        langs = m.get(self.lang_combo.currentText(), ['en'])
        
        self.status_loading(True)
        self.worker_thread = QThread()
        self.ai_worker = AIWorker()
        self.ai_worker.moveToThread(self.worker_thread)
        
        self.worker_thread.started.connect(lambda: self.ai_worker.run_ocr(self.canvas.cv_img, langs))
        self.ai_worker.finished.connect(self.on_ocr_finished)
        self.ai_worker.error.connect(self.on_ai_error)
        
        self.worker_thread.start()

    def on_ocr_finished(self, mask_data, _):
        if mask_data is not None:
            h, w = mask_data.shape
            rgba = np.zeros((h, w, 4), dtype=np.uint8)
            rgba[mask_data > 0] = [255, 0, 0, 180] 
            self.canvas.mask = QImage(rgba.data, w, h, w*4, QImage.Format_ARGB32).copy()
            self.canvas.update_mask_display()
        self.status_loading(False)

    def on_lama_clean(self):
        if self.canvas.cv_img is None or self.worker_thread: return
        
        self.status_loading(True)
        ptr = self.canvas.mask.bits()
        mask_np = np.frombuffer(ptr, np.uint8).reshape((self.canvas.mask.height(), self.canvas.mask.width(), 4))
        mask_gray = mask_np[:, :, 3].copy()
        
        n = self.tile_slider.slider.value()
        
        self.worker_thread = QThread()
        self.ai_worker = AIWorker()
        self.ai_worker.moveToThread(self.worker_thread)
        
        self.worker_thread.started.connect(lambda: self.ai_worker.run_clean(self.canvas.cv_img, mask_gray, n))
        self.ai_worker.finished.connect(self.on_clean_finished)
        self.ai_worker.error.connect(self.on_ai_error)
        
        self.worker_thread.start()

    def on_clean_finished(self, res, patches):
        if res is not None:
            self.undo_stack.append(patches)
            if len(self.undo_stack) > 20: self.undo_stack.pop(0)
            self.canvas.set_image(res)
            self.canvas.clear_mask()
        self.status_loading(False)

    def on_ai_error(self, message):
        self.status_loading(False)
        QMessageBox.critical(self, "AI Engine Error", f"Operation failed: {message}")

    #////////////////////////#
    #   SYSTEM & IO HANDLERS #
    #////////////////////////#

    def on_export(self, fmt):
        if self.canvas.cv_img is None: return
        path, _ = QFileDialog.getSaveFileName(self, "Export", "", f"{fmt.upper()} (*.{fmt})")
        if path:
            out = cv2.cvtColor(self.canvas.cv_img, cv2.COLOR_RGB2BGR)
            cv2.imwrite(path, out, [int(cv2.IMWRITE_JPEG_QUALITY), 95] if fmt=="jpg" else [])

    def on_photoshop_bridge(self):
        if self.canvas.cv_img is None: return
        it = self.file_list.currentItem()
        if not it: return
        self.status_loading(True)
        orig = cv2.cvtColor(cv2.imread(it.data(Qt.UserRole)), cv2.COLOR_BGR2RGB)
        status = PhotoshopBridge.send_to_ps(orig, self.canvas.cv_img)
        if status != "Success":
            QMessageBox.warning(self, "Photoshop Bridge", f"Link failed: {status}")
        self.status_loading(False)

    def status_loading(self, busy):
        self.nav_bar.setEnabled(not busy)
        self.right_panel.setEnabled(not busy)
        self.setCursor(Qt.WaitCursor if busy else Qt.ArrowCursor)
        if not busy and self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None

    def on_open_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Select Folder")
        if p:
            self.file_list.clear()
            for f in sorted(os.listdir(p)):
                if f.lower().endswith(('.jpg','.jpeg','.png','.webp')): 
                    self.file_list.add_file(os.path.join(p, f))

    def on_file_clicked(self, it):
        img = cv2.imread(it.data(Qt.UserRole))
        if img is not None: 
            self.undo_stack = []
            self.canvas.set_image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    def update_system_stats(self):
        used, total = self.monitor.get_vram_info()
        if total > 0:
            perc = int((used/total)*100)
            self.vram_bar.setValue(perc)
            self.vram_label.setText(f"VRAM {perc}%")
            if perc > 90:
                self.vram_label.setStyleSheet("color: #ff4444;")
            else:
                self.vram_label.setStyleSheet("")