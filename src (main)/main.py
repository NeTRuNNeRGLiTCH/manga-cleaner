import sys, cv2, os, numpy as np, gc, time
import functions as fn
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, 
                             QHBoxLayout, QWidget, QFileDialog, QScrollArea, QSlider, 
                             QRadioButton, QListWidget, QDockWidget, QFrame, QComboBox, 
                             QProgressBar, QMessageBox)
from PySide6.QtGui import QPixmap, QImage, QShortcut, QKeySequence, QPainter, QPen, QColor, QCursor
from PySide6.QtCore import Qt, QPoint, QTimer, QThread, Signal, QObject

class AIWorker(QObject):
    finished = Signal(object)
    progress = Signal(int)

    def run_scan(self, img, lang):
        mask = fn.run_pro_scan(img, lang)
        self.finished.emit(mask)

    def run_clean(self, img, mask, lama, device):
        result = fn.run_ai_clean_tiled(img, mask, lama, device, self.progress.emit)
        self.finished.emit(result)

class TitanStudioV1(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TITAN MANGA STUDIO v1")
        self.resize(1400, 900)
        
        self.device = fn.get_device()
        self.lama = fn.initialize_lama()
        
        self.cv_img = None
        self.mask = None
        self.original_backup = None
        self.history = [] 
        self.max_history = 10
        
        self.current_file_path = None
        self.brush_size, self.zoom_factor = 60, 1.0
        self.last_point = None
        self.is_processing = False

        self.init_ui()
        self.setup_shortcuts()
        
        self.cursor_timer = QTimer()
        self.cursor_timer.timeout.connect(self.update)
        self.cursor_timer.start(16)

    def save_history(self):
        """Saves current state to history stack for Undo."""
        if self.cv_img is not None:
            self.history.append((self.cv_img.copy(), self.mask.copy()))
            if len(self.history) > self.max_history:
                self.history.pop(0)

    def undo_action(self):
        """Restores previous state from history."""
        if not self.history: return
        self.cv_img, self.mask = self.history.pop()
        self.update_display()

    def export_final_image(self):
        """Saves as high-quality JPG via Photoshop or direct OpenCV fallback."""
        if self.cv_img is None: return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Cleaned Image", "", "JPEG (*.jpg)")
        if not save_path: return

        try:
            import win32com.client
            cv2.imwrite(save_path, self.cv_img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
            QMessageBox.information(self, "Titan", "Image Saved Successfully!")
        except Exception as e:
            cv2.imwrite(save_path, self.cv_img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
            print(f"Photoshop Link Failed, saved via OpenCV: {e}")

    def on_file_selected(self, item):
        self.current_file_path = item.text()
        with open(self.current_file_path, "rb") as f:
            data = np.frombuffer(f.read(), np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            self.cv_img = img
            self.original_backup = img.copy()
        
        self.mask = np.zeros(self.cv_img.shape[:2], dtype=np.uint8)
        self.history = [] 
        self.zoom_factor = 1.0
        self.update_display()

    def init_ui(self):
        header = QFrame(); header.setFixedHeight(60); header.setStyleSheet("background: #111; border-bottom: 1px solid #333;")
        h_lay = QHBoxLayout(header)
        h_lay.addWidget(QLabel("TITAN // STUDIO", styleSheet="color: #00d4ff; font-weight: 900; font-size: 18px;"))
        self.progress_bar = QProgressBar(); self.progress_bar.setFixedWidth(200); h_lay.addWidget(self.progress_bar)
        h_lay.addStretch()
        
        btn_undo = QPushButton("↺ UNDO"); btn_undo.clicked.connect(self.undo_action); h_lay.addWidget(btn_undo)
        btn_save = QPushButton("💾 EXPORT"); btn_save.clicked.connect(self.export_final_image); h_lay.addWidget(btn_save)
        btn_load = QPushButton("📁 FOLDER"); btn_load.clicked.connect(self.load_folder); h_lay.addWidget(btn_load)
        self.setMenuWidget(header)

        self.scroll_area = QScrollArea(); self.scroll_area.setAlignment(Qt.AlignCenter)
        self.canvas = QLabel(); self.canvas.setMouseTracking(True)
        self.scroll_area.setWidget(self.canvas); self.setCentralWidget(self.scroll_area)

        self.file_list = QListWidget(); self.file_list.itemDoubleClicked.connect(self.on_file_selected)
        dock_assets = QDockWidget("ASSETS"); dock_assets.setWidget(self.file_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock_assets)

        tools = QWidget(); v_tools = QVBoxLayout(tools)
        self.lang_combo = QComboBox(); self.lang_combo.addItems(["en", "ko", "ja"])
        v_tools.addWidget(QLabel("OCR SOURCE:")); v_tools.addWidget(self.lang_combo)
        
        self.btn_scan = QPushButton("🤖 AUTO DETECT"); self.btn_scan.clicked.connect(self.action_scan)
        v_tools.addWidget(self.btn_scan)
        
        v_tools.addSpacing(20); v_tools.addWidget(QLabel("BRUSH SIZE:"))
        self.brush_slider = QSlider(Qt.Horizontal); self.brush_slider.setRange(5, 400); self.brush_slider.setValue(60)
        self.brush_slider.valueChanged.connect(lambda v: setattr(self, 'brush_size', v))
        v_tools.addWidget(self.brush_slider)
        
        self.rb_paint = QRadioButton("🖌️ PAINT (B)"); self.rb_paint.setChecked(True); v_tools.addWidget(self.rb_paint)
        self.rb_erase = QRadioButton("🧼 ERASER (E)"); v_tools.addWidget(self.rb_erase)
        
        v_tools.addStretch()
        self.btn_clean = QPushButton("🚀 LAUNCH AI CLEAN"); self.btn_clean.setFixedHeight(60)
        self.btn_clean.setStyleSheet("background: #005bb5; color: white; font-weight: bold; border-radius: 4px;")
        self.btn_clean.clicked.connect(self.action_clean)
        v_tools.addWidget(self.btn_clean)
        
        dock_tools = QDockWidget("CONTROL PANEL"); dock_tools.setWidget(tools)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_tools)

    def update_display(self):
        if self.cv_img is None: return
        disp = self.cv_img.copy()
        mask_idx = self.mask > 0
        overlay = np.full_like(disp, (0, 0, 255))
        disp[mask_idx] = cv2.addWeighted(disp, 0.4, overlay, 0.6, 0)[mask_idx]
        
        h, w = disp.shape[:2]
        q_img = QImage(cv2.cvtColor(disp, cv2.COLOR_BGR2RGB).data, w, h, w*3, QImage.Format_RGB888)
        pix = QPixmap.fromImage(q_img)
        sz = pix.size() * self.zoom_factor
        self.canvas.setPixmap(pix.scaled(sz, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.canvas.setFixedSize(sz)

    def mouseMoveEvent(self, event):
        if self.cv_img is not None and (event.buttons() & Qt.LeftButton):
            curr = self.canvas.mapFrom(self, event.position().toPoint())
            if self.last_point:
                o_last, o_curr = self.last_point / self.zoom_factor, curr / self.zoom_factor
                thickness = int(self.brush_size / self.zoom_factor)
                color = 255 if self.rb_paint.isChecked() else 0
                cv2.line(self.mask, (int(o_last.x()), int(o_last.y())), (int(o_curr.x()), int(o_curr.y())), color, thickness)
                self.last_point = curr
                self.update_display()

    def mousePressEvent(self, event):
        if self.cv_img is not None:
            self.save_history()
            self.last_point = self.canvas.mapFrom(self, event.position().toPoint())

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.cv_img is not None:
            p = QPainter(self)
            pos = self.mapFromGlobal(QCursor.pos())
            r = (self.brush_size * self.zoom_factor) / 2
            p.setPen(QPen(QColor(0, 212, 255, 150), 2))
            p.drawEllipse(pos, r, r)

    def load_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            valid_exts = ('.png', '.jpg', '.jpeg', '.webp')
            files = [os.path.join(path, f) for f in sorted(os.listdir(path)) if f.lower().endswith(valid_exts)]
            self.file_list.clear()
            for f in files: self.file_list.addItem(f)

    def action_scan(self):
        if self.is_processing or self.cv_img is None: return
        self.save_history()
        self.toggle_ui(False)
        self.thread = QThread()
        self.worker = AIWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(lambda: self.worker.run_scan(self.cv_img, self.lang_combo.currentText()))
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def on_scan_finished(self, mask):
        self.mask = mask
        self.toggle_ui(True)
        self.update_display()

    def action_clean(self):
        if self.is_processing or self.cv_img is None or np.count_nonzero(self.mask) == 0: return
        self.save_history()
        self.toggle_ui(False)
        self.thread = QThread()
        self.worker = AIWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(lambda: self.worker.run_clean(self.cv_img, self.mask, self.lama, self.device))
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_clean_finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def on_clean_finished(self, res):
        self.cv_img = res
        self.mask = np.zeros_like(self.mask)
        self.toggle_ui(True)
        self.update_display()
        self.progress_bar.setValue(0)

    def toggle_ui(self, enabled):
        self.is_processing = not enabled
        self.btn_clean.setEnabled(enabled)
        self.btn_scan.setEnabled(enabled)
        self.file_list.setEnabled(enabled)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo_action)
        QShortcut(QKeySequence("Ctrl+S"), self, self.export_final_image)
        QShortcut(QKeySequence("B"), self, lambda: self.rb_paint.setChecked(True))
        QShortcut(QKeySequence("E"), self, lambda: self.rb_erase.setChecked(True))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        import qdarktheme
        app.setStyleSheet(qdarktheme.load_stylesheet("dark"))
    except ImportError:
        pass
    
    win = TitanStudioV1()
    win.show()
    sys.exit(app.exec())