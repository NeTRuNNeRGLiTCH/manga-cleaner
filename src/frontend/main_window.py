import os
import re
import cv2
import numpy as np
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame, QSplitter, QFileDialog,
                             QMenu, QMessageBox, QGraphicsView, QProgressBar,
                             QDialog, QCheckBox, QColorDialog, QStackedWidget)
from PySide6.QtGui import QShortcut, QKeySequence, QImage, QPainterPath, QColor
from PySide6.QtCore import Qt, QTimer, QThread
from enum import Enum, auto
from src.frontend.widgets import (FileListWidget, ToolGroup, LabeledSlider, 
                                HardwareMonitor, CategorySelector, ColorSwatchButton)
from src.utils.i18n import tr, tr_label
from src.frontend.canvas import MangaCanvas
from src.frontend.help_system import HelpSystem
from src.utils.system_info import SystemMonitor
from src.utils.history import HistoryManager
from src.utils.config import Config
from src.utils.logger import logger
from src.utils.paths import Paths
from src.utils import i18n
from src.backend.batch_engine import BatchEngine
from src.backend.model_manager import MODEL_SPECS, ModelManager
from src.frontend.batch_setup_dialog import BatchSetupDialog
from src.frontend.model_manager_dialog import ModelManagerDialog
from src.frontend.typesetter_panel import TypesetterPanel
from src.frontend.project_reset import ProjectResetController


#/////////////////////////////////#
#          PAGE STATE ENUM        #
#/////////////////////////////////#
class PageState(Enum):
    UNMODIFIED = auto()
    MODIFIED = auto()
    WAITING = auto()
    READY = auto()
    ERROR = auto()


#/////////////////////////////////#
#     STUDIO MAIN CONTROLLER      #
#/////////////////////////////////#

class MainWindow(QMainWindow):
    def __init__(self):
        """Initialize the main window, shared application state, and startup services."""
        super().__init__()
        self.setWindowTitle(tr("main.app_name_v_version", app_name=Config.APP_NAME, version=Config.VERSION))
        self.resize(1500, 900)

        self.monitor = SystemMonitor()
        self.history = HistoryManager(Config.MAX_HISTORY)
        self.batch_engine = BatchEngine()
        self.worker_thread = None
        self.is_batching = False
        
        # Tool & Category States
        self.current_category = "CLEANER"
        self.last_cleaner_tool = "BRUSH"
        self.is_alt_erasing = False 
        self.is_alt_brushing = False 
        self.is_space_moving = False
        self.pre_space_tool = "NONE"

        
        self.current_img_path = None
        self.batch_scan_type = "ocr"
        self.image_sessions = {}
        self.pending_page_texts = {}  # Single source of truth for unplaced .txt dialogues
        self.page_states = {}
        self.task_queue = []
        self.total_tasks = 0
        self.completed_tasks = 0
        self.total_lama_tasks = 0
        self.completed_lama_tasks = 0
        
        self.init_ui()
        self.setup_shortcuts()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_telemetry)
        self.timer.start(2000)
        QTimer.singleShot(600, self.prompt_model_setup_on_first_run)
        logger.info("--- STUDIO INTERFACE READY ---")

    def prompt_model_setup_on_first_run(self):
        """Offer optional model downloads once when the application has no models."""
        missing = [key for key in MODEL_SPECS if not ModelManager.is_available(key)]
        marker_path = os.path.join(Paths.CACHE, "model_setup_prompted")
        if not missing or os.path.exists(marker_path):
            return

        try:
            with open(marker_path, "w", encoding="utf-8") as marker:
                marker.write("shown")
        except OSError as exc:
            logger.warning(f"Could not save first-run model prompt state: {exc}")

        dialog = ModelManagerDialog(self, model_keys=missing, setup_mode=True)
        dialog.exec()

    def open_model_manager(self):
        """Open the model information and download window for all AI models."""
        dialog = ModelManagerDialog(self, model_keys=list(MODEL_SPECS))
        dialog.exec()

    def ensure_model_available(self, model_key):
        """Prompt to download a missing model and return whether it is ready."""
        if ModelManager.is_available(model_key):
            return True

        model_name = ModelManager.model_name(model_key)
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Warning)
        message.setWindowTitle(tr("models.model_required_title"))
        message.setText(tr("models.model_required_message", model=model_name))
        download_button = message.addButton(
            tr("models.download_model"), QMessageBox.AcceptRole
        )
        message.addButton(tr("common.cancel"), QMessageBox.RejectRole)
        message.exec()
        if message.clickedButton() != download_button:
            return False

        dialog = ModelManagerDialog(self, model_keys=[model_key])
        dialog.exec()
        return ModelManager.is_available(model_key)

    def init_ui(self):
        """Build the application shell, navigation, canvas, and category workspaces."""
        self.central = QWidget()
        self.setCentralWidget(self.central)
        main_lay = QVBoxLayout(self.central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        #/////////////////////////////////#
        #           NAVIGATION            #
        #/////////////////////////////////#
        self.nav = QFrame()
        self.nav.setObjectName("NavBar")
        self.nav.setFixedHeight(60)
        nav_lay = QHBoxLayout(self.nav)
        
        title = QLabel(f"{Config.APP_NAME.upper()} {Config.VERSION}")
        title.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold; font-size: 18px;")

        btn_reset = QPushButton(tr("main.reset"))
        btn_reset.setObjectName("ActionBtn")
        btn_reset.setToolTip(
            tr("main.close_the_current_project_in_memory")
        )
        btn_reset.clicked.connect(lambda: ProjectResetController.reset(self))

        self.hw_mon = HardwareMonitor()
        
        btn_help = QPushButton(tr("main.help"))
        btn_help.clicked.connect(lambda: HelpSystem.show_guide(self))
        
        btn_open = QPushButton(tr("main.import_folder"))
        btn_open.clicked.connect(self.on_open_folder)
        
        self.btn_editor = QPushButton(tr("main.send_to_editor"))
        ed_menu = QMenu(self)
        
        ps_action = ed_menu.addAction(tr("main.adobe_photoshop"))
        ps_action.triggered.connect(lambda: self.on_editor_bridge("photoshop"))
        if os.name != 'nt':
            ps_action.setEnabled(False)
            ps_action.setText(tr("main.adobe_photoshop"))
            
        ed_menu.addAction(tr("main.photopea_web")).triggered.connect(lambda: self.on_editor_bridge("photopea"))
        self.btn_editor.setMenu(ed_menu)
        
        self.btn_export = QPushButton(tr("main.export"))
        self.btn_export.setObjectName("PrimaryBtn")
        exp_menu = QMenu(self)
        exp_menu.addAction(tr("main.export_as_jpg")).triggered.connect(lambda: self.on_export("jpg"))
        exp_menu.addAction(tr("main.export_as_png")).triggered.connect(lambda: self.on_export("png"))
        self.btn_export.setMenu(exp_menu)

        self.btn_language = QPushButton(f"🌐 {i18n.current_language().upper()}")
        self.btn_language.setObjectName("ActionBtn")
        self.btn_language.setToolTip(tr("main.select_language"))
        language_menu = QMenu(self)
        automatic_label = tr("main.automatic_system_language")
        automatic_action = language_menu.addAction(automatic_label)
        automatic_action.triggered.connect(
            lambda _checked=False: self.on_language_selected("auto", automatic_label)
        )
        language_menu.addSeparator()
        for language_code, display_name in i18n.available_languages():
            language_action = language_menu.addAction(display_name)
            language_action.triggered.connect(
                lambda _checked=False, code=language_code, name=display_name:
                    self.on_language_selected(code, name)
            )
        self.btn_language.setMenu(language_menu)

        # Let translated labels determine button width through each button's sizeHint.
        btn_models = QPushButton(tr("models.manage"))
        btn_models.clicked.connect(self.open_model_manager)

        for nav_button in (self.btn_language, btn_help, btn_models, btn_open, btn_reset, self.btn_editor, self.btn_export):
            nav_button.setMinimumHeight(30)

        nav_lay.addWidget(title)
        nav_lay.addStretch()
        nav_lay.addWidget(self.hw_mon)
        nav_lay.addSpacing(10)
        nav_lay.addWidget(self.btn_language)
        nav_lay.addWidget(btn_help)
        nav_lay.addWidget(btn_models)
        nav_lay.addWidget(btn_open)
        nav_lay.addWidget(btn_reset)
        nav_lay.addWidget(self.btn_editor)
        nav_lay.addWidget(self.btn_export)
        main_lay.addWidget(self.nav)

        split = QSplitter(Qt.Horizontal)
        
        #/////////////////////////////////#
        #           LEFT PANEL            #
        #/////////////////////////////////#
        self.lp = QFrame()
        self.lp.setObjectName("SidePanel")
        lp_lay = QVBoxLayout(self.lp)
        
        header_lay = QHBoxLayout()
        self.chk_all = QCheckBox()
        self.chk_all.toggled.connect(self.toggle_all_files)
        lbl_assets = QLabel(tr("main.project_assets"))
        lbl_assets.setStyleSheet("color: #888888; font-weight: bold;")
        header_lay.addWidget(self.chk_all)
        header_lay.addWidget(lbl_assets)
        header_lay.addStretch()

        self.file_list = FileListWidget()
        self.file_list.itemClicked.connect(self.on_file_clicked)
        self.btn_batch = QPushButton(tr("main.run_batch_process"))
        self.btn_batch.setObjectName("ActionBtn")
        self.btn_batch.clicked.connect(self.on_start_batch)
        
        lp_lay.addLayout(header_lay)
        lp_lay.addWidget(self.file_list)
        lp_lay.addWidget(self.btn_batch)

        #/////////////////////////////////#
        #             CANVAS              #
        #/////////////////////////////////#
        self.canvas = MangaCanvas()
        self.canvas.mask_changed.connect(lambda: self.history.push_mask_state(self.canvas.mask))
        self.canvas.mask_changed.connect(self.mark_current_modified)
        self.canvas.image_patch_created.connect(self.on_manual_image_patch)
        self.canvas.clean_color_picked.connect(self.on_clean_color_picked)
        self.canvas.text_modified.connect(self.mark_current_modified)
        self.canvas.texts_list_changed.connect(self.refresh_page_text_list)
        
        #/////////////////////////////////#
        #      RIGHT PANEL (CATEGORIZED)  #
        #/////////////////////////////////#
        self.rp = QFrame()
        self.rp.setObjectName("SidePanel")
        rp_lay = QVBoxLayout(self.rp)
        rp_lay.setSpacing(6)
        
        self.cat_lbl = QLabel(tr("main.category_cleaner"))
        self.cat_lbl.setStyleSheet(f"color: {Config.COLOR_TEXT}; font-weight: bold; font-size: 11px;")
        rp_lay.addWidget(self.cat_lbl)

        self.mode_lbl = QLabel(tr("main.mode_painting"))
        self.mode_lbl.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold; font-size: 10px;")
        rp_lay.addWidget(self.mode_lbl)

        # 4-Category Switcher Grid (CLEANER | TYPESETTER | STITCHER | TRANSLATOR)
        self.cat_selector = CategorySelector(["CLEANER", "TYPESETTER", "STITCHER", "TRANSLATOR"])
        self.cat_selector.category_changed.connect(self.set_category)
        rp_lay.addWidget(self.cat_selector)

        self.category_stack = QStackedWidget()

        # ==========================================
        # PAGE 0: CLEANER CATEGORY WORKSPACE
        # ==========================================
        self.cleaner_page = QWidget()
        cl_lay = QVBoxLayout(self.cleaner_page)
        cl_lay.setContentsMargins(0, 0, 0, 0)
        cl_lay.setSpacing(6)

        self.tools = ToolGroup(
            tr("main.cleaner_mask_tools"),
            ["MOVE", "BRUSH", "ERASER", "RECT", "LASSO", "POLY", "BUCKET", "CLEAR", "MANUAL"],
            full_width_buttons=["MANUAL"]
        )
        self.tools.buttons["MOVE"].clicked.connect(lambda: self.set_tool("NONE"))
        self.tools.buttons["BRUSH"].clicked.connect(lambda: self.set_tool("BRUSH"))
        self.tools.buttons["ERASER"].clicked.connect(lambda: self.set_tool("ERASER"))
        self.tools.buttons["RECT"].clicked.connect(lambda: self.set_tool("RECT"))
        self.tools.buttons["LASSO"].clicked.connect(lambda: self.set_tool("LASSO"))
        self.tools.buttons["POLY"].clicked.connect(lambda: self.set_tool("POLY"))
        self.tools.buttons["BUCKET"].clicked.connect(lambda: self.set_tool("BUCKET"))
        self.tools.buttons["CLEAR"].clicked.connect(self.canvas.clear_mask)
        self.tools.buttons["MANUAL"].setToolTip(tr("main.manual_cleaner_brush_d_paint_directly"))
        self.tools.buttons["MANUAL"].clicked.connect(lambda: self.set_tool("PAINT"))

        # Contextual Manual Cleaner Sub-Bar (Only visible when MANUAL / PICKER is active!)
        self.manual_col_frame = QFrame()
        mc_lay = QHBoxLayout(self.manual_col_frame)
        mc_lay.setContentsMargins(5, 2, 5, 2)
        mc_lay.setSpacing(6)

        self.btn_picker = QPushButton(tr("main.picker_i"))
        self.btn_picker.setCheckable(True)
        self.btn_picker.setToolTip(tr("main.eyedropper_color_picker_i_click_on"))
        self.btn_picker.clicked.connect(lambda: self.set_tool("PICKER"))

        self.swatch_manual_clean = ColorSwatchButton(
            QColor(255, 255, 255), width=42, height=24, tooltip=tr("main.click_to_choose_manual_cleaner_color")
        )
        self.swatch_manual_clean.clicked.connect(self.choose_manual_clean_color)

        btn_white_reset = QPushButton(tr("main.white"))
        btn_white_reset.setToolTip(tr("main.reset_manual_paint_color_to_pure"))
        btn_white_reset.clicked.connect(lambda: self.on_clean_color_picked(QColor(255, 255, 255)))

        mc_lay.addWidget(self.btn_picker, 1)
        mc_lay.addWidget(self.swatch_manual_clean)
        mc_lay.addWidget(btn_white_reset)
        self.manual_col_frame.setVisible(False)

        self.b_slider = LabeledSlider(tr("main.brush_size"), 40, 1, 300, self.canvas.set_brush_size)
        self.o_slider = LabeledSlider(tr("main.mask_opacity"), 60, 0, 100, self.canvas.set_mask_opacity, suffix="%")
        self.t_slider = LabeledSlider(tr("main.max_tile_size"), 2048, 512, 4096, is_tile=True)
        
        self.canvas.brush_size_changed.connect(self.b_slider.slider.setValue)
        
        btn_scan = QPushButton(tr("main.ocr_scan_o"))
        btn_scan.setObjectName("ActionBtn")
        btn_scan.clicked.connect(self.on_ocr_scan)

        btn_trans = QPushButton(tr("main.transparency_scan_t"))
        btn_trans.setObjectName("ActionBtn")
        btn_trans.clicked.connect(self.on_transparency_scan)
        
        self.btn_clean = QPushButton(tr("main.execute_clean_c"))
        self.btn_clean.setObjectName("PrimaryBtn")
        self.btn_clean.setFixedHeight(45)
        self.btn_clean.clicked.connect(self.on_lama_clean)
        
        self.queue_lbl = QLabel(tr("main.processing_queued_0"))
        self.queue_lbl.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.queue_lbl.setAlignment(Qt.AlignCenter)

        cl_lay.addWidget(self.tools)
        cl_lay.addWidget(self.manual_col_frame)
        cl_lay.addWidget(self.b_slider)
        cl_lay.addWidget(self.o_slider)
        cl_lay.addSpacing(8)
        cl_lay.addWidget(btn_scan)
        cl_lay.addWidget(btn_trans)
        cl_lay.addWidget(self.t_slider)
        cl_lay.addWidget(self.btn_clean)
        cl_lay.addWidget(self.queue_lbl)
        cl_lay.addStretch()

        # PAGE 1: TYPESETTER CATEGORY WORKSPACE
        self.typesetter_panel = TypesetterPanel(self)
        self.typesetter_page = self.typesetter_panel
        self.canvas.text_selected.connect(self.typesetter_panel.sync_text_ui_from_item)

        # ==========================================
        # PAGE 2: STITCHER CATEGORY WORKSPACE (constructed on first use)
        # ==========================================
        self.stitcher_page = None
        self.stitcher_container = QWidget()
        self.stitcher_layout = QVBoxLayout(self.stitcher_container)
        self.stitcher_layout.setContentsMargins(0, 0, 0, 0)

        # ==========================================
        # PAGE 3: TRANSLATOR CATEGORY WORKSPACE (constructed on first use)
        # ==========================================
        self.translator_page = None
        self.translator_container = QWidget()
        self.translator_layout = QVBoxLayout(self.translator_container)
        self.translator_layout.setContentsMargins(0, 0, 0, 0)

        # Add all 4 Category Pages to Stack
        self.category_stack.addWidget(self.cleaner_page)     # Index 0: CLEANER
        self.category_stack.addWidget(self.typesetter_page)  # Index 1: TYPESETTER
        self.category_stack.addWidget(self.stitcher_container)    # Index 2: STITCHER
        self.category_stack.addWidget(self.translator_container)  # Index 3: TRANSLATOR

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(10)

        rp_lay.addWidget(self.category_stack, 1)
        rp_lay.addWidget(self.progress_bar)
        
        split.addWidget(self.lp)
        split.addWidget(self.canvas)
        split.addWidget(self.rp)
        split.setSizes([220, 1000, 250])
        main_lay.addWidget(split, 1)

        self.set_category("CLEANER")

    #/////////////////////////////////#
    #    CATEGORY & TOOL SWITCHING    #
    #/////////////////////////////////#

    def set_category(self, category: str):
        """Switch the active workspace and initialize deferred panels when needed."""
        self.current_category = category
        self.cat_lbl.setText(tr("main.category_category", category=tr_label(category)))

        for name, btn in self.cat_selector.buttons.items():
            btn.blockSignals(True)
            btn.setChecked(name == category)
            btn.blockSignals(False)

        if category == "CLEANER":
            self.category_stack.setCurrentIndex(0)
            self.canvas.mask_item.setVisible(True)
            target_tool = self.last_cleaner_tool if self.last_cleaner_tool != "TEXT" else "BRUSH"
            self.set_tool(target_tool, switch_category=False)

        elif category == "TYPESETTER":
            # Font enumeration and combo population can be expensive on systems
            # with many installed fonts, so do this only when needed.
            if self.typesetter_panel.all_system_fonts is None:
                self.typesetter_panel.populate_font_combo()
            self.category_stack.setCurrentIndex(1)
            self.set_tool("TEXT", switch_category=False)

        elif category == "STITCHER":
            if self.stitcher_page is None:
                from src.backend.stitcher import StitcherPanel

                self.stitcher_page = StitcherPanel(self)
                self.stitcher_layout.addWidget(self.stitcher_page)
            self.category_stack.setCurrentIndex(2)
            self.set_tool("NONE", switch_category=False)

        elif category == "TRANSLATOR":
            if self.translator_page is None:
                from src.backend.translator import TranslatorPanel

                self.translator_page = TranslatorPanel(self)
                self.translator_layout.addWidget(self.translator_page)
            self.category_stack.setCurrentIndex(3)
            self.set_tool("TEXT", switch_category=False)

    def set_tool(self, tool, switch_category=True):
        """Activate a canvas tool and synchronize its visual and category state."""
        if switch_category:
            if tool == "TEXT" and self.current_category not in ("TYPESETTER", "TRANSLATOR"):
                self.set_category("TYPESETTER")
                return
            elif tool in ["BRUSH", "ERASER", "RECT", "LASSO", "POLY", "BUCKET", "PAINT", "PICKER"] and self.current_category != "CLEANER":
                self.last_cleaner_tool = tool
                self.set_category("CLEANER")
                return

        if tool in ["BRUSH", "ERASER", "RECT", "LASSO", "POLY", "BUCKET", "PAINT", "PICKER"]:
            self.last_cleaner_tool = tool

        if self.canvas.current_tool == "POLY" and tool != "POLY":
            self.canvas.poly_points.clear()
            self.canvas.preview_item.setPath(QPainterPath())

        if self.canvas.is_editing_text() and tool != "TEXT":
            self.canvas.scene.focusItem().clearFocus()

        self.canvas.current_tool = tool

        for grp in (self.tools, self.typesetter_panel.type_tools):
            for btn in grp.buttons.values():
                btn.setAutoExclusive(False)
                btn.setChecked(False)
                btn.setAutoExclusive(True)

        # Show Manual Color & Picker bar ONLY when in Manual Clean mode (PAINT or PICKER)
        is_manual_mode = tool in ("PAINT", "PICKER")
        self.manual_col_frame.setVisible(is_manual_mode)
        self.btn_picker.blockSignals(True)
        self.btn_picker.setChecked(tool == "PICKER")
        self.btn_picker.blockSignals(False)

        self.canvas.scene.update()
        self.canvas.update_cursor_visuals()
        
        if tool == "NONE":
            self.canvas.setDragMode(QGraphicsView.ScrollHandDrag)
            self.canvas.viewport().unsetCursor()
            self.canvas.cursor_item.hide()
            if self.current_category == "CLEANER":
                self.tools.buttons["MOVE"].setChecked(True)
            elif self.current_category == "TYPESETTER":
                self.typesetter_panel.type_tools.buttons["MOVE"].setChecked(True)
            self.mode_lbl.setText(tr("main.mode_moving"))
            self.mode_lbl.setStyleSheet("color: #888888; font-weight: bold;")
            
        else:
            self.canvas.setDragMode(QGraphicsView.NoDrag)
            
            if tool in ["BRUSH", "ERASER", "PAINT"]:
                if not self.canvas.is_locked:
                    self.canvas.viewport().setCursor(Qt.BlankCursor)
                    self.canvas.cursor_item.show()
                else:
                    self.canvas.viewport().unsetCursor()
            elif tool == "TEXT":
                if not self.canvas.is_locked:
                    self.canvas.viewport().setCursor(Qt.IBeamCursor)
                else:
                    self.canvas.viewport().unsetCursor()
                self.canvas.cursor_item.hide()
            else:
                if not self.canvas.is_locked:
                    self.canvas.viewport().setCursor(Qt.CrossCursor)
                else:
                    self.canvas.viewport().unsetCursor()
                self.canvas.cursor_item.hide()
            
            if tool == "TEXT":
                self.typesetter_panel.type_tools.buttons["TEXT"].setChecked(True)
            elif tool in ("PAINT", "PICKER"):
                self.tools.buttons["MANUAL"].setChecked(True)
            elif tool in self.tools.buttons:
                self.tools.buttons[tool].setChecked(True)
            
            if tool == "ERASER":
                self.mode_lbl.setText(tr("main.mode_erasing_mask"))
                self.mode_lbl.setStyleSheet("color: #00d4ff; font-weight: bold;")
            elif tool == "BUCKET":
                self.mode_lbl.setText(tr("main.mode_filling_mask"))
                self.mode_lbl.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold;")
            elif tool == "PAINT":
                self.mode_lbl.setText(tr("main.mode_manual_clean_brush"))
                self.mode_lbl.setStyleSheet("color: #00ff8c; font-weight: bold;")
            elif tool == "PICKER":
                self.mode_lbl.setText(tr("main.mode_color_picker"))
                self.mode_lbl.setStyleSheet("color: #00ff8c; font-weight: bold;")
            elif tool == "TEXT":
                self.mode_lbl.setText(tr("main.mode_typesetting"))
                self.mode_lbl.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold;")
            else:
                self.mode_lbl.setText(tr("main.mode_painting_mask"))
                self.mode_lbl.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold;")

    # --- MANUAL CLEANER HANDLERS ---
    def on_manual_image_patch(self, x, y, old_patch):
        """Record a manual image edit in history and mark the current page as modified."""
        self.history.push_image_action(x, y, old_patch)
        self.mark_current_modified()

    def on_clean_color_picked(self, color: QColor):
        """Apply a color selected from the canvas to the manual-clean brush."""
        self.canvas.manual_clean_color = QColor(color)
        self.swatch_manual_clean.set_color(color)
        self.canvas.update_cursor_visuals()
        if self.canvas.current_tool == "PICKER":
            self.set_tool("PAINT", switch_category=False)

    def choose_manual_clean_color(self):
        """Open a color picker for the manual-clean brush."""
        c = QColorDialog.getColor(self.canvas.manual_clean_color, self, tr("main.select_manual_cleaner_brush_color"))
        if c.isValid():
            self.on_clean_color_picked(c)

    # --- TYPESETTER COMPATIBILITY DELEGATES ---
    def _run_if_not_typing(self, func):
        """Run a shortcut action only when the canvas is not editing text."""
        if not self.canvas.is_editing_text():
            func()

    def refresh_page_text_list(self):
        """Delegate text-layer list refreshes to the Typesetter panel."""
        if hasattr(self, "typesetter_panel"):
            self.typesetter_panel.refresh_page_text_list()

    def spawn_pending_text_by_index(self, p_idx: int):
        """Delegate queued dialogue placement to the Typesetter panel."""
        self.typesetter_panel.spawn_pending_text_by_index(p_idx)
    def setup_shortcuts(self):
        """Register keyboard shortcuts for tools, scans, cleanup, and history."""
        QShortcut(QKeySequence("B"), self).activated.connect(lambda: self._run_if_not_typing(lambda: self.set_tool("BRUSH")))
        QShortcut(QKeySequence("E"), self).activated.connect(lambda: self._run_if_not_typing(lambda: self.set_tool("ERASER")))
        QShortcut(QKeySequence("R"), self).activated.connect(lambda: self._run_if_not_typing(lambda: self.set_tool("RECT")))
        QShortcut(QKeySequence("L"), self).activated.connect(lambda: self._run_if_not_typing(lambda: self.set_tool("LASSO")))
        QShortcut(QKeySequence("P"), self).activated.connect(lambda: self._run_if_not_typing(lambda: self.set_tool("POLY")))
        QShortcut(QKeySequence("G"), self).activated.connect(lambda: self._run_if_not_typing(lambda: self.set_tool("BUCKET")))
        QShortcut(QKeySequence("D"), self).activated.connect(lambda: self._run_if_not_typing(lambda: self.set_tool("PAINT")))
        QShortcut(QKeySequence("I"), self).activated.connect(lambda: self._run_if_not_typing(lambda: self.set_tool("PICKER")))
        QShortcut(QKeySequence("X"), self).activated.connect(lambda: self._run_if_not_typing(lambda: self.set_tool("TEXT")))
        QShortcut(QKeySequence("M"), self).activated.connect(lambda: self._run_if_not_typing(lambda: self.set_tool("NONE")))
        
        QShortcut(QKeySequence("O"), self).activated.connect(lambda: self._run_if_not_typing(self.on_ocr_scan))
        QShortcut(QKeySequence("T"), self).activated.connect(lambda: self._run_if_not_typing(self.on_transparency_scan))
        QShortcut(QKeySequence("C"), self).activated.connect(lambda: self._run_if_not_typing(self.on_lama_clean))
        QShortcut(QKeySequence("Delete"), self).activated.connect(lambda: self._run_if_not_typing(self.canvas.delete_selected_texts))
        
        QShortcut(QKeySequence("Alt+Z"), self).activated.connect(lambda: self._run_if_not_typing(self.on_undo_image))
        QShortcut(QKeySequence("Alt+Shift+Z"), self).activated.connect(lambda: self._run_if_not_typing(self.on_redo_image))
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(lambda: self._run_if_not_typing(self.on_smart_ctrl_z))
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(lambda: self._run_if_not_typing(self.on_smart_ctrl_shift_z))

    def keyPressEvent(self, event):
        """Handle window-level key presses that modify canvas interaction state."""
        if self.canvas.is_editing_text():
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key_Alt and not event.isAutoRepeat():
            if self.canvas.current_tool == "BRUSH":
                self.is_alt_erasing = True
                self.set_tool("ERASER", switch_category=False)
            elif self.canvas.current_tool == "ERASER":
                self.is_alt_brushing = True
                self.set_tool("BRUSH", switch_category=False)
                
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            if not getattr(self, 'is_space_moving', False):
                self.is_space_moving = True
                self.pre_space_tool = self.canvas.current_tool
                self.set_tool("NONE", switch_category=False)
                
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Restore interaction state when temporary modifier keys are released."""
        if self.canvas.is_editing_text():
            super().keyReleaseEvent(event)
            return

        if event.key() == Qt.Key_Alt and not event.isAutoRepeat():
            if getattr(self, 'is_alt_erasing', False):
                self.is_alt_erasing = False
                if self.canvas.current_tool == "ERASER":
                    self.set_tool("BRUSH", switch_category=False)
            elif getattr(self, 'is_alt_brushing', False):
                self.is_alt_brushing = False
                if self.canvas.current_tool == "BRUSH":
                    self.set_tool("ERASER", switch_category=False)
                    
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            if getattr(self, 'is_space_moving', False):
                self.is_space_moving = False
                if self.canvas.current_tool == "NONE":
                    self.set_tool(self.pre_space_tool, switch_category=False)
                    
        super().keyReleaseEvent(event)

    def toggle_all_files(self, checked):
        """Select or clear all entries in the project file list."""
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.file_list.count()):
            self.file_list.item(i).setCheckState(state)

    #/////////////////////////////////#
    #        HISTORY OPERATIONS       #
    #/////////////////////////////////#

    def on_smart_ctrl_z(self):
        """Route Ctrl+Z to text editing or image history as appropriate."""
        if self.canvas.current_tool in ("PAINT", "PICKER"):
            self.on_undo_image()
        else:
            self.on_undo_mask()

    def on_smart_ctrl_shift_z(self):
        """Route Ctrl+Shift+Z to text editing or image redo as appropriate."""
        if self.canvas.current_tool in ("PAINT", "PICKER"):
            self.on_redo_image()
        else:
            self.on_redo_mask()

    def on_undo_image(self):
        """Undo the most recent image or mask operation."""
        if self.canvas.is_locked: return
        res = self.history.pop_image_undo(self.canvas.cv_img)
        if res:
            x, y, p = res
            self.mark_current_modified()
            self.canvas.cv_img[y:y+p.shape[0], x:x+p.shape[1]] = p
            self.canvas.refresh_image_pixmap()

    def on_redo_image(self):
        """Redo the most recently undone image or mask operation."""
        if self.canvas.is_locked: return
        res = self.history.pop_image_redo(self.canvas.cv_img)
        if res:
            x, y, p = res
            self.mark_current_modified()
            self.canvas.cv_img[y:y+p.shape[0], x:x+p.shape[1]] = p
            self.canvas.refresh_image_pixmap()

    def on_undo_mask(self):
        """Restore the previous canvas mask from history."""
        if self.canvas.is_locked: return
        res = self.history.pop_mask_undo(self.canvas.mask)
        if res:
            self.mark_current_modified()
            self.canvas.mask = res
            self.canvas.update_mask_display()

    def on_redo_mask(self):
        """Reapply the next canvas mask state from history."""
        if self.canvas.is_locked: return
        res = self.history.pop_mask_redo(self.canvas.mask)
        if res:
            self.mark_current_modified()
            self.canvas.mask = res
            self.canvas.update_mask_display()

    #/////////////////////////////////#
    #       AI EXECUTION PIPELINE     #
    #/////////////////////////////////#

    def _check_lock_state(self):
        """Update canvas controls and cursor behavior for the current lock state."""
        locked_paths = set()
        
        if self.worker_thread is not None and hasattr(self, 'worker'):
            active_path = getattr(self.worker, 'source_path', None)
            if active_path: locked_paths.add(active_path)
            
        for item in self.task_queue:
            locked_paths.add(item["path"])
                
        if self.is_batching:
            for idx in range(self.batch_engine.current_index, len(self.batch_engine.files)):
                locked_paths.add(self.batch_engine.files[idx])

        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.UserRole)
            is_locked = (file_path in locked_paths)
            item.setData(Qt.UserRole + 2, is_locked)

        if self.current_img_path:
            self.canvas.set_locked(self.current_img_path in locked_paths)
        else:
            self.canvas.set_locked(False)

    def _update_queue_ui(self):
        """Refresh labels and progress indicators for queued processing tasks."""
        pending = self.total_lama_tasks - self.completed_lama_tasks
        self.queue_lbl.setText(tr("main.processing_queued_pending", pending=pending))

        if pending > 0 and self.total_lama_tasks > 0:
            val = int((self.completed_lama_tasks / self.total_lama_tasks) * 100)
            self.progress_bar.setValue(val)
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)
            self.total_lama_tasks = 0
            self.completed_lama_tasks = 0
            
        self._check_lock_state()

    def on_worker_progress(self, val):
        """Display progress reported by the active background worker."""
        if self.worker.task != "clean" or self.total_lama_tasks == 0: return
        base_progress = (self.completed_lama_tasks / self.total_lama_tasks) * 100
        task_fraction = (val / 100.0) * (100 / self.total_lama_tasks)
        self.progress_bar.setValue(int(base_progress + task_fraction))

    def enqueue_task(self, task, path, *args):
        """Add a processing request to the queue and start queue execution if idle."""
        self.task_queue.append({
            "task": task,
            "path": path,
            "args": args
        })
        self._update_queue_ui()
        self._process_queue()

    def _process_queue(self):
        """Create and launch a worker for the next queued task."""
        if self.worker_thread is not None:
            return

        if not self.task_queue:
            self._update_queue_ui()
            return

        item = self.task_queue.pop(0)
        source_path = item["path"]
        
        self.page_states[source_path] = PageState.WAITING
        self.file_list.update_item_state(source_path, "waiting")

        self.setCursor(Qt.WaitCursor)
        self.worker_thread = QThread()
        from src.backend.workers import AIWorker

        self.worker = AIWorker(item["task"], item["args"])
        self.worker.source_path = source_path

        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.process)
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.finished.connect(self.on_task_finished)
        self.worker.error.connect(self.on_task_error)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()
        self._update_queue_ui() 

    def stop_thread(self):
        """Request cancellation and safely release the active worker thread."""
        self.setCursor(Qt.ArrowCursor)
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
        self._update_queue_ui()

    def on_task_error(self, message):
        """Report a worker failure and advance or stop queued processing."""
        source_path = getattr(self.worker, 'source_path', None)
        task = getattr(self.worker, "task", None)
        task_args = getattr(self.worker, "args", None)
        was_batching = self.is_batching
        if source_path:
            self.page_states[source_path] = PageState.ERROR
            self.file_list.update_item_state(source_path, "error")

        self.stop_thread()
        self.is_batching = False
        self.task_queue.clear()
        self.total_lama_tasks = 0
        self.completed_lama_tasks = 0
        self._update_queue_ui()

        required_model = {"ocr": "ocr", "clean": "lama"}.get(task)
        if required_model and not ModelManager.is_available(required_model):
            if self.ensure_model_available(required_model):
                if was_batching:
                    QMessageBox.information(
                        self,
                        tr("models.download_complete_title"),
                        tr("models.retry_batch_after_download"),
                    )
                else:
                    self.enqueue_task(task, source_path, *(task_args or ()))
            return

        QMessageBox.critical(self, tr("main.hardware_error"), message)

    def _get_final_img_for_path(self, path):
        """Return the latest processed image associated with a source path."""
        is_active = (path == self.current_img_path)
        if is_active:
            return self.canvas.get_composited_image()
        session = self.image_sessions.get(path, {})
        return MangaCanvas.render_texts_onto_cv_img(session.get("img"), session.get("texts", []))

    def on_task_finished(self, result, patches):
        """Apply worker results to the project and continue queued work."""
        task = self.worker.task  
        source_path = getattr(self.worker, 'source_path', self.current_img_path)
        is_active = (source_path == self.current_img_path)

        new_state = PageState.READY if task == "clean" else PageState.MODIFIED
        self.page_states[source_path] = new_state
        self.file_list.update_item_state(source_path, new_state.name.lower())

        if task == "clean":
            self.completed_lama_tasks += 1
            target_history = self.history if is_active else self.image_sessions[source_path]["history"]
            if len(patches) > 0:
                for x, y, p in patches: target_history.push_image_action(x, y, p)

            if is_active:
                self.canvas.set_image(result)
                self.canvas.clear_mask()
            else:
                self.image_sessions[source_path]["img"] = result
                self.image_sessions[source_path]["mask"].fill(Qt.transparent)

        elif task in ["ocr", "transparency"]:
            h, w = result.shape[:2]
            rgba = np.zeros((h, w, 4), dtype=np.uint8)
            rgba[result > 0] = [0, 255, 0, 255] if task == "transparency" else [255, 0, 0, 255]
            new_mask = QImage(rgba.data, w, h, w*4, QImage.Format_ARGB32).copy()

            if is_active:
                self.canvas.mask = new_mask
                self.canvas.update_mask_display()
            else:
                self.image_sessions[source_path]["mask"] = new_mask

        self.stop_thread()

        if self.is_batching:
            if task == "clean":
                final_img = self._get_final_img_for_path(source_path)
                is_last = self._save_batch_current(final_img)
                if is_last is None: return
                if is_last: self.finalize_batch()
                else: self.step_batch()
            elif task in ["ocr", "transparency"]:
                # Scanning creates a mask for later review; only explicit Mask batch mode runs LaMa.
                final_img = self._get_final_img_for_path(source_path)
                is_last = self._save_batch_current(final_img)
                if is_last is None: return
                if is_last: self.finalize_batch()
                else: self.step_batch()

        self._process_queue()

    def on_ocr_scan(self):
        """Queue OCR detection for the active page without cleaning its mask."""
        if self.canvas.cv_img is None or self.canvas.is_locked: return
        if not self.ensure_model_available("ocr"):
            return
        self.mark_current_modified()
        self.enqueue_task("ocr", self.current_img_path, self.canvas.cv_img.copy())

    def on_transparency_scan(self):
        """Queue transparency detection for the active page."""
        if self.canvas.cv_img is None or not self.current_img_path or self.canvas.is_locked: return
        self.mark_current_modified()
        self.enqueue_task("transparency", self.current_img_path, self.canvas.cv_img.copy())

    def on_lama_clean(self):
        """Queue LaMa cleanup using the current mask."""
        if self.canvas.cv_img is None or self.canvas.is_locked: return
        ptr = self.canvas.mask.bits()
        mask_np = np.frombuffer(ptr, np.uint8).reshape((self.canvas.mask.height(), self.canvas.mask.width(), 4))
        mask_gray = mask_np[:, :, 3].copy()

        if not np.any(mask_gray):
            if self.is_batching:
                is_last = self._save_batch_current(self.canvas.get_composited_image())
                if is_last is None: return
                if is_last: self.finalize_batch()
                else: self.step_batch()
            else:
                QMessageBox.information(self, tr("main.nothing_selected"), tr("main.no_mask_area_detected"))
            return

        if not self.ensure_model_available("lama"):
            return

        self.total_lama_tasks += 1
        t_size = self.t_slider.slider.value() * 512
        self.mark_current_modified()
        self.enqueue_task("clean", self.current_img_path, self.canvas.cv_img.copy(), mask_gray, t_size)

    #/////////////////////////////////#
    #    BATCH & PHOTOSHOP BRIDGE     #
    #/////////////////////////////////#

    def _confirm_unplaced_texts(self, target_paths: list) -> bool:
        """Warns the user if any target page still has unplaced [ + ] script lines before exporting."""
        if self.current_img_path:
            self.pending_page_texts[self.current_img_path] = list(self.canvas.pending_texts)

        pages_with_pending = []
        total_pending_lines = 0
        for p in target_paths:
            q = self.pending_page_texts.get(p, [])
            if q:
                pages_with_pending.append(os.path.basename(p))
                total_pending_lines += len(q)

        if not pages_with_pending:
            return True

        preview = ", ".join(pages_with_pending[:5])
        if len(pages_with_pending) > 5:
            preview += f" (+{len(pages_with_pending) - 5} more)"

        ans = QMessageBox.warning(
            self,
            tr("main.unplaced_queued_dialogues"),
            tr("main.there_are_total_pending_lines_unplaced", total_pending_lines=total_pending_lines, count=len(pages_with_pending), preview=preview),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return ans == QMessageBox.Yes

    def _save_batch_current(self, image):
        """Save the current batch image or report the export failure in the UI."""
        try:
            return self.batch_engine.save_current(image)
        except (OSError, cv2.error) as exc:
            index = self.batch_engine.current_index
            if index < len(self.batch_engine.files):
                failed_path = self.batch_engine.files[index]
                self.page_states[failed_path] = PageState.ERROR
                self.file_list.update_item_state(failed_path, "error")

            logger.error(f"Batch export failed: {exc}")
            self.is_batching = False
            self.task_queue.clear()
            self.total_lama_tasks = 0
            self.completed_lama_tasks = 0
            self._update_queue_ui()
            QMessageBox.critical(
                self,
                tr("main.batch_save_failed_title"),
                tr("main.batch_save_failed", error=str(exc)),
            )
            return None

    def on_start_batch(self):
        """Collect batch settings and initialize the batch-processing sequence."""
        if self.file_list.count() == 0: return

        dialog = BatchSetupDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        scan_choice, fmt = dialog.get_results()
        if scan_choice == "Transparency Scan": self.batch_scan_type = "transparency"
        elif scan_choice == "Mask": self.batch_scan_type = "mask"
        elif scan_choice == "none": self.batch_scan_type = "none"
        else: self.batch_scan_type = "ocr"

        paths = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.checkState() == Qt.Checked:
                paths.append(item.data(Qt.UserRole))

        if not paths:
            self.chk_all.setChecked(True)
            paths = [self.file_list.item(i).data(Qt.UserRole) for i in range(self.file_list.count())]

        if not self._confirm_unplaced_texts(paths):
            return

        required_model = {"Mask": "lama", "OCR Scan": "ocr"}.get(scan_choice)
        if required_model and not self.ensure_model_available(required_model):
            return

        try:
            self.batch_engine.initialize_batch(paths, fmt)
        except OSError as exc:
            logger.error(f"Could not initialize batch export: {exc}")
            QMessageBox.critical(
                self,
                tr("main.batch_save_failed_title"),
                tr("main.batch_save_failed", error=str(exc)),
            )
            return

        self.is_batching = True
        if self.batch_scan_type == "mask":
            self.total_lama_tasks += len(paths)
        self.step_batch()
        self._check_lock_state()

    def step_batch(self):
        """Process the next page in the active batch."""
        path = self.batch_engine.get_next()
        if path:
            if path not in self.image_sessions:
                img_data = np.fromfile(path, dtype=np.uint8)
                img = cv2.imdecode(img_data, cv2.IMREAD_UNCHANGED)
                if img is not None:
                    if len(img.shape) == 2: img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
                    elif len(img.shape) == 3 and img.shape[2] == 4: img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
                    else: img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                    self.image_sessions[path] = {
                        "img": img.copy(),
                        "mask": QImage(img.shape[1], img.shape[0], QImage.Format_ARGB32),
                        "history": HistoryManager(Config.MAX_HISTORY),
                        "texts": []
                    }
                    self.image_sessions[path]["mask"].fill(Qt.transparent)

            is_active = (path == self.current_img_path)

            if self.batch_scan_type == "none":
                img_cv = self._get_final_img_for_path(path)
                
                self.page_states[path] = PageState.READY
                self.file_list.update_item_state(path, "ready")
                self._update_queue_ui()
                
                is_last = self._save_batch_current(img_cv)
                if is_last is None: return
                if is_last: self.finalize_batch()
                else: QTimer.singleShot(0, self.step_batch)
                return
                
            elif self.batch_scan_type == "mask":
                mask_q = self.canvas.mask if is_active else self.image_sessions[path]["mask"]
                img_cv = self.canvas.cv_img if is_active else self.image_sessions[path]["img"]

                ptr = mask_q.bits()
                mask_np = np.frombuffer(ptr, np.uint8).reshape((mask_q.height(), mask_q.width(), 4))
                mask_gray = mask_np[:, :, 3].copy()

                if not np.any(mask_gray):
                    self.total_lama_tasks -= 1
                    self.page_states[path] = PageState.READY
                    self.file_list.update_item_state(path, "ready")
                    self._update_queue_ui()
                    
                    is_last = self._save_batch_current(self._get_final_img_for_path(path))
                    if is_last is None: return
                    if is_last: self.finalize_batch()
                    else: QTimer.singleShot(0, self.step_batch)
                    return

                t_size = self.t_slider.slider.value() * 512
                self.enqueue_task("clean", path, img_cv.copy(), mask_gray, t_size)
            else:
                img_cv = self.canvas.cv_img if is_active else self.image_sessions[path]["img"]
                self.enqueue_task(self.batch_scan_type, path, img_cv.copy())

    def finalize_batch(self):
        """Finish batch processing and update the project with its results."""
        self.is_batching = False
        self._check_lock_state()
        
        self.setCursor(Qt.WaitCursor)
        if self.batch_engine.export_format == "photoshop":
            from src.backend.photoshop import PhotoshopBridge

            PhotoshopBridge.open_batch_in_ps(self.batch_engine.files, self.batch_engine.output_dir)
        elif self.batch_engine.export_format == "photopea":
            from src.backend.photopea import PhotopeaBridge

            PhotopeaBridge.open_batch_in_photopea(self.batch_engine.files, self.batch_engine.output_dir)
        self.setCursor(Qt.ArrowCursor)
            
        if self.batch_engine.export_format == "none":
            QMessageBox.information(self, tr("main.batch_complete"), tr("main.all_selected_pages_processed_and_updated"))
        else:
            QMessageBox.information(self, tr("main.batch_complete"), tr("main.saved_to_output_dir", output_dir=self.batch_engine.output_dir))

    #/////////////////////////////////#
    #         FILE OPERATIONS         #
    #/////////////////////////////////#

    def on_open_folder(self):
        """Choose an image folder and load its files into the project."""
        p = QFileDialog.getExistingDirectory(self, tr("main.select_folder"))
        if p:
            self.image_sessions.clear()
            self.pending_page_texts.clear()
            self.page_states.clear()
            self.file_list.clear()
            self.canvas.clear_texts()
            self.current_img_path = None
            natural_key = lambda name: [int(s) if s.isdigit() else s.lower() for s in re.split(r"(\d+)", name)]
            for f in sorted(os.listdir(p), key=natural_key):
                if f.lower().endswith(('.jpg','.jpeg','.png','.webp')):
                    full_path = os.path.join(p, f)
                    self.page_states[full_path] = PageState.UNMODIFIED
                    self.file_list.add_file(full_path)
            if self.stitcher_page is not None:
                self.stitcher_page.clear_blocks()
            if self.translator_page is not None:
                self.translator_page.refresh_active_page_preview()

    def mark_current_modified(self):
        """Mark the active page as modified and update its project status."""
        if self.current_img_path:
            if self.page_states.get(self.current_img_path) != PageState.MODIFIED:
                self.page_states[self.current_img_path] = PageState.MODIFIED
                self.file_list.update_item_state(self.current_img_path, "modified")

    def on_file_clicked(self, it):
        """Load the selected project image and restore its page-specific state."""
        path_real = it.data(Qt.UserRole)
        if path_real == self.current_img_path: return 

        # 1. Save outgoing page state before changing current_img_path
        if self.current_img_path and self.canvas.cv_img is not None:
            self.pending_page_texts[self.current_img_path] = list(self.canvas.pending_texts)
            self.image_sessions[self.current_img_path] = {
                "img": self.canvas.cv_img.copy(),
                "mask": self.canvas.mask.copy(),
                "history": self.history,
                "texts": self.canvas.get_texts_data()
            }

        # 2. Fetch incoming page's pending script queue BEFORE any canvas signals fire!
        incoming_pending = list(self.pending_page_texts.get(path_real, []))
        self.current_img_path = path_real

        if path_real in self.image_sessions:
            session = self.image_sessions[path_real]
            self.history = session["history"]
            self.canvas.set_image(session["img"])
            self.canvas.mask = session["mask"].copy()
            self.canvas.update_mask_display()
            self.canvas.pending_texts = incoming_pending
            self.canvas.load_texts_data(session.get("texts", []))
        else:
            img_data = np.fromfile(path_real, dtype=np.uint8)
            img = cv2.imdecode(img_data, cv2.IMREAD_UNCHANGED)

            if img is not None:
                if len(img.shape) == 2: img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
                elif len(img.shape) == 3 and img.shape[2] == 4: img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
                else: img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                self.history = HistoryManager(Config.MAX_HISTORY)
                self.canvas.set_image(img)
                # Load incoming_pending AFTER clear_texts so clear_texts doesn't wipe it!
                self.canvas.blockSignals(True)
                self.canvas.clear_texts()
                self.canvas.blockSignals(False)
                self.canvas.pending_texts = incoming_pending
                self.refresh_page_text_list()
                
                self.image_sessions[path_real] = {
                    "img": img.copy(),
                    "mask": self.canvas.mask.copy(),
                    "history": self.history,
                    "texts": []
                }
            else:
                QMessageBox.warning(self, tr("main.load_error"), tr("main.the_file_is_corrupted_or_cannot", basename=os.path.basename(path_real)))
                logger.error(f"Failed to decode image: {path_real}")
                
        self._check_lock_state()
        if self.translator_page is not None:
            self.translator_page.refresh_active_page_preview()

    def on_export(self, fmt):
        """Export the active page in the selected image format."""
        if self.canvas.cv_img is None: return
        if self.current_img_path and not self._confirm_unplaced_texts([self.current_img_path]):
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("main.export_2"), "", f"{fmt.upper()} (*.{fmt})")
        if path:
            composited = self.canvas.get_composited_image()
            if len(composited.shape) == 3 and composited.shape[2] == 4:
                img_out = cv2.cvtColor(composited, cv2.COLOR_RGBA2BGRA)
                if fmt.lower() in ["jpg", "jpeg"]:
                    img_out = cv2.cvtColor(img_out, cv2.COLOR_BGRA2BGR)
            else:
                img_out = cv2.cvtColor(composited, cv2.COLOR_RGB2BGR)
                
            ext = os.path.splitext(path)[1]
            if not ext:
                ext = f".{fmt.lower()}"
                path += ext
            is_success, im_buf_arr = cv2.imencode(ext, img_out)
            if is_success:
                im_buf_arr.tofile(path)

    def on_editor_bridge(self, target="photoshop"):
        """Send the current page to the selected external editor."""
        if self.canvas.cv_img is None or not self.current_img_path: return
        if not self._confirm_unplaced_texts([self.current_img_path]):
            return

        img_data = np.fromfile(self.current_img_path, dtype=np.uint8)
        orig = cv2.imdecode(img_data, cv2.IMREAD_UNCHANGED)

        if orig is not None:
            if len(orig.shape) == 3 and orig.shape[2] == 4:
                orig = cv2.cvtColor(orig, cv2.COLOR_BGRA2RGBA)
            else:
                orig = cv2.cvtColor(orig, cv2.COLOR_BGR2RGB)

            composited = self.canvas.get_composited_image()
            self.setCursor(Qt.WaitCursor)
            if target == "photoshop":
                from src.backend.photoshop import PhotoshopBridge

                res = PhotoshopBridge.send_to_ps(orig, composited)
            elif target == "photopea":
                from src.backend.photopea import PhotopeaBridge

                res = PhotopeaBridge.send_to_photopea(orig, composited, self.current_img_path)
            self.setCursor(Qt.ArrowCursor)

            if res != "Success":
                logger.error(f"[X] UI Blocked Editor Bridge Transfer: {res}")
                QMessageBox.warning(self, tr("main.editor_error"), tr("main.could_not_send_to_capitalize_res", capitalize=target.capitalize(), res=res))

    def update_telemetry(self):
        """Refresh system usage and memory telemetry in the navigation bar."""
        ram, gpu = self.monitor.get_stats()
        self.hw_mon.lbl.setText(tr("main.choice_ram_ram_mb", choice='GPU' if gpu else 'CPU', ram=ram))
        self.hw_mon.bar.setValue(min(ram // 40, 100))

    def on_language_selected(self, language_code, selected_name):
        """Save a language preference and explain that it applies after restart."""
        saved_language = i18n.get_saved_language() or "auto"
        if saved_language == language_code:
            return

        if not i18n.save_language(language_code):
            QMessageBox.warning(
                self,
                tr("main.language_setting_error"),
                tr("main.language_save_failed"),
            )
            return

        active_language = dict(i18n.available_languages()).get(
            i18n.current_language(), i18n.current_language().upper()
        )
        QMessageBox.information(
            self,
            tr("main.restart_required"),
            tr(
                "main.language_restart_message",
                selected=selected_name,
                active=active_language,
            ),
        )
