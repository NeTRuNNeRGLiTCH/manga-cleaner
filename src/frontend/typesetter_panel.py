import json
import os
import shutil

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.frontend.canvas import MangaTextItem
from src.frontend.widgets import ColorSwatchButton, ToolGroup
from src.utils.config import Config
from src.utils.i18n import tr
from src.utils.logger import logger
from src.utils.paths import Paths


class TypesetterPanel(QWidget):
    """Owns the Typesetter controls, font preferences, and text-layer list."""

    def __init__(self, main_window):
        """Initialize the Typesetter panel, font preferences, and text controls."""
        super().__init__(main_window)
        self.mw = main_window
        self.canvas = main_window.canvas
        self._initialize_font_preferences()
        self.canvas.default_font_family = self.last_selected_font
        self._build_ui()
        self.update_color_swatches()

    def _initialize_font_preferences(self):
        """Prepare font preference state and migrate legacy settings when present."""
        self.font_prefs_path = os.path.join(Paths.CACHE, "font_presets.json")
        legacy_path = os.path.join(Paths.BUNDLE_DIR, "font_presets.json")
        if not os.path.exists(self.font_prefs_path) and os.path.exists(legacy_path):
            try:
                shutil.move(legacy_path, self.font_prefs_path)
            except Exception as exc:
                logger.warning(f"Could not migrate legacy font presets: {exc}")

        self.favorite_fonts = set()
        self.font_aliases = {}
        self.fav_only_pref = False
        self.last_selected_font = "Arial"
        self.all_system_fonts = None
        self._load_font_prefs()

    def _load_font_prefs(self):
        """Load saved favorites, aliases, filter state, and the last selected font."""
        if not os.path.exists(self.font_prefs_path):
            return
        try:
            with open(self.font_prefs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.favorite_fonts = set(data.get("favorites", []))
            self.font_aliases = dict(data.get("aliases", {}))
            self.fav_only_pref = bool(data.get("fav_only", False))
            self.last_selected_font = str(data.get("last_font", "Arial"))
        except Exception as exc:
            logger.error(f"Failed to load font presets: {exc}")

    def _save_font_prefs(self):
        """Persist font favorites, aliases, filter state, and the selected font."""
        try:
            with open(self.font_prefs_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "favorites": sorted(self.favorite_fonts),
                        "aliases": self.font_aliases,
                        "fav_only": bool(self.fav_only_pref),
                        "last_font": self.last_selected_font,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as exc:
            logger.error(f"Failed to save font presets: {exc}")

    def _build_ui(self):
        """Create the font, text-style, color, and text-layer controls."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.type_tools = ToolGroup(tr("main.typesetter_tools"), ["MOVE", "TEXT"])
        self.type_tools.buttons["MOVE"].clicked.connect(lambda: self.mw.set_tool("NONE"))
        self.type_tools.buttons["TEXT"].clicked.connect(lambda: self.mw.set_tool("TEXT"))
        layout.addWidget(self.type_tools)

        title = QLabel(tr("main.font_manager_filter"))
        title.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold;")
        layout.addWidget(title)

        filter_row = QHBoxLayout()
        self.font_search = QLineEdit()
        self.font_search.setPlaceholderText(tr("main.search_font_or_alias"))
        self.font_search.setStyleSheet(
            f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 3px; font-size: 11px;"
        )
        self.font_search.textChanged.connect(self.populate_font_combo)

        self.chk_fav_only = QCheckBox(tr("main.only"))
        self.chk_fav_only.setToolTip(tr("main.show_only_favorite_fonts_saved_across"))
        self.chk_fav_only.setStyleSheet(
            f"color: {Config.COLOR_ACCENT}; font-size: 10px; font-weight: bold;"
        )
        self.chk_fav_only.setChecked(self.fav_only_pref)
        self.chk_fav_only.toggled.connect(self.on_fav_only_toggled)
        filter_row.addWidget(self.font_search, 1)
        filter_row.addWidget(self.chk_fav_only)
        layout.addLayout(filter_row)

        font_row = QHBoxLayout()
        self.font_combo = QComboBox()
        self.font_combo.setStyleSheet(
            f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 4px; font-size: 11px;"
        )
        self.font_combo.currentIndexChanged.connect(self.on_font_combo_selected)

        self.btn_fav_font = QPushButton("☆")
        self.btn_fav_font.setFixedWidth(28)
        self.btn_fav_font.setToolTip(tr("main.toggle_favorite_for_current_font"))
        self.btn_fav_font.clicked.connect(self.toggle_current_font_favorite)

        self.btn_alias_font = QPushButton("✎")
        self.btn_alias_font.setFixedWidth(28)
        self.btn_alias_font.setToolTip(tr("main.set_custom_alias_use_case_name"))
        self.btn_alias_font.clicked.connect(self.rename_current_font_alias)
        font_row.addWidget(self.font_combo, 1)
        font_row.addWidget(self.btn_fav_font)
        font_row.addWidget(self.btn_alias_font)
        layout.addLayout(font_row)

        style_row = QHBoxLayout()
        size_label = QLabel(tr("main.size"))
        size_label.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 300)
        self.font_size_spin.setValue(32)
        self.font_size_spin.valueChanged.connect(self.on_text_style_ui_changed)

        self.btn_bold = QPushButton(tr("main.b"))
        self.btn_bold.setCheckable(True)
        self.btn_bold.setFixedWidth(28)
        self.btn_bold.clicked.connect(self.on_text_style_ui_changed)

        self.btn_italic = QPushButton(tr("main.i"))
        self.btn_italic.setCheckable(True)
        self.btn_italic.setFixedWidth(28)
        self.btn_italic.clicked.connect(self.on_text_style_ui_changed)

        self.btn_center = QPushButton("≡")
        self.btn_center.setToolTip(tr("main.center_align_text"))
        self.btn_center.setCheckable(True)
        self.btn_center.setChecked(True)
        self.btn_center.setFixedWidth(28)
        self.btn_center.clicked.connect(self.on_text_style_ui_changed)
        style_row.addWidget(size_label)
        style_row.addWidget(self.font_size_spin, 1)
        style_row.addWidget(self.btn_bold)
        style_row.addWidget(self.btn_italic)
        style_row.addWidget(self.btn_center)
        layout.addLayout(style_row)

        rotation_row = QHBoxLayout()
        angle_label = QLabel(tr("main.angle"))
        angle_label.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.rot_spin = QSpinBox()
        self.rot_spin.setRange(-180, 180)
        self.rot_spin.setSuffix("°")
        self.rot_spin.setValue(0)
        self.rot_spin.valueChanged.connect(self.on_text_rotation_ui_changed)

        self.btn_reset_rot = QPushButton("0°")
        self.btn_reset_rot.setToolTip(tr("main.reset_rotation_to_0"))
        self.btn_reset_rot.setFixedWidth(34)
        self.btn_reset_rot.clicked.connect(lambda: self.rot_spin.setValue(0))

        self.btn_auto_width = QPushButton(tr("main.fit_box"))
        self.btn_auto_width.setToolTip(tr("main.reset_box_width_to_auto_fit"))
        self.btn_auto_width.clicked.connect(self.on_reset_box_width)
        rotation_row.addWidget(angle_label)
        rotation_row.addWidget(self.rot_spin, 1)
        rotation_row.addWidget(self.btn_reset_rot)
        rotation_row.addWidget(self.btn_auto_width)
        layout.addLayout(rotation_row)

        colors_title = QLabel(tr("main.color_swatches_stroke_mode"))
        colors_title.setStyleSheet(
            f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold; margin-top: 4px;"
        )
        layout.addWidget(colors_title)

        color_row = QHBoxLayout()
        fill_label = QLabel(tr("main.fill"))
        fill_label.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.swatch_text_color = ColorSwatchButton(
            QColor(0, 0, 0), width=42, height=24, tooltip=tr("main.click_to_pick_fill_color")
        )
        self.swatch_text_color.clicked.connect(self.choose_text_color)

        self.btn_swap_colors = QPushButton("⇄")
        self.btn_swap_colors.setToolTip(tr("main.swap_fill_and_stroke_colors"))
        self.btn_swap_colors.setFixedWidth(30)
        self.btn_swap_colors.clicked.connect(self.swap_text_and_stroke_colors)

        stroke_label = QLabel(tr("main.stroke"))
        stroke_label.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.swatch_stroke_color = ColorSwatchButton(
            QColor(255, 255, 255), width=42, height=24,
            tooltip=tr("main.click_to_pick_outer_stroke_color"),
        )
        self.swatch_stroke_color.clicked.connect(self.choose_stroke_color)
        color_row.addWidget(fill_label)
        color_row.addWidget(self.swatch_text_color)
        color_row.addStretch()
        color_row.addWidget(self.btn_swap_colors)
        color_row.addStretch()
        color_row.addWidget(stroke_label)
        color_row.addWidget(self.swatch_stroke_color)
        layout.addLayout(color_row)

        self.btn_stroke_mode = QPushButton(tr("main.mode_normal_no_stroke"))
        self.btn_stroke_mode.setCheckable(True)
        self.btn_stroke_mode.setToolTip(tr("main.toggle_between_normal_text_and_outer"))
        self.btn_stroke_mode.toggled.connect(self.on_stroke_mode_toggled)
        layout.addWidget(self.btn_stroke_mode)

        self.stroke_settings_frame = QFrame()
        stroke_row = QHBoxLayout(self.stroke_settings_frame)
        stroke_row.setContentsMargins(0, 0, 0, 0)
        stroke_size_label = QLabel(tr("main.size"))
        stroke_size_label.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.stroke_spin = QSpinBox()
        self.stroke_spin.setRange(1, 30)
        self.stroke_spin.setSuffix(" px")
        self.stroke_spin.setValue(3)
        self.stroke_spin.valueChanged.connect(self.on_text_style_ui_changed)
        opacity_label = QLabel(tr("main.opacity"))
        opacity_label.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.stroke_op_spin = QSpinBox()
        self.stroke_op_spin.setRange(10, 100)
        self.stroke_op_spin.setSuffix("%")
        self.stroke_op_spin.setValue(100)
        self.stroke_op_spin.valueChanged.connect(self.on_text_style_ui_changed)
        stroke_row.addWidget(stroke_size_label)
        stroke_row.addWidget(self.stroke_spin, 1)
        stroke_row.addWidget(opacity_label)
        stroke_row.addWidget(self.stroke_op_spin, 1)
        layout.addWidget(self.stroke_settings_frame)
        self.stroke_settings_frame.setVisible(False)

        layers_header = QHBoxLayout()
        self.lbl_text_layers = QLabel(tr("main.page_text_layers_0_placed_0"))
        self.lbl_text_layers.setStyleSheet(
            f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold; margin-top: 4px;"
        )
        self.chk_show_guides = QCheckBox(tr("main.show_outlines"))
        self.chk_show_guides.setToolTip(tr("main.toggle_bounding_boxes_visibility_for_uns"))
        self.chk_show_guides.setStyleSheet(
            f"color: {Config.COLOR_ACCENT}; font-size: 10px; font-weight: bold;"
        )
        self.chk_show_guides.setChecked(True)
        self.chk_show_guides.toggled.connect(self.canvas.set_show_text_guides)
        layers_header.addWidget(self.lbl_text_layers)
        layers_header.addStretch()
        layers_header.addWidget(self.chk_show_guides)
        layout.addLayout(layers_header)

        self.text_layer_list = QListWidget()
        self.text_layer_list.setMinimumHeight(110)
        self.text_layer_list.setStyleSheet(
            f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; font-size: 11px;"
        )
        self.text_layer_list.itemClicked.connect(self.on_text_layer_item_clicked)
        layout.addWidget(self.text_layer_list, 1)

        queue_actions_row = QHBoxLayout()
        self.btn_new_text = QPushButton(tr("main.new_text"))
        self.btn_new_text.clicked.connect(self.create_new_text)
        self.btn_remove_pending = QPushButton(tr("main.remove_from_queue"))
        self.btn_remove_pending.clicked.connect(self.remove_selected_pending_text)
        queue_actions_row.addWidget(self.btn_new_text, 1)
        queue_actions_row.addWidget(self.btn_remove_pending, 1)
        layout.addLayout(queue_actions_row)

        actions_row = QHBoxLayout()
        self.btn_del_text = QPushButton(tr("main.delete_selected"))
        self.btn_del_text.clicked.connect(self.canvas.delete_selected_texts)
        self.btn_clear_texts = QPushButton(tr("main.clear_all"))
        self.btn_clear_texts.clicked.connect(self.on_clear_all_page_texts)
        actions_row.addWidget(self.btn_del_text, 1)
        actions_row.addWidget(self.btn_clear_texts, 1)
        layout.addLayout(actions_row)

    def populate_font_combo(self):
        """Enumerate system fonts on demand and populate the filtered font selector."""
        if self.all_system_fonts is None:
            self.all_system_fonts = QFontDatabase.families()

        current_family = self.font_combo.currentData(Qt.UserRole)
        if not current_family:
            current_family = self.last_selected_font or self.canvas.default_font_family
        query = self.font_search.text().strip().lower()
        favorites_only = self.chk_fav_only.isChecked()

        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        sorted_fonts = sorted(
            self.all_system_fonts,
            key=lambda family: (
                0 if family in self.favorite_fonts else 1,
                self.font_aliases.get(family, family).lower(),
            ),
        )

        selected_index = 0
        for family in sorted_fonts:
            is_favorite = family in self.favorite_fonts
            if favorites_only and not is_favorite:
                continue
            alias = self.font_aliases.get(family, "")
            if query and query not in f"{family.lower()} {alias.lower()}":
                continue
            star = "★ " if is_favorite else ""
            display_name = f"{star}{alias} [{family}]" if alias else f"{star}{family}"
            self.font_combo.addItem(display_name, family)
            item_index = self.font_combo.count() - 1
            self.font_combo.setItemData(item_index, QFont(family, 10), Qt.FontRole)
            if family == current_family:
                selected_index = item_index

        if self.font_combo.count() > 0:
            self.font_combo.setCurrentIndex(selected_index)
            family = self.font_combo.currentData(Qt.UserRole)
            if family:
                self.canvas.default_font_family = family
                self.last_selected_font = family
        self.font_combo.blockSignals(False)
        self.update_font_fav_button_visual()

    def get_selected_font_family(self) -> str:
        """Return the selected font family or the saved default family."""
        family = self.font_combo.currentData(Qt.UserRole)
        return family if family else self.last_selected_font

    def on_fav_only_toggled(self, checked: bool):
        """Persist the favorites-only filter and refresh the font selector."""
        self.fav_only_pref = bool(checked)
        self._save_font_prefs()
        self.populate_font_combo()

    def update_font_fav_button_visual(self):
        """Show whether the selected font is marked as a favorite."""
        family = self.get_selected_font_family()
        is_favorite = family in self.favorite_fonts
        self.btn_fav_font.setText("★" if is_favorite else "☆")
        self.btn_fav_font.setStyleSheet(
            f"color: {Config.COLOR_ACCENT}; font-weight: bold;" if is_favorite else ""
        )

    def on_font_combo_selected(self):
        """Save the chosen font and apply it to the current text style."""
        family = self.get_selected_font_family()
        if family:
            self.last_selected_font = family
            self._save_font_prefs()
        self.update_font_fav_button_visual()
        self.on_text_style_ui_changed()

    def toggle_current_font_favorite(self):
        """Add or remove the selected font from the favorites list."""
        family = self.get_selected_font_family()
        if not family:
            return
        if family in self.favorite_fonts:
            self.favorite_fonts.remove(family)
        else:
            self.favorite_fonts.add(family)
        self._save_font_prefs()
        self.populate_font_combo()

    def rename_current_font_alias(self):
        """Prompt for and save a display alias for the selected font."""
        family = self.get_selected_font_family()
        if not family:
            return
        current_alias = self.font_aliases.get(family, "")
        new_alias, accepted = QInputDialog.getText(
            self,
            tr("main.rename_alias_font"),
            tr("main.enter_custom_alias_for_fam_leave", fam=family),
            QLineEdit.Normal,
            current_alias,
        )
        if accepted:
            clean_alias = new_alias.strip()
            if clean_alias:
                self.font_aliases[family] = clean_alias
            elif family in self.font_aliases:
                del self.font_aliases[family]
            self._save_font_prefs()
            self.populate_font_combo()

    def update_color_swatches(self):
        """Synchronize fill and stroke swatches with the canvas defaults."""
        self.swatch_text_color.set_color(self.canvas.default_text_color)
        self.swatch_stroke_color.set_color(self.canvas.default_stroke_color)

    def on_stroke_mode_toggled(self, enabled: bool):
        """Show stroke controls and apply the selected stroke mode."""
        self.btn_stroke_mode.setText(
            tr("main.mode_stroke_outside") if enabled else tr("main.mode_normal_no_stroke")
        )
        self.stroke_settings_frame.setVisible(enabled)
        self.on_text_style_ui_changed()

    def refresh_page_text_list(self):
        """Rebuild the list of placed text layers and queued dialogue."""
        self.text_layer_list.blockSignals(True)
        self.text_layer_list.clear()
        placed_count = len(self.canvas.text_items)
        pending_count = len(self.canvas.pending_texts)
        self.lbl_text_layers.setText(
            tr(
                "main.page_text_layers_placed_count_placed",
                placed_count=placed_count,
                pending_count=pending_count,
            )
        )

        if self.mw.current_img_path:
            self.mw.pending_page_texts[self.mw.current_img_path] = list(self.canvas.pending_texts)

        for index, item in enumerate(self.canvas.text_items, start=1):
            preview = item.toPlainText().replace("\n", " ").strip() or "<Empty>"
            if len(preview) > 22:
                preview = preview[:22] + "..."
            list_item = QListWidgetItem(f"[ ✓ ] {index}. {preview}")
            list_item.setData(Qt.UserRole, ("PLACED", item))
            self.text_layer_list.addItem(list_item)
            if item.isSelected():
                list_item.setSelected(True)

        for pending_index, text in enumerate(self.canvas.pending_texts):
            preview = text.replace("\n", " ").strip()
            if len(preview) > 22:
                preview = preview[:22] + "..."
            list_item = QListWidgetItem(f"[ + ] {preview}")
            list_item.setForeground(QColor(Config.COLOR_ACCENT))
            list_item.setToolTip(tr("main.click_to_place_on_canvas_with", text_str=text))
            list_item.setData(Qt.UserRole, ("PENDING", pending_index))
            self.text_layer_list.addItem(list_item)

        self.text_layer_list.blockSignals(False)
        translator = getattr(self.mw, "translator_page", None)
        if translator is not None:
            translator.refresh_active_page_preview()

    def spawn_pending_text_by_index(self, pending_index: int):
        """Place a queued dialogue line on the canvas and remove it from the queue."""
        if self.canvas.cv_img is None or self.canvas.is_locked:
            return
        if 0 <= pending_index < len(self.canvas.pending_texts):
            text = self.canvas.pending_texts.pop(pending_index)
            if self.mw.current_img_path:
                self.mw.pending_page_texts[self.mw.current_img_path] = list(self.canvas.pending_texts)
            if self.canvas.current_tool == "NONE":
                self.mw.set_tool("TEXT", switch_category=False)
            center = self.canvas.mapToScene(self.canvas.viewport().rect().center())
            item = self.canvas.add_text_item(center, initial_text=text, enter_edit=False)
            item.from_script_queue = True
            self.mw.mark_current_modified()
            self.refresh_page_text_list()

    def on_text_layer_item_clicked(self, list_item):
        """Select a placed text layer or a pending dialogue line in the list."""
        data = list_item.data(Qt.UserRole)
        if not isinstance(data, tuple):
            return
        kind, payload = data
        if kind == "PLACED":
            if isinstance(payload, MangaTextItem) and payload in self.canvas.text_items:
                if self.canvas.current_tool == "NONE":
                    self.mw.set_tool("TEXT", switch_category=False)
                self.canvas.scene.clearSelection()
                payload.setSelected(True)
                self.canvas.centerOn(payload)
                self.sync_text_ui_from_item(payload)

    def remove_selected_pending_text(self):
        """Remove the selected pending dialogue line from the active page queue."""
        list_item = self.text_layer_list.currentItem()
        data = list_item.data(Qt.UserRole) if list_item is not None else None
        if not isinstance(data, tuple) or data[0] != "PENDING":
            return

        pending_index = int(data[1])
        if not 0 <= pending_index < len(self.canvas.pending_texts):
            return

        self.canvas.pending_texts.pop(pending_index)
        if self.mw.current_img_path:
            self.mw.pending_page_texts[self.mw.current_img_path] = list(self.canvas.pending_texts)
        self.mw.mark_current_modified()
        self.refresh_page_text_list()

    def create_new_text(self):
        """Create an editable text box without consuming a pending dialogue line."""
        if self.canvas.cv_img is None or self.canvas.is_locked:
            return
        if self.canvas.current_tool != "TEXT":
            self.mw.set_tool("TEXT", switch_category=False)
        center = self.canvas.mapToScene(self.canvas.viewport().rect().center())
        self.canvas.add_text_item(center)

    def on_clear_all_page_texts(self):
        """Remove placed text boxes while preserving queued dialogue."""
        if not self.canvas.text_items:
            return
        self.canvas.clear_placed_texts_only(return_script_items_to_queue=True)
        if self.mw.current_img_path:
            self.mw.pending_page_texts[self.mw.current_img_path] = list(self.canvas.pending_texts)
        self.mw.mark_current_modified()
        self.refresh_page_text_list()

    def sync_text_ui_from_item(self, item: MangaTextItem):
        """Load a selected text item's style and colors into the controls."""
        controls = (
            self.font_combo,
            self.font_size_spin,
            self.btn_bold,
            self.btn_italic,
            self.btn_center,
            self.btn_stroke_mode,
            self.stroke_spin,
            self.stroke_op_spin,
            self.rot_spin,
        )
        for control in controls:
            control.blockSignals(True)

        index = self.font_combo.findData(item.font_family, Qt.UserRole)
        if index >= 0:
            self.font_combo.setCurrentIndex(index)
        self.update_font_fav_button_visual()
        self.font_size_spin.setValue(int(item.font_size))
        self.btn_bold.setChecked(item.is_bold)
        self.btn_italic.setChecked(item.is_italic)
        self.btn_center.setChecked(item.align_center)
        self.btn_stroke_mode.setChecked(item.stroke_enabled)
        self.btn_stroke_mode.setText(
            tr("main.mode_stroke_outside") if item.stroke_enabled else tr("main.mode_normal_no_stroke")
        )
        self.stroke_settings_frame.setVisible(item.stroke_enabled)
        self.stroke_spin.setValue(max(1, int(item.stroke_width)))
        self.stroke_op_spin.setValue(int(item.stroke_opacity))
        self.rot_spin.setValue(int(round(item.rotation())))
        self.canvas.default_text_color = QColor(item.text_color)
        self.canvas.default_stroke_color = QColor(item.stroke_color)
        self.update_color_swatches()
        for control in controls:
            control.blockSignals(False)
        self.refresh_page_text_list()

    def on_text_rotation_ui_changed(self, value):
        """Apply the selected rotation angle to selected text items."""
        for item in self.canvas.scene.selectedItems():
            if isinstance(item, MangaTextItem):
                item.set_rotation_angle(float(value))

    def on_reset_box_width(self):
        """Restore automatic box width for selected text items."""
        for item in self.canvas.scene.selectedItems():
            if isinstance(item, MangaTextItem):
                item.reset_box_width()

    def on_text_style_ui_changed(self):
        """Apply current font and stroke settings to new and selected text."""
        family = self.get_selected_font_family()
        size = self.font_size_spin.value()
        bold = self.btn_bold.isChecked()
        italic = self.btn_italic.isChecked()
        center = self.btn_center.isChecked()
        stroke_enabled = self.btn_stroke_mode.isChecked()
        stroke_width = self.stroke_spin.value()
        stroke_opacity = self.stroke_op_spin.value()

        self.canvas.default_font_family = family
        self.canvas.default_font_size = size
        self.canvas.default_bold = bold
        self.canvas.default_italic = italic
        self.canvas.default_align_center = center
        self.canvas.default_stroke_enabled = stroke_enabled
        self.canvas.default_stroke_width = stroke_width
        self.canvas.default_stroke_opacity = stroke_opacity

        for item in self.canvas.scene.selectedItems():
            if isinstance(item, MangaTextItem):
                item.font_family = family
                item.font_size = size
                item.is_bold = bold
                item.is_italic = italic
                item.align_center = center
                item.stroke_enabled = stroke_enabled
                item.stroke_width = stroke_width
                item.stroke_opacity = stroke_opacity
                item.update_style()
                self.mw.mark_current_modified()

    def swap_text_and_stroke_colors(self):
        """Exchange the default fill and stroke colors."""
        self.canvas.default_text_color, self.canvas.default_stroke_color = (
            QColor(self.canvas.default_stroke_color),
            QColor(self.canvas.default_text_color),
        )
        self.update_color_swatches()
        for item in self.canvas.scene.selectedItems():
            if isinstance(item, MangaTextItem):
                item.text_color = QColor(self.canvas.default_text_color)
                item.stroke_color = QColor(self.canvas.default_stroke_color)
                item.update_style()
                self.mw.mark_current_modified()

    def choose_text_color(self):
        """Choose and apply a fill color for text."""
        color = QColorDialog.getColor(
            self.canvas.default_text_color, self, tr("main.select_text_fill_color")
        )
        if color.isValid():
            self.canvas.default_text_color = color
            self.update_color_swatches()
            for item in self.canvas.scene.selectedItems():
                if isinstance(item, MangaTextItem):
                    item.text_color = color
                    item.update_style()
                    self.mw.mark_current_modified()

    def choose_stroke_color(self):
        """Choose and apply an outer stroke color for text."""
        color = QColorDialog.getColor(
            self.canvas.default_stroke_color, self, tr("main.select_outer_stroke_color")
        )
        if color.isValid():
            self.canvas.default_stroke_color = color
            self.update_color_swatches()
            for item in self.canvas.scene.selectedItems():
                if isinstance(item, MangaTextItem):
                    item.stroke_color = color
                    item.update_style()
                    self.mw.mark_current_modified()
