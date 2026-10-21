import os
import json
import cv2
import numpy as np
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame, QSplitter, QFileDialog,
                             QMenu, QMessageBox, QGraphicsView, QProgressBar, QInputDialog,
                             QDialog, QComboBox, QDialogButtonBox, QFormLayout, QCheckBox,
                             QSpinBox, QColorDialog, QListWidget, QListWidgetItem,
                             QStackedWidget, QLineEdit)
from PySide6.QtGui import QShortcut, QKeySequence, QImage, QPainterPath, QColor, QFontDatabase, QFont
from PySide6.QtCore import Qt, QTimer, QThread
from enum import Enum, auto
from src.frontend.widgets import (FileListWidget, ToolGroup, LabeledSlider, 
                                HardwareMonitor, CategorySelector, ColorSwatchButton)
from src.frontend.canvas import MangaCanvas, MangaTextItem
from src.frontend.help_system import HelpSystem
from src.utils.system_info import SystemMonitor
from src.utils.history import HistoryManager
from src.utils.config import Config
from src.utils.paths import Paths
from src.utils.logger import logger
from src.backend.photoshop import PhotoshopBridge
from src.backend.photopea import PhotopeaBridge
from src.backend.batch_engine import BatchEngine
from src.backend.workers import AIWorker, get_pool, _run_flush_process
from src.backend.stitcher import StitcherPanel
from src.backend.translator import TranslatorPanel

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
#    STUDIO MAIN CONTROLLER       #
#/////////////////////////////////#

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{Config.APP_NAME} v{Config.VERSION}")
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

        # Font Filter, Favorites & Alias Database
        self.font_prefs_path = os.path.join(Paths.BUNDLE_DIR, "font_presets.json")
        self.favorite_fonts = set()
        self.font_aliases = {}
        self.all_system_fonts = sorted(QFontDatabase.families())
        self.load_font_prefs()
        
        self.current_img_path = None
        self.batch_scan_type = "ocr"
        self.image_sessions = {}
        self.pending_page_texts = {}  # Lazy queue for .txt dialogues before page is opened
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
        logger.info("--- STUDIO INTERFACE READY ---")

    # --- FONT PREFERENCES PERSISTENCE ---
    def load_font_prefs(self):
        if os.path.exists(self.font_prefs_path):
            try:
                with open(self.font_prefs_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.favorite_fonts = set(data.get("favorites", []))
                    self.font_aliases = dict(data.get("aliases", {}))
            except Exception as e:
                logger.error(f"Failed to load font presets: {e}")

    def save_font_prefs(self):
        try:
            with open(self.font_prefs_path, "w", encoding="utf-8") as f:
                json.dump({
                    "favorites": sorted(list(self.favorite_fonts)),
                    "aliases": self.font_aliases
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save font presets: {e}")

    def init_ui(self):
        self.central = QWidget()
        self.setCentralWidget(self.central)
        main_lay = QVBoxLayout(self.central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        #/////////////////////////////////#
        #            NAVIGATION           #
        #/////////////////////////////////#
        self.nav = QFrame()
        self.nav.setObjectName("NavBar")
        self.nav.setFixedHeight(60)
        nav_lay = QHBoxLayout(self.nav)
        
        title = QLabel(f"{Config.APP_NAME.upper()} {Config.VERSION}")
        title.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold; font-size: 18px;")
        
        self.hw_mon = HardwareMonitor()
        
        btn_help = QPushButton("?")
        btn_help.setFixedSize(30, 30)
        btn_help.clicked.connect(lambda: HelpSystem.show_guide(self))
        
        btn_open = QPushButton("IMPORT FOLDER")
        btn_open.clicked.connect(self.on_open_folder)
        
        self.btn_editor = QPushButton("SEND TO EDITOR ▼")
        ed_menu = QMenu(self)
        
        ps_action = ed_menu.addAction("Adobe Photoshop")
        ps_action.triggered.connect(lambda: self.on_editor_bridge("photoshop"))
        if os.name != 'nt':
            ps_action.setEnabled(False)
            ps_action.setText("Adobe Photoshop")
            
        ed_menu.addAction("Photopea (Web)").triggered.connect(lambda: self.on_editor_bridge("photopea"))
        self.btn_editor.setMenu(ed_menu)
        
        self.btn_export = QPushButton("EXPORT ▼")
        self.btn_export.setObjectName("PrimaryBtn")
        exp_menu = QMenu(self)
        exp_menu.addAction("Export as JPG").triggered.connect(lambda: self.on_export("jpg"))
        exp_menu.addAction("Export as PNG").triggered.connect(lambda: self.on_export("png"))
        self.btn_export.setMenu(exp_menu)

        nav_lay.addWidget(title)
        nav_lay.addStretch()
        nav_lay.addWidget(self.hw_mon)
        nav_lay.addSpacing(10)
        nav_lay.addWidget(btn_help)
        nav_lay.addWidget(btn_open)
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
        lbl_assets = QLabel("PROJECT ASSETS")
        lbl_assets.setStyleSheet("color: #888888; font-weight: bold;")
        header_lay.addWidget(self.chk_all)
        header_lay.addWidget(lbl_assets)
        header_lay.addStretch()

        self.file_list = FileListWidget()
        self.file_list.itemClicked.connect(self.on_file_clicked)
        self.btn_batch = QPushButton("RUN BATCH PROCESS")
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
        self.canvas.text_selected.connect(self.sync_text_ui_from_item)
        self.canvas.texts_list_changed.connect(self.refresh_page_text_list)
        
        #/////////////////////////////////#
        #      RIGHT PANEL (CATEGORIZED)  #
        #/////////////////////////////////#
        self.rp = QFrame()
        self.rp.setObjectName("SidePanel")
        rp_lay = QVBoxLayout(self.rp)
        rp_lay.setSpacing(6)
        
        self.cat_lbl = QLabel("CATEGORY: CLEANER")
        self.cat_lbl.setStyleSheet(f"color: {Config.COLOR_TEXT}; font-weight: bold; font-size: 11px;")
        rp_lay.addWidget(self.cat_lbl)

        self.mode_lbl = QLabel("MODE: PAINTING")
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
            "Cleaner & Mask Tools",
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
        self.tools.buttons["MANUAL"].setToolTip("Manual Cleaner Brush [D] - Paint directly on page (Ctrl+Z to Undo)")
        self.tools.buttons["MANUAL"].clicked.connect(lambda: self.set_tool("PAINT"))

        # Contextual Manual Cleaner Sub-Bar (Only visible when MANUAL / PICKER is active!)
        self.manual_col_frame = QFrame()
        mc_lay = QHBoxLayout(self.manual_col_frame)
        mc_lay.setContentsMargins(5, 2, 5, 2)
        mc_lay.setSpacing(6)

        self.btn_picker = QPushButton("PICKER [I]")
        self.btn_picker.setCheckable(True)
        self.btn_picker.setToolTip("Eyedropper Color Picker [I] - Click on page to sample color")
        self.btn_picker.clicked.connect(lambda: self.set_tool("PICKER"))

        self.swatch_manual_clean = ColorSwatchButton(
            QColor(255, 255, 255), width=42, height=24, tooltip="Click to choose Manual Cleaner Color"
        )
        self.swatch_manual_clean.clicked.connect(self.choose_manual_clean_color)

        btn_white_reset = QPushButton("White")
        btn_white_reset.setFixedWidth(50)
        btn_white_reset.setToolTip("Reset Manual Paint Color to Pure White")
        btn_white_reset.clicked.connect(lambda: self.on_clean_color_picked(QColor(255, 255, 255)))

        mc_lay.addWidget(self.btn_picker, 1)
        mc_lay.addWidget(self.swatch_manual_clean)
        mc_lay.addWidget(btn_white_reset)
        self.manual_col_frame.setVisible(False)

        self.b_slider = LabeledSlider("BRUSH SIZE", 40, 1, 300, self.canvas.set_brush_size)
        self.o_slider = LabeledSlider("MASK OPACITY", 60, 0, 100, self.canvas.set_mask_opacity, suffix="%")
        self.t_slider = LabeledSlider("MAX TILE SIZE", 2048, 512, 4096, is_tile=True)
        
        self.canvas.brush_size_changed.connect(self.b_slider.slider.setValue)
        
        btn_scan = QPushButton("OCR SCAN [O]")
        btn_scan.setObjectName("ActionBtn")
        btn_scan.clicked.connect(self.on_ocr_scan)

        btn_trans = QPushButton("TRANSPARENCY SCAN [T]")
        btn_trans.setObjectName("ActionBtn")
        btn_trans.clicked.connect(self.on_transparency_scan)
        
        self.btn_clean = QPushButton("EXECUTE CLEAN [C]")
        self.btn_clean.setObjectName("PrimaryBtn")
        self.btn_clean.setFixedHeight(45)
        self.btn_clean.clicked.connect(self.on_lama_clean)
        
        self.queue_lbl = QLabel("Processing / Queued: 0")
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

        # ==========================================
        # PAGE 1: TYPESETTER CATEGORY WORKSPACE
        # ==========================================
        self.typesetter_page = QWidget()
        tp_lay = QVBoxLayout(self.typesetter_page)
        tp_lay.setContentsMargins(4, 4, 4, 4)
        tp_lay.setSpacing(6)

        self.type_tools = ToolGroup("Typesetter Tools", ["MOVE", "TEXT"])
        self.type_tools.buttons["MOVE"].clicked.connect(lambda: self.set_tool("NONE"))
        self.type_tools.buttons["TEXT"].clicked.connect(lambda: self.set_tool("TEXT"))
        tp_lay.addWidget(self.type_tools)

        # --- FONT FILTER, FAVORITES & ALIASES ---
        tp_title = QLabel("FONT MANAGER & FILTER")
        tp_title.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold;")
        tp_lay.addWidget(tp_title)

        row_filter = QHBoxLayout()
        self.font_search = QLineEdit()
        self.font_search.setPlaceholderText("Search font or alias...")
        self.font_search.setStyleSheet(f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 3px; font-size: 11px;")
        self.font_search.textChanged.connect(self.populate_font_combo)

        self.chk_fav_only = QCheckBox("★ Only")
        self.chk_fav_only.setToolTip("Show Only Favorite Fonts")
        self.chk_fav_only.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-size: 10px; font-weight: bold;")
        self.chk_fav_only.toggled.connect(self.populate_font_combo)

        row_filter.addWidget(self.font_search, 1)
        row_filter.addWidget(self.chk_fav_only)
        tp_lay.addLayout(row_filter)

        row_font_sel = QHBoxLayout()
        self.font_combo = QComboBox()
        self.font_combo.setStyleSheet(f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 4px; font-size: 11px;")
        self.font_combo.currentIndexChanged.connect(self.on_font_combo_selected)

        self.btn_fav_font = QPushButton("☆")
        self.btn_fav_font.setFixedWidth(28)
        self.btn_fav_font.setToolTip("Toggle Favorite for Current Font")
        self.btn_fav_font.clicked.connect(self.toggle_current_font_favorite)

        self.btn_alias_font = QPushButton("✎")
        self.btn_alias_font.setFixedWidth(28)
        self.btn_alias_font.setToolTip("Set Custom Alias/Use-Case Name for Current Font")
        self.btn_alias_font.clicked.connect(self.rename_current_font_alias)

        row_font_sel.addWidget(self.font_combo, 1)
        row_font_sel.addWidget(self.btn_fav_font)
        row_font_sel.addWidget(self.btn_alias_font)
        tp_lay.addLayout(row_font_sel)

        # Size, Bold, Italic, Align
        row_style = QHBoxLayout()
        lbl_sz = QLabel("Size:")
        lbl_sz.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 300)
        self.font_size_spin.setValue(32)
        self.font_size_spin.valueChanged.connect(self.on_text_style_ui_changed)

        self.btn_bold = QPushButton("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setFixedWidth(28)
        self.btn_bold.clicked.connect(self.on_text_style_ui_changed)

        self.btn_italic = QPushButton("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setFixedWidth(28)
        self.btn_italic.clicked.connect(self.on_text_style_ui_changed)

        self.btn_center = QPushButton("≡")
        self.btn_center.setToolTip("Center Align Text")
        self.btn_center.setCheckable(True)
        self.btn_center.setChecked(True)
        self.btn_center.setFixedWidth(28)
        self.btn_center.clicked.connect(self.on_text_style_ui_changed)

        row_style.addWidget(lbl_sz)
        row_style.addWidget(self.font_size_spin, 1)
        row_style.addWidget(self.btn_bold)
        row_style.addWidget(self.btn_italic)
        row_style.addWidget(self.btn_center)
        tp_lay.addLayout(row_style)

        # Rotation & Fit Box Row
        row_rot = QHBoxLayout()
        lbl_rot = QLabel("Angle:")
        lbl_rot.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.rot_spin = QSpinBox()
        self.rot_spin.setRange(-180, 180)
        self.rot_spin.setSuffix("°")
        self.rot_spin.setValue(0)
        self.rot_spin.valueChanged.connect(self.on_text_rotation_ui_changed)

        self.btn_reset_rot = QPushButton("0°")
        self.btn_reset_rot.setToolTip("Reset Rotation to 0°")
        self.btn_reset_rot.setFixedWidth(34)
        self.btn_reset_rot.clicked.connect(lambda: self.rot_spin.setValue(0))

        self.btn_auto_width = QPushButton("Fit Box")
        self.btn_auto_width.setToolTip("Reset Box Width to Auto-Fit")
        self.btn_auto_width.setFixedWidth(64)
        self.btn_auto_width.clicked.connect(self.on_reset_box_width)

        row_rot.addWidget(lbl_rot)
        row_rot.addWidget(self.rot_spin, 1)
        row_rot.addWidget(self.btn_reset_rot)
        row_rot.addWidget(self.btn_auto_width)
        tp_lay.addLayout(row_rot)

        # --- PHOTOSHOP-STYLE COLOR SWATCHES & SINGLE RENDER MODE BUTTON ---
        lbl_col = QLabel("COLOR SWATCHES & STROKE MODE")
        lbl_col.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold; margin-top: 4px;")
        tp_lay.addWidget(lbl_col)

        row_colors = QHBoxLayout()
        lbl_fill_tag = QLabel("Fill:")
        lbl_fill_tag.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.swatch_text_color = ColorSwatchButton(QColor(0, 0, 0), width=42, height=24, tooltip="Click to pick Fill Color")
        self.swatch_text_color.clicked.connect(self.choose_text_color)

        self.btn_swap_colors = QPushButton("⇄")
        self.btn_swap_colors.setToolTip("Swap Fill and Stroke Colors")
        self.btn_swap_colors.setFixedWidth(30)
        self.btn_swap_colors.clicked.connect(self.swap_text_and_stroke_colors)

        lbl_str_tag = QLabel("Stroke:")
        lbl_str_tag.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.swatch_stroke_color = ColorSwatchButton(QColor(255, 255, 255), width=42, height=24, tooltip="Click to pick Outer Stroke Color")
        self.swatch_stroke_color.clicked.connect(self.choose_stroke_color)

        row_colors.addWidget(lbl_fill_tag)
        row_colors.addWidget(self.swatch_text_color)
        row_colors.addStretch()
        row_colors.addWidget(self.btn_swap_colors)
        row_colors.addStretch()
        row_colors.addWidget(lbl_str_tag)
        row_colors.addWidget(self.swatch_stroke_color)
        tp_lay.addLayout(row_colors)

        # Single Toggle Button for Normal vs Stroke Mode
        self.btn_stroke_mode = QPushButton("Mode: Normal (No Stroke)")
        self.btn_stroke_mode.setCheckable(True)
        self.btn_stroke_mode.setToolTip("Toggle between Normal Text and Outer Stroke Mode")
        self.btn_stroke_mode.toggled.connect(self.on_stroke_mode_toggled)
        tp_lay.addWidget(self.btn_stroke_mode)

        self.stroke_settings_frame = QFrame()
        row_stroke = QHBoxLayout(self.stroke_settings_frame)
        row_stroke.setContentsMargins(0, 0, 0, 0)
        lbl_st = QLabel("Size:")
        lbl_st.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.stroke_spin = QSpinBox()
        self.stroke_spin.setRange(1, 30)
        self.stroke_spin.setSuffix(" px")
        self.stroke_spin.setValue(3)
        self.stroke_spin.valueChanged.connect(self.on_text_style_ui_changed)

        lbl_op = QLabel("Opacity:")
        lbl_op.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.stroke_op_spin = QSpinBox()
        self.stroke_op_spin.setRange(10, 100)
        self.stroke_op_spin.setSuffix("%")
        self.stroke_op_spin.setValue(100)
        self.stroke_op_spin.valueChanged.connect(self.on_text_style_ui_changed)

        row_stroke.addWidget(lbl_st)
        row_stroke.addWidget(self.stroke_spin, 1)
        row_stroke.addWidget(lbl_op)
        row_stroke.addWidget(self.stroke_op_spin, 1)
        tp_lay.addWidget(self.stroke_settings_frame)
        self.stroke_settings_frame.setVisible(False)

        # Page Text Detector List
        self.lbl_text_layers = QLabel("PAGE TEXT LAYERS (0 Placed | 0 Queued)")
        self.lbl_text_layers.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold; margin-top: 4px;")
        tp_lay.addWidget(self.lbl_text_layers)

        self.text_layer_list = QListWidget()
        self.text_layer_list.setMinimumHeight(110)
        self.text_layer_list.setStyleSheet(f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; font-size: 11px;")
        self.text_layer_list.itemClicked.connect(self.on_text_layer_item_clicked)
        tp_lay.addWidget(self.text_layer_list, 1)

        row_del_btns = QHBoxLayout()
        self.btn_del_text = QPushButton("DELETE SELECTED")
        self.btn_del_text.clicked.connect(self.canvas.delete_selected_texts)
        self.btn_clear_texts = QPushButton("CLEAR ALL")
        self.btn_clear_texts.clicked.connect(self.on_clear_all_page_texts)
        row_del_btns.addWidget(self.btn_del_text, 1)
        row_del_btns.addWidget(self.btn_clear_texts, 1)
        tp_lay.addLayout(row_del_btns)

        # ==========================================
        # PAGE 2: STITCHER CATEGORY WORKSPACE
        # ==========================================
        self.stitcher_page = StitcherPanel(self)

        # ==========================================
        # PAGE 3: TRANSLATOR CATEGORY WORKSPACE
        # ==========================================
        self.translator_page = TranslatorPanel(self)

        # Add all 4 Category Pages to Stack
        self.category_stack.addWidget(self.cleaner_page)     # Index 0: CLEANER
        self.category_stack.addWidget(self.typesetter_page)  # Index 1: TYPESETTER
        self.category_stack.addWidget(self.stitcher_page)    # Index 2: STITCHER
        self.category_stack.addWidget(self.translator_page)  # Index 3: TRANSLATOR

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

        self.populate_font_combo()
        self.update_color_swatches()
        self.set_category("CLEANER")

    #/////////////////////////////////#
    #     FONT FILTER & ALIAS LOGIC   #
    #/////////////////////////////////#

    def get_selected_font_family(self) -> str:
        fam = self.font_combo.currentData(Qt.UserRole)
        return fam if fam else "Arial"

    def populate_font_combo(self):
        current_fam = self.get_selected_font_family()
        if not current_fam or current_fam == "Arial":
            current_fam = self.canvas.default_font_family

        query = self.font_search.text().strip().lower()
        fav_only = self.chk_fav_only.isChecked()

        self.font_combo.blockSignals(True)
        self.font_combo.clear()

        sorted_fonts = sorted(
            self.all_system_fonts,
            key=lambda f: (0 if f in self.favorite_fonts else 1, self.font_aliases.get(f, f).lower())
        )

        selected_idx = 0
        for fam in sorted_fonts:
            is_fav = fam in self.favorite_fonts
            if fav_only and not is_fav:
                continue

            alias = self.font_aliases.get(fam, "")
            searchable = f"{fam.lower()} {alias.lower()}"
            if query and query not in searchable:
                continue

            star_prefix = "★ " if is_fav else ""
            display_name = f"{star_prefix}{alias} [{fam}]" if alias else f"{star_prefix}{fam}"

            self.font_combo.addItem(display_name, fam)
            idx = self.font_combo.count() - 1
            self.font_combo.setItemData(idx, QFont(fam, 10), Qt.FontRole)
            if fam == current_fam:
                selected_idx = idx

        if self.font_combo.count() > 0:
            self.font_combo.setCurrentIndex(selected_idx)
        self.font_combo.blockSignals(False)
        self.update_font_fav_button_visual()

    def update_font_fav_button_visual(self):
        fam = self.get_selected_font_family()
        is_fav = fam in self.favorite_fonts
        self.btn_fav_font.setText("★" if is_fav else "☆")
        self.btn_fav_font.setStyleSheet(
            f"color: {Config.COLOR_ACCENT}; font-weight: bold;" if is_fav else ""
        )

    def on_font_combo_selected(self):
        self.update_font_fav_button_visual()
        self.on_text_style_ui_changed()

    def toggle_current_font_favorite(self):
        fam = self.get_selected_font_family()
        if not fam:
            return
        if fam in self.favorite_fonts:
            self.favorite_fonts.remove(fam)
        else:
            self.favorite_fonts.add(fam)
        self.save_font_prefs()
        self.populate_font_combo()

    def rename_current_font_alias(self):
        fam = self.get_selected_font_family()
        if not fam:
            return
        current_alias = self.font_aliases.get(fam, "")
        new_alias, ok = QInputDialog.getText(
            self,
            "Rename / Alias Font",
            f"Enter custom alias for '{fam}'\n(Leave empty to restore default name):",
            QLineEdit.Normal,
            current_alias
        )
        if ok:
            clean_alias = new_alias.strip()
            if clean_alias:
                self.font_aliases[fam] = clean_alias
            elif fam in self.font_aliases:
                del self.font_aliases[fam]
            self.save_font_prefs()
            self.populate_font_combo()

    #/////////////////////////////////#
    #     CATEGORY & TOOL SWITCHING   #
    #/////////////////////////////////#

    def set_category(self, category: str):
        self.current_category = category
        self.cat_lbl.setText(f"CATEGORY: {category}")

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
            self.category_stack.setCurrentIndex(1)
            self.set_tool("TEXT", switch_category=False)

        elif category == "STITCHER":
            self.category_stack.setCurrentIndex(2)
            self.set_tool("NONE", switch_category=False)

        elif category == "TRANSLATOR":
            self.category_stack.setCurrentIndex(3)
            self.set_tool("TEXT", switch_category=False)

    def set_tool(self, tool, switch_category=True):
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

        for grp in (self.tools, self.type_tools):
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
                self.type_tools.buttons["MOVE"].setChecked(True)
            self.mode_lbl.setText("MODE: MOVING")
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
                self.type_tools.buttons["TEXT"].setChecked(True)
            elif tool in ("PAINT", "PICKER"):
                self.tools.buttons["MANUAL"].setChecked(True)
            elif tool in self.tools.buttons:
                self.tools.buttons[tool].setChecked(True)
            
            if tool == "ERASER":
                self.mode_lbl.setText("MODE: ERASING MASK")
                self.mode_lbl.setStyleSheet("color: #00d4ff; font-weight: bold;")
            elif tool == "BUCKET":
                self.mode_lbl.setText("MODE: FILLING MASK")
                self.mode_lbl.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold;")
            elif tool == "PAINT":
                self.mode_lbl.setText("MODE: MANUAL CLEAN BRUSH")
                self.mode_lbl.setStyleSheet("color: #00ff8c; font-weight: bold;")
            elif tool == "PICKER":
                self.mode_lbl.setText("MODE: COLOR PICKER")
                self.mode_lbl.setStyleSheet("color: #00ff8c; font-weight: bold;")
            elif tool == "TEXT":
                self.mode_lbl.setText("MODE: TYPESETTING")
                self.mode_lbl.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold;")
            else:
                self.mode_lbl.setText("MODE: PAINTING MASK")
                self.mode_lbl.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold;")

    # --- MANUAL CLEANER HANDLERS ---
    def on_manual_image_patch(self, x, y, old_patch):
        self.history.push_image_action(x, y, old_patch)
        self.mark_current_modified()

    def on_clean_color_picked(self, color: QColor):
        self.canvas.manual_clean_color = QColor(color)
        self.swatch_manual_clean.set_color(color)
        self.canvas.update_cursor_visuals()
        if self.canvas.current_tool == "PICKER":
            self.set_tool("PAINT", switch_category=False)

    def choose_manual_clean_color(self):
        c = QColorDialog.getColor(self.canvas.manual_clean_color, self, "Select Manual Cleaner Brush Color")
        if c.isValid():
            self.on_clean_color_picked(c)

    # --- TEXT UI HANDLERS ---
    def _run_if_not_typing(self, func):
        if not self.canvas.is_editing_text():
            func()

    def update_color_swatches(self):
        self.swatch_text_color.set_color(self.canvas.default_text_color)
        self.swatch_stroke_color.set_color(self.canvas.default_stroke_color)

    def on_stroke_mode_toggled(self, enabled: bool):
        self.btn_stroke_mode.setText("Mode: Stroke (Outside)" if enabled else "Mode: Normal (No Stroke)")
        self.stroke_settings_frame.setVisible(enabled)
        self.on_text_style_ui_changed()

    def refresh_page_text_list(self):
        self.text_layer_list.blockSignals(True)
        self.text_layer_list.clear()
        placed_count = len(self.canvas.text_items)
        pending_count = len(self.canvas.pending_texts)
        self.lbl_text_layers.setText(f"PAGE TEXT LAYERS ({placed_count} Placed | {pending_count} Queued)")

        # 1. Show Placed Canvas Text Items first ([ ✓ ])
        for idx, item in enumerate(self.canvas.text_items, start=1):
            preview = item.toPlainText().replace("\n", " ").strip() or "<Empty>"
            if len(preview) > 22:
                preview = preview[:22] + "..."
            list_item = QListWidgetItem(f"[ ✓ ] {idx}. {preview}")
            list_item.setData(Qt.UserRole, ("PLACED", item))
            self.text_layer_list.addItem(list_item)
            if item.isSelected():
                list_item.setSelected(True)

        # 2. Show Pending Queued Script Lines below ([ + ] click to spawn with active font!)
        for p_idx, text_str in enumerate(self.canvas.pending_texts):
            preview = text_str.replace("\n", " ").strip()
            if len(preview) > 22:
                preview = preview[:22] + "..."
            list_item = QListWidgetItem(f"[ + ] {preview}")
            list_item.setForeground(QColor(Config.COLOR_ACCENT))
            list_item.setToolTip(f"Click to place on canvas with current font:\n{text_str}")
            list_item.setData(Qt.UserRole, ("PENDING", p_idx))
            self.text_layer_list.addItem(list_item)

        self.text_layer_list.blockSignals(False)

    def on_text_layer_item_clicked(self, list_item):
        data = list_item.data(Qt.UserRole)
        if not isinstance(data, tuple):
            return

        kind, payload = data
        if kind == "PLACED":
            target_item = payload
            if isinstance(target_item, MangaTextItem) and target_item in self.canvas.text_items:
                if self.canvas.current_tool == "NONE":
                    self.set_tool("TEXT", switch_category=False)
                self.canvas.scene.clearSelection()
                target_item.setSelected(True)
                self.canvas.centerOn(target_item)
                self.sync_text_ui_from_item(target_item)

        elif kind == "PENDING":
            if self.canvas.cv_img is None or self.canvas.is_locked:
                return
            p_idx = payload
            if 0 <= p_idx < len(self.canvas.pending_texts):
                text_str = self.canvas.pending_texts.pop(p_idx)
                if self.current_img_path:
                    self.pending_page_texts[self.current_img_path] = list(self.canvas.pending_texts)
                if self.canvas.current_tool == "NONE":
                    self.set_tool("TEXT", switch_category=False)
                center_pt = self.canvas.mapToScene(self.canvas.viewport().rect().center())
                self.canvas.add_text_item(center_pt, initial_text=text_str, enter_edit=False)
                self.mark_current_modified()
                self.refresh_page_text_list()

    def on_clear_all_page_texts(self):
        if not self.canvas.text_items and not self.canvas.pending_texts:
            return
        self.canvas.clear_texts()
        if self.current_img_path:
            self.pending_page_texts[self.current_img_path] = []
        self.mark_current_modified()

    def sync_text_ui_from_item(self, item: MangaTextItem):
        self.font_combo.blockSignals(True)
        self.font_size_spin.blockSignals(True)
        self.btn_bold.blockSignals(True)
        self.btn_italic.blockSignals(True)
        self.btn_center.blockSignals(True)
        self.btn_stroke_mode.blockSignals(True)
        self.stroke_spin.blockSignals(True)
        self.stroke_op_spin.blockSignals(True)
        self.rot_spin.blockSignals(True)

        idx = self.font_combo.findData(item.font_family, Qt.UserRole)
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)
        self.update_font_fav_button_visual()

        self.font_size_spin.setValue(int(item.font_size))
        self.btn_bold.setChecked(item.is_bold)
        self.btn_italic.setChecked(item.is_italic)
        self.btn_center.setChecked(item.align_center)
        self.btn_stroke_mode.setChecked(item.stroke_enabled)
        self.btn_stroke_mode.setText("Mode: Stroke (Outside)" if item.stroke_enabled else "Mode: Normal (No Stroke)")
        self.stroke_settings_frame.setVisible(item.stroke_enabled)
        self.stroke_spin.setValue(max(1, int(item.stroke_width)))
        self.stroke_op_spin.setValue(int(item.stroke_opacity))
        self.rot_spin.setValue(int(round(item.rotation())))
        self.canvas.default_text_color = QColor(item.text_color)
        self.canvas.default_stroke_color = QColor(item.stroke_color)
        self.update_color_swatches()

        self.font_combo.blockSignals(False)
        self.font_size_spin.blockSignals(False)
        self.btn_bold.blockSignals(False)
        self.btn_italic.blockSignals(False)
        self.btn_center.blockSignals(False)
        self.btn_stroke_mode.blockSignals(False)
        self.stroke_spin.blockSignals(False)
        self.stroke_op_spin.blockSignals(False)
        self.rot_spin.blockSignals(False)
        self.refresh_page_text_list()

    def on_text_rotation_ui_changed(self, val):
        for it in self.canvas.scene.selectedItems():
            if isinstance(it, MangaTextItem):
                it.set_rotation_angle(float(val))

    def on_reset_box_width(self):
        for it in self.canvas.scene.selectedItems():
            if isinstance(it, MangaTextItem):
                it.reset_box_width()

    def on_text_style_ui_changed(self):
        fam = self.get_selected_font_family()
        sz = self.font_size_spin.value()
        bold = self.btn_bold.isChecked()
        italic = self.btn_italic.isChecked()
        center = self.btn_center.isChecked()
        st_en = self.btn_stroke_mode.isChecked()
        st_w = self.stroke_spin.value()
        st_op = self.stroke_op_spin.value()

        self.canvas.default_font_family = fam
        self.canvas.default_font_size = sz
        self.canvas.default_bold = bold
        self.canvas.default_italic = italic
        self.canvas.default_align_center = center
        self.canvas.default_stroke_enabled = st_en
        self.canvas.default_stroke_width = st_w
        self.canvas.default_stroke_opacity = st_op

        for it in self.canvas.scene.selectedItems():
            if isinstance(it, MangaTextItem):
                it.font_family = fam
                it.font_size = sz
                it.is_bold = bold
                it.is_italic = italic
                it.align_center = center
                it.stroke_enabled = st_en
                it.stroke_width = st_w
                it.stroke_opacity = st_op
                it.update_style()
                self.mark_current_modified()

    def swap_text_and_stroke_colors(self):
        self.canvas.default_text_color, self.canvas.default_stroke_color = (
            QColor(self.canvas.default_stroke_color),
            QColor(self.canvas.default_text_color),
        )
        self.update_color_swatches()
        for it in self.canvas.scene.selectedItems():
            if isinstance(it, MangaTextItem):
                it.text_color = QColor(self.canvas.default_text_color)
                it.stroke_color = QColor(self.canvas.default_stroke_color)
                it.update_style()
                self.mark_current_modified()

    def choose_text_color(self):
        c = QColorDialog.getColor(self.canvas.default_text_color, self, "Select Text Fill Color")
        if c.isValid():
            self.canvas.default_text_color = c
            self.update_color_swatches()
            for it in self.canvas.scene.selectedItems():
                if isinstance(it, MangaTextItem):
                    it.text_color = c
                    it.update_style()
                    self.mark_current_modified()

    def choose_stroke_color(self):
        c = QColorDialog.getColor(self.canvas.default_stroke_color, self, "Select Outer Stroke Color")
        if c.isValid():
            self.canvas.default_stroke_color = c
            self.update_color_swatches()
            for it in self.canvas.scene.selectedItems():
                if isinstance(it, MangaTextItem):
                    it.stroke_color = c
                    it.update_style()
                    self.mark_current_modified()

    def setup_shortcuts(self):
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
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.file_list.count()):
            self.file_list.item(i).setCheckState(state)

    #/////////////////////////////////#
    #       HISTORY OPERATIONS        #
    #/////////////////////////////////#

    def on_smart_ctrl_z(self):
        if self.canvas.current_tool in ("PAINT", "PICKER"):
            self.on_undo_image()
        else:
            self.on_undo_mask()

    def on_smart_ctrl_shift_z(self):
        if self.canvas.current_tool in ("PAINT", "PICKER"):
            self.on_redo_image()
        else:
            self.on_redo_mask()

    def on_undo_image(self):
        if self.canvas.is_locked: return
        res = self.history.pop_image_undo(self.canvas.cv_img)
        if res:
            x, y, p = res
            self.mark_current_modified()
            self.canvas.cv_img[y:y+p.shape[0], x:x+p.shape[1]] = p
            self.canvas.refresh_image_pixmap()

    def on_redo_image(self):
        if self.canvas.is_locked: return
        res = self.history.pop_image_redo(self.canvas.cv_img)
        if res:
            x, y, p = res
            self.mark_current_modified()
            self.canvas.cv_img[y:y+p.shape[0], x:x+p.shape[1]] = p
            self.canvas.refresh_image_pixmap()

    def on_undo_mask(self):
        if self.canvas.is_locked: return
        res = self.history.pop_mask_undo(self.canvas.mask)
        if res:
            self.mark_current_modified()
            self.canvas.mask = res
            self.canvas.update_mask_display()

    def on_redo_mask(self):
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
        pending = self.total_lama_tasks - self.completed_lama_tasks
        self.queue_lbl.setText(f"Processing / Queued: {pending}")

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
        if self.worker.task != "clean" or self.total_lama_tasks == 0: return
        base_progress = (self.completed_lama_tasks / self.total_lama_tasks) * 100
        task_fraction = (val / 100.0) * (100 / self.total_lama_tasks)
        self.progress_bar.setValue(int(base_progress + task_fraction))

    def enqueue_task(self, task, path, *args):
        self.task_queue.append({
            "task": task,
            "path": path,
            "args": args
        })
        self._update_queue_ui()
        self._process_queue()

    def _process_queue(self):
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
        self.setCursor(Qt.ArrowCursor)
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
        self._update_queue_ui()

    def on_task_error(self, message):
        source_path = getattr(self.worker, 'source_path', None)
        if source_path:
            self.page_states[source_path] = PageState.ERROR
            self.file_list.update_item_state(source_path, "error")

        self.stop_thread()
        self.is_batching = False
        self.task_queue.clear()
        self.total_lama_tasks = 0
        self.completed_lama_tasks = 0
        self._update_queue_ui()
        QMessageBox.critical(self, "Hardware Error", message)

    def _get_final_img_for_path(self, path):
        is_active = (path == self.current_img_path)
        if is_active:
            return self.canvas.get_composited_image()
        session = self.image_sessions.get(path, {})
        return MangaCanvas.render_texts_onto_cv_img(session.get("img"), session.get("texts", []))

    def on_task_finished(self, result, patches):
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
                is_last = self.batch_engine.save_current(final_img)
                if is_last: self.finalize_batch()
                else: self.step_batch()
            elif task in ["ocr", "transparency"]:
                mask_q = self.canvas.mask if is_active else self.image_sessions[source_path]["mask"]
                img_cv = self.canvas.cv_img if is_active else self.image_sessions[source_path]["img"]

                ptr = mask_q.bits()
                mask_np = np.frombuffer(ptr, np.uint8).reshape((mask_q.height(), mask_q.width(), 4))
                mask_gray = mask_np[:, :, 3].copy()
                t_size = self.t_slider.slider.value() * 512
                self.enqueue_task("clean", source_path, img_cv.copy(), mask_gray, t_size)

        self._process_queue()

    def on_ocr_scan(self):
        if self.canvas.cv_img is None or self.canvas.is_locked: return
        self.mark_current_modified()
        self.enqueue_task("ocr", self.current_img_path, self.canvas.cv_img.copy())

    def on_transparency_scan(self):
        if self.canvas.cv_img is None or not self.current_img_path or self.canvas.is_locked: return
        self.mark_current_modified()
        self.enqueue_task("transparency", self.current_img_path, self.canvas.cv_img.copy())

    def on_lama_clean(self):
        if self.canvas.cv_img is None or self.canvas.is_locked: return
        ptr = self.canvas.mask.bits()
        mask_np = np.frombuffer(ptr, np.uint8).reshape((self.canvas.mask.height(), self.canvas.mask.width(), 4))
        mask_gray = mask_np[:, :, 3].copy()

        if not np.any(mask_gray):
            if self.is_batching:
                is_last = self.batch_engine.save_current(self.canvas.get_composited_image())
                if is_last: self.finalize_batch()
                else: self.step_batch()
            else:
                QMessageBox.information(self, "Nothing Selected", "No mask area detected!")
            return

        self.total_lama_tasks += 1
        t_size = self.t_slider.slider.value() * 512
        self.mark_current_modified()
        self.enqueue_task("clean", self.current_img_path, self.canvas.cv_img.copy(), mask_gray, t_size)

    #/////////////////////////////////#
    #    BATCH & PHOTOSHOP BRIDGE     #
    #/////////////////////////////////#

    def on_start_batch(self):
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

        self.batch_engine.initialize_batch(paths, fmt)
        self.is_batching = True
        self.total_lama_tasks += len(paths)
        self.step_batch()
        self._check_lock_state()

    def step_batch(self):
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
                        "texts": [],
                        "pending_texts": list(self.pending_page_texts.get(path, []))
                    }
                    self.image_sessions[path]["mask"].fill(Qt.transparent)

            is_active = (path == self.current_img_path)

            if self.batch_scan_type == "none":
                img_cv = self._get_final_img_for_path(path)
                self.total_lama_tasks -= 1
                
                self.page_states[path] = PageState.READY
                self.file_list.update_item_state(path, "ready")
                self._update_queue_ui()
                
                is_last = self.batch_engine.save_current(img_cv)
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
                    
                    is_last = self.batch_engine.save_current(self._get_final_img_for_path(path))
                    if is_last: self.finalize_batch()
                    else: QTimer.singleShot(0, self.step_batch)
                    return

                t_size = self.t_slider.slider.value() * 512
                self.enqueue_task("clean", path, img_cv.copy(), mask_gray, t_size)
            else:
                img_cv = self.canvas.cv_img if is_active else self.image_sessions[path]["img"]
                self.enqueue_task(self.batch_scan_type, path, img_cv.copy())

    def finalize_batch(self):
        self.is_batching = False
        self._check_lock_state()
        
        self.setCursor(Qt.WaitCursor)
        if self.batch_engine.export_format == "photoshop":
            PhotoshopBridge.open_batch_in_ps(self.batch_engine.files, self.batch_engine.output_dir)
        elif self.batch_engine.export_format == "photopea":
            PhotopeaBridge.open_batch_in_photopea(self.batch_engine.files, self.batch_engine.output_dir)
        self.setCursor(Qt.ArrowCursor)
            
        if self.batch_engine.export_format == "none":
            QMessageBox.information(self, "Batch Complete", "All selected pages processed and updated in the studio memory.")
        else:
            QMessageBox.information(self, "Batch Complete", f"Saved to: {self.batch_engine.output_dir}")

    #/////////////////////////////////#
    #         FILE OPERATIONS         #
    #/////////////////////////////////#

    def on_open_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Select Folder")
        if p:
            self.image_sessions.clear()
            self.pending_page_texts.clear()
            self.page_states.clear()
            self.file_list.clear()
            self.canvas.clear_texts()
            self.current_img_path = None
            for f in sorted(os.listdir(p)):
                if f.lower().endswith(('.jpg','.jpeg','.png','.webp')):
                    full_path = os.path.join(p, f)
                    self.page_states[full_path] = PageState.UNMODIFIED
                    self.file_list.add_file(full_path)
            if hasattr(self, "stitcher_page"):
                self.stitcher_page.clear_blocks()
            if hasattr(self, "translator_page"):
                self.translator_page.refresh_active_page_preview()

    def mark_current_modified(self):
        if self.current_img_path:
            if self.page_states.get(self.current_img_path) != PageState.MODIFIED:
                self.page_states[self.current_img_path] = PageState.MODIFIED
                self.file_list.update_item_state(self.current_img_path, "modified")

    def on_file_clicked(self, it):
        path_real = it.data(Qt.UserRole)
        if path_real == self.current_img_path: return 

        if self.current_img_path and self.canvas.cv_img is not None:
            self.pending_page_texts[self.current_img_path] = list(self.canvas.pending_texts)
            self.image_sessions[self.current_img_path] = {
                "img": self.canvas.cv_img.copy(),
                "mask": self.canvas.mask.copy(),
                "history": self.history,
                "texts": self.canvas.get_texts_data(),
                "pending_texts": list(self.canvas.pending_texts)
            }

        self.current_img_path = path_real

        if path_real in self.image_sessions:
            session = self.image_sessions[path_real]
            self.history = session["history"]
            self.canvas.set_image(session["img"])
            self.canvas.mask = session["mask"].copy()
            self.canvas.update_mask_display()
            self.canvas.load_texts_data(session.get("texts", []))
            self.canvas.pending_texts = list(session.get("pending_texts", self.pending_page_texts.get(path_real, [])))
            self.refresh_page_text_list()
        else:
            img_data = np.fromfile(path_real, dtype=np.uint8)
            img = cv2.imdecode(img_data, cv2.IMREAD_UNCHANGED)

            if img is not None:
                if len(img.shape) == 2: img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
                elif len(img.shape) == 3 and img.shape[2] == 4: img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
                else: img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                self.history = HistoryManager(Config.MAX_HISTORY)
                self.canvas.set_image(img)
                self.canvas.clear_texts()
                self.canvas.pending_texts = list(self.pending_page_texts.get(path_real, []))
                self.refresh_page_text_list()
                
                self.image_sessions[path_real] = {
                    "img": img.copy(),
                    "mask": self.canvas.mask.copy(),
                    "history": self.history,
                    "texts": [],
                    "pending_texts": list(self.canvas.pending_texts)
                }
            else:
                QMessageBox.warning(self, "Load Error", f"The file is corrupted or cannot be processed:\n{os.path.basename(path_real)}")
                logger.error(f"Failed to decode image: {path_real}")
                
        self._check_lock_state()
        if hasattr(self, "translator_page"):
            self.translator_page.refresh_active_page_preview()

    def on_export(self, fmt):
        if self.canvas.cv_img is None: return
        path, _ = QFileDialog.getSaveFileName(self, "Export", "", f"{fmt.upper()} (*.{fmt})")
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
        if self.canvas.cv_img is None or not self.current_img_path: return

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
                res = PhotoshopBridge.send_to_ps(orig, composited)
            elif target == "photopea":
                res = PhotopeaBridge.send_to_photopea(orig, composited, self.current_img_path)
            self.setCursor(Qt.ArrowCursor)

            if res != "Success":
                logger.error(f"[X] UI Blocked Editor Bridge Transfer: {res}")
                QMessageBox.warning(self, "Editor Error", f"Could not send to {target.capitalize()}:\n{res}\n\nCheck your logs folder for details.")

    def update_telemetry(self):
        ram, gpu = self.monitor.get_stats()
        self.hw_mon.lbl.setText(f"{'GPU' if gpu else 'CPU'} | RAM: {ram}MB")
        self.hw_mon.bar.setValue(min(ram // 40, 100))

#/////////////////////////////////#
#     BATCH SETUP DIALOG MODAL    #
#/////////////////////////////////#

class BatchSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Setup")
        self.setStyleSheet(f"background-color: {Config.COLOR_PANEL}; color: {Config.COLOR_TEXT};")

        self.scan_mode = QComboBox()
        self.scan_mode.addItems(["none", "Mask", "OCR Scan", "Transparency Scan"])
        self.scan_mode.setStyleSheet(f"background-color: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 4px;")

        self.export_fmt = QComboBox()
        self.export_fmt.addItems(["none", "png", "jpg", "photoshop", "photopea"])
        self.export_fmt.setStyleSheet(f"background-color: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 4px;")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet(f"QPushButton {{ background-color: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 6px; }}")

        layout = QFormLayout(self)
        layout.addRow("Scan Mode:", self.scan_mode)
        layout.addRow("Export Format:", self.export_fmt)
        layout.addWidget(buttons)

    def get_results(self):
        return self.scan_mode.currentText(), self.export_fmt.currentText()