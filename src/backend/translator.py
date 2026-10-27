import os
import re
import subprocess
import unicodedata
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, 
    QFileDialog, QMessageBox, QCheckBox, QComboBox, QInputDialog
)
from PySide6.QtCore import Qt
from src.utils.config import Config
from src.utils.paths import Paths
from src.utils.logger import logger


def _nfc(s: str) -> str:
    """Normalizes Unicode strings to NFC so decomposed NFD filenames/Hangul/Kana match byte-for-byte."""
    return unicodedata.normalize("NFC", s) if s else ""


#/////////////////////////////////#
#    SCRIPT PARSER & GENERATOR    #
#/////////////////////////////////#

class TranslationScriptEngine:
    """Generates and parses structured <translation> .txt templates for scanlation teams."""

    @staticmethod
    def generate_template(project_paths: list) -> str:
        header = (
            "# =====================================================================\n"
            "# MANGA CLEANER - TRANSLATION SCRIPT TEMPLATE\n"
            "# =====================================================================\n"
            "# Instructions:\n"
            "# 1. DO NOT MODIFY OR DELETE the <translation> ... </translation> tags.\n"
            "#    Only text strictly inside those tags will be read.\n"
            "# 2. Each '-' represents a dialogue bubble / text box on that image.\n"
            "# 3. Empty '-' lines are automatically ignored (leave as-is if page has no text).\n"
            "# 4. Add as many '-' lines under an image as needed. Use '//' for manual line breaks.\n"
            "# 5. If 'Match pages by [filename]' is unchecked in the UI, the [brackets] are\n"
            "#    ignored and dialogues are loaded strictly by image order (Image 1, Image 2...).\n"
            "# 6. You may add as many optional notes or comments as desired outside the\n"
            "#    <translation> ... </translation> tags; Manga Cleaner will ignore them.\n"
            "# =====================================================================\n\n"
            "### SERIES TITLE: \n"
            "### CHAPTER: \n\n"
            "<translation>\n\n"
        )

        body_blocks = []
        for idx, path in enumerate(project_paths, start=1):
            filename = _nfc(os.path.basename(path))
            block = f"Image {idx} [{filename}]\n-\n-\n"
            body_blocks.append(block)

        footer = "\n</translation>\n"
        return header + "\n".join(body_blocks) + footer

    @staticmethod
    def parse_script(raw_text: str) -> list:
        non_comment_lines = [
            line for line in raw_text.splitlines()
            if not line.strip().startswith("#")
        ]
        cleaned_text = "\n".join(non_comment_lines)

        tag_pattern = re.compile(
            r"^\s*<translation>\s*$(.*?)^\s*</translation>\s*$",
            re.IGNORECASE | re.DOTALL | re.MULTILINE
        )
        match = tag_pattern.search(cleaned_text)

        if not match:
            fallback_pattern = re.compile(r"<translation>(.*?)</translation>", re.IGNORECASE | re.DOTALL)
            match = fallback_pattern.search(cleaned_text)

        if not match:
            raise ValueError(
                "Could not find <translation> ... </translation> tags in the selected file.\n"
                "Please ensure the tags were not modified or deleted."
            )

        inner_content = match.group(1)
        entries = []
        current_entry = None

        img_header_re = re.compile(r"^\s*image\s+(\d+)(?:\s*\[([^\]]+)\])?", re.IGNORECASE)

        for raw_line in inner_content.splitlines():
            line = raw_line.strip()

            if not line or (line.startswith("(") and not line.startswith("-")):
                continue

            header_match = img_header_re.match(line)
            if header_match:
                img_idx = int(header_match.group(1))
                bracket_name = _nfc(header_match.group(2).strip()) if header_match.group(2) else None
                current_entry = {
                    "index": img_idx,
                    "filename": bracket_name,
                    "lines": []
                }
                entries.append(current_entry)
                continue

            if line.startswith("-") and current_entry is not None:
                dialogue = _nfc(line[1:].strip())
                if dialogue:
                    dialogue = dialogue.replace("//", "\n")
                    current_entry["lines"].append(dialogue)

        return entries


#/////////////////////////////////#
#    TRANSLATOR UI WORKSPACE      #
#/////////////////////////////////#

class TranslatorPanel(QWidget):
    """Self-contained UI workspace for the TRANSLATOR (.txt script) category."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.loaded_script_path = None
        self.parsed_entries = []
        self.path_dialogues_map = {}  # { full_path: ["line1", "line2"] }
        
        # Base translations path (shared with MangaTranslate)
        self.translations_root = getattr(Paths, "TRANSLATIONS", os.path.join(Paths.BUNDLE_DIR, "translations"))
        os.makedirs(self.translations_root, exist_ok=True)
        
        self.init_ui()
        self.refresh_series_folders()

    def init_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 6, 4, 4)
        lay.setSpacing(6)

        title = QLabel("SCRIPT GENERATOR & IMPORTER")
        title.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-size: 11px; font-weight: bold;")
        lay.addWidget(title)

        # --- SECTION 1: GENERATE TEMPLATE ---
        lbl_gen = QLabel("1. TEMPLATE GENERATOR (.TXT)")
        lbl_gen.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold;")
        lay.addWidget(lbl_gen)

        desc_gen = QLabel("Generates a structured .txt file matching all currently loaded images in Project Assets.")
        desc_gen.setWordWrap(True)
        desc_gen.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        lay.addWidget(desc_gen)

        self.btn_gen_txt = QPushButton("📄 Generate .TXT Template")
        self.btn_gen_txt.setObjectName("ActionBtn")
        self.btn_gen_txt.clicked.connect(self.on_generate_template)
        lay.addWidget(self.btn_gen_txt)

        # --- SECTION 2: TRANSLATIONS FOLDER HIERARCHY ---
        lbl_imp = QLabel("2. TRANSLATION SCRIPT SOURCE")
        lbl_imp.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold; margin-top: 6px;")
        lay.addWidget(lbl_imp)

        # Series Subfolder Row
        row_series = QHBoxLayout()
        lbl_series = QLabel("Series:")
        lbl_series.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px; min-width: 42px;")
        
        self.combo_series_folder = QComboBox()
        self.combo_series_folder.setToolTip("Select series folder inside translations/")
        self.combo_series_folder.currentIndexChanged.connect(self._on_series_folder_changed)

        self.btn_new_series_folder = QPushButton("➕")
        self.btn_new_series_folder.setToolTip("Create new series folder in translations/")
        self.btn_new_series_folder.setFixedSize(26, 24)
        self.btn_new_series_folder.setStyleSheet("background-color: #1e1e28; border: 1px solid #333342; font-size: 11px;")
        self.btn_new_series_folder.clicked.connect(self.on_create_new_series_folder)

        self.btn_open_folder = QPushButton("📁")
        self.btn_open_folder.setToolTip("Open selected series folder in File Explorer")
        self.btn_open_folder.setFixedSize(26, 24)
        self.btn_open_folder.setStyleSheet("background-color: #1e1e28; border: 1px solid #333342; font-size: 11px;")
        self.btn_open_folder.clicked.connect(self.on_open_translations_folder)

        row_series.addWidget(lbl_series)
        row_series.addWidget(self.combo_series_folder, 1)
        row_series.addWidget(self.btn_new_series_folder)
        row_series.addWidget(self.btn_open_folder)
        lay.addLayout(row_series)

        # Script File Selector Row
        row_script_sel = QHBoxLayout()
        lbl_pick = QLabel("Script:")
        lbl_pick.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px; min-width: 42px;")
        
        self.combo_folder_scripts = QComboBox()
        self.combo_folder_scripts.setToolTip("Scripts (.txt) available in the selected series folder")
        self.combo_folder_scripts.activated.connect(self.on_folder_script_selected)

        row_script_sel.addWidget(lbl_pick)
        row_script_sel.addWidget(self.combo_folder_scripts, 1)
        lay.addLayout(row_script_sel)

        # Options Checkboxes
        self.chk_match_brackets = QCheckBox("Match pages by [filename] brackets")
        self.chk_match_brackets.setChecked(True)
        self.chk_match_brackets.setToolTip(
            "When checked, attaches dialogues strictly to the file inside [001.jpg] brackets\n"
            "(entries without brackets or with non-existent filenames are skipped and reported).\n"
            "When unchecked, ignores [] brackets and loads strictly by Image 1, Image 2 order."
        )
        self.chk_match_brackets.setStyleSheet(f"color: {Config.COLOR_TEXT}; font-size: 10px;")
        lay.addWidget(self.chk_match_brackets)

        self.chk_clear_existing = QCheckBox("Replace existing pending layers on import")
        self.chk_clear_existing.setChecked(True)
        self.chk_clear_existing.setStyleSheet(f"color: {Config.COLOR_TEXT}; font-size: 10px;")
        lay.addWidget(self.chk_clear_existing)

        # Action Buttons Row (Import Selected / Browse File)
        row_import_btns = QHBoxLayout()
        self.btn_load_selected_txt = QPushButton("📥 Import Selected")
        self.btn_load_selected_txt.setObjectName("PrimaryBtn")
        self.btn_load_selected_txt.setToolTip("Load and queue dialogues from the script chosen in the dropdown above")
        self.btn_load_selected_txt.setFixedHeight(34)
        self.btn_load_selected_txt.clicked.connect(self.on_import_selected_script)

        self.btn_browse_txt = QPushButton("Browse .TXT...")
        self.btn_browse_txt.setToolTip("Open file dialog to import a .txt script from any location")
        self.btn_browse_txt.setFixedHeight(34)
        self.btn_browse_txt.clicked.connect(self.on_import_script_dialog)

        row_import_btns.addWidget(self.btn_load_selected_txt, 1)
        row_import_btns.addWidget(self.btn_browse_txt, 1)
        lay.addLayout(row_import_btns)

        # Unload / Clear Script from Memory Button
        self.btn_unload_script = QPushButton("🗑️ Unload Script from Memory")
        self.btn_unload_script.setToolTip("Removes all pending dialogue queues from memory without resetting page edits")
        self.btn_unload_script.setStyleSheet(
            "background-color: #241418; color: #ff5566; border: 1px solid #441e22; font-size: 10px; font-weight: bold; padding: 4px;"
        )
        self.btn_unload_script.clicked.connect(self.on_unload_script)
        lay.addWidget(self.btn_unload_script)

        self.lbl_script_status = QLabel("Loaded Script: None")
        self.lbl_script_status.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.lbl_script_status.setWordWrap(True)
        lay.addWidget(self.lbl_script_status)

        # --- SECTION 3: ACTIVE PAGE DIALOGUE PREVIEW ---
        self.lbl_page_lines = QLabel("3. ACTIVE PAGE QUEUED DIALOGUES (0)")
        self.lbl_page_lines.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold; margin-top: 6px;")
        lay.addWidget(self.lbl_page_lines)

        self.dialogue_list = QListWidget()
        self.dialogue_list.setMinimumHeight(130)
        self.dialogue_list.setStyleSheet(f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; font-size: 11px;")
        self.dialogue_list.itemDoubleClicked.connect(self.on_spawn_single_dialogue)
        lay.addWidget(self.dialogue_list, 1)

        row_actions = QHBoxLayout()
        self.btn_spawn_sel = QPushButton("+ Send to Canvas")
        self.btn_spawn_sel.setToolTip("Spawns the selected queued line onto the current page canvas")
        self.btn_spawn_sel.clicked.connect(self.on_spawn_selected_button)

        self.btn_go_typeset = QPushButton("Go to Typesetter ➔")
        self.btn_go_typeset.clicked.connect(lambda: self.mw.set_category("TYPESETTER"))

        row_actions.addWidget(self.btn_spawn_sel, 1)
        row_actions.addWidget(self.btn_go_typeset, 1)
        lay.addLayout(row_actions)

    # --- TRANSLATIONS HIERARCHY METHODS ---
    def refresh_series_folders(self):
        """Populates the series combo with translations/ and its series subdirectories."""
        current_data = self.combo_series_folder.currentData()
        self.combo_series_folder.blockSignals(True)
        self.combo_series_folder.clear()

        base_dir = self.translations_root
        self.combo_series_folder.addItem("📁 [Root] translations/", base_dir)

        natural_key = lambda name: [int(s) if s.isdigit() else s.lower() for s in re.split(r"(\d+)", name)]
        if os.path.exists(base_dir):
            subdirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
            for d in sorted(subdirs, key=natural_key):
                sub_path = os.path.join(base_dir, d)
                self.combo_series_folder.addItem(f"📂 {d}", sub_path)

        idx = self.combo_series_folder.findData(current_data)
        if idx >= 0:
            self.combo_series_folder.setCurrentIndex(idx)
        else:
            self.combo_series_folder.setCurrentIndex(0)

        self.combo_series_folder.blockSignals(False)
        self.refresh_scripts_for_selected_series()

    def get_selected_series_dir(self) -> str:
        data = self.combo_series_folder.currentData()
        if data and os.path.exists(data):
            return data
        return self.translations_root

    def _on_series_folder_changed(self):
        self.refresh_scripts_for_selected_series()

    def refresh_scripts_for_selected_series(self):
        """Populates .txt files strictly belonging to the active series without auto-importing."""
        target_dir = self.get_selected_series_dir()

        self.combo_folder_scripts.blockSignals(True)
        self.combo_folder_scripts.clear()
        self.combo_folder_scripts.addItem("Select script...", "")

        if os.path.exists(target_dir):
            natural_key = lambda name: [int(s) if s.isdigit() else s.lower() for s in re.split(r"(\d+)", name)]
            txt_files = [
                f for f in os.listdir(target_dir) 
                if f.lower().endswith(".txt") and os.path.isfile(os.path.join(target_dir, f))
            ]
            for fname in sorted(txt_files, key=natural_key):
                full_path = os.path.join(target_dir, fname)
                self.combo_folder_scripts.addItem(fname, full_path)

        self.combo_folder_scripts.setCurrentIndex(0)
        self.combo_folder_scripts.blockSignals(False)

    def on_create_new_series_folder(self):
        folder_name, ok = QInputDialog.getText(
            self, "New Series Folder", "Enter series / comic title name:"
        )
        if ok and folder_name.strip():
            clean_name = re.sub(r'[\\/*?:"<>|]', "", folder_name.strip())
            new_path = os.path.join(self.translations_root, clean_name)
            os.makedirs(new_path, exist_ok=True)
            self.refresh_series_folders()
            idx = self.combo_series_folder.findData(new_path)
            if idx >= 0:
                self.combo_series_folder.setCurrentIndex(idx)

    def on_folder_script_selected(self, index: int):
        if index <= 0:
            return
        selected_path = self.combo_folder_scripts.itemData(index)
        if selected_path and os.path.exists(selected_path):
            self.import_script_from_path(selected_path)

    def on_open_translations_folder(self):
        folder = self.get_selected_series_dir()
        os.makedirs(folder, exist_ok=True)
        if os.name == "nt":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])

    # --- PROJECT RESOLUTION HELPERS ---
    def _get_all_project_paths(self) -> list:
        return [self.mw.file_list.item(i).data(Qt.UserRole) for i in range(self.mw.file_list.count())]

    def _resolve_entries_to_paths(self, project_paths: list, entries: list, use_brackets: bool) -> tuple:
        resolved = {}
        unmatched = []
        basename_to_path = {_nfc(os.path.basename(p)).lower(): p for p in project_paths}
        stem_to_path = {_nfc(os.path.splitext(os.path.basename(p))[0]).lower(): p for p in project_paths}

        for entry in entries:
            lines = entry.get("lines", [])
            if not lines:
                continue

            target_path = None
            if use_brackets:
                raw_fname = entry.get("filename")
                if raw_fname:
                    fname_key = _nfc(raw_fname.strip()).lower()
                    target_path = basename_to_path.get(fname_key)
                    if target_path is None:
                        stem_key = os.path.splitext(fname_key)[0]
                        target_path = stem_to_path.get(stem_key)
                    if target_path is None:
                        unmatched.append(f"Image {entry.get('index')} [{raw_fname}]")
                else:
                    unmatched.append(f"Image {entry.get('index')} [missing brackets]")
            else:
                idx = entry.get("index", 0) - 1
                if 0 <= idx < len(project_paths):
                    target_path = project_paths[idx]
                else:
                    unmatched.append(f"Image {entry.get('index')}")

            if target_path:
                if target_path not in resolved:
                    resolved[target_path] = []
                resolved[target_path].extend(lines)

        return resolved, unmatched

    # --- SCRIPT OPERATIONS ---
    def on_generate_template(self):
        paths = self._get_all_project_paths()
        if not paths:
            QMessageBox.warning(
                self,
                "No Images Loaded",
                "Please import a folder with at least 1 image before generating the translation template."
            )
            return

        target_dir = self.get_selected_series_dir()
        default_file = os.path.join(target_dir, "translation_script.txt")
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Translation Template", default_file, "Text Files (*.txt)"
        )
        if not save_path:
            return

        if not save_path.lower().endswith(".txt"):
            save_path += ".txt"

        try:
            content = TranslationScriptEngine.generate_template(paths)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"[TRANSLATOR] Generated template for {len(paths)} images: {save_path}")
            self.refresh_scripts_for_selected_series()
            QMessageBox.information(
                self,
                "Template Generated",
                f"Created translation template for {len(paths)} images:\n{save_path}"
            )
        except Exception as e:
            logger.error(f"[TRANSLATOR] Failed to generate template: {e}")
            QMessageBox.critical(self, "Error", f"Could not save template:\n{e}")

    def on_import_selected_script(self):
        idx = self.combo_folder_scripts.currentIndex()
        if idx <= 0:
            QMessageBox.warning(self, "No Script Selected", "Please select a script from the dropdown or click 'Browse .TXT...'.")
            return
        selected_path = self.combo_folder_scripts.itemData(idx)
        if selected_path and os.path.exists(selected_path):
            self.import_script_from_path(selected_path)

    def on_import_script_dialog(self):
        paths = self._get_all_project_paths()
        if not paths:
            QMessageBox.warning(
                self,
                "No Images Loaded",
                "Please import a folder with at least 1 image before importing a translation script."
            )
            return

        target_dir = self.get_selected_series_dir()
        open_path, _ = QFileDialog.getOpenFileName(
            self, "Import Translation Script (.txt)", target_dir, "Text Files (*.txt)"
        )
        if not open_path:
            return

        self.import_script_from_path(open_path)

    def import_script_from_path(self, open_path: str):
        paths = self._get_all_project_paths()
        if not paths:
            QMessageBox.warning(self, "No Images Loaded", "Please import an image folder first.")
            return

        try:
            with open(open_path, "r", encoding="utf-8") as f:
                raw_text = f.read()

            entries = TranslationScriptEngine.parse_script(raw_text)
            self.loaded_script_path = open_path
            self.parsed_entries = entries

            use_brackets = self.chk_match_brackets.isChecked()
            self.path_dialogues_map, unmatched = self._resolve_entries_to_paths(paths, entries, use_brackets)

            total_lines = sum(len(v) for v in self.path_dialogues_map.values())
            pages_with_text = len(self.path_dialogues_map)
            mode_str = "[filename]" if use_brackets else "Order"
            self.lbl_script_status.setText(
                f"Loaded ({mode_str}): {os.path.basename(open_path)} ({total_lines} lines / {pages_with_text} pages)"
            )

            queued_pages = self.queue_script_across_project(
                self.path_dialogues_map, replace_existing=self.chk_clear_existing.isChecked()
            )
            self.refresh_active_page_preview()

            unmatched_msg = ""
            if unmatched:
                preview_unmatched = ", ".join(unmatched[:5])
                if len(unmatched) > 5:
                    preview_unmatched += f" (+{len(unmatched) - 5} more)"
                unmatched_msg = f"\n⚠️ Unmatched pages ({len(unmatched)}): {preview_unmatched}\n"

            QMessageBox.information(
                self,
                "Script Queued in Layers",
                f"Matched by: {'[filename] brackets' if use_brackets else 'Image Order'}\n"
                f"Queued {total_lines} dialogue lines across {queued_pages} pages.\n"
                f"{unmatched_msg}\n"
                f"In TYPESETTER -> PAGE TEXT LAYERS, simply click any '[ + ]' line to spawn it on the canvas!"
            )

        except Exception as e:
            logger.error(f"[TRANSLATOR] Script import error: {e}")
            QMessageBox.critical(self, "Script Import Error", str(e))

    def on_unload_script(self):
        """Clears all queued [ + ] lines across all loaded pages and frees in-memory translation mappings."""
        if not self.mw.pending_page_texts and not self.mw.canvas.pending_texts and not self.path_dialogues_map:
            QMessageBox.information(self, "Notice", "There are no queued script dialogues in memory to unload.")
            return

        ans = QMessageBox.question(
            self,
            "Unload Script",
            "Are you sure you want to unload the current translation script from memory?\n\n"
            "• All unplaced '[ + ]' dialogue queues across all pages will be removed.\n"
            "• Placed texts already on the canvas will NOT be deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if ans != QMessageBox.Yes:
            return

        # 1. Clear memory caches
        self.loaded_script_path = None
        self.parsed_entries.clear()
        self.path_dialogues_map.clear()
        self.mw.pending_page_texts.clear()
        self.mw.canvas.pending_texts.clear()

        # 2. Reset combo indicator & status label
        self.combo_folder_scripts.setCurrentIndex(0)
        self.lbl_script_status.setText("Loaded Script: None")

        # 3. Synchronize both Translator and Typesetter layer lists
        self.refresh_active_page_preview()
        self.mw.refresh_page_text_list()

        QMessageBox.information(
            self,
            "Script Unloaded",
            "The translation script has been unloaded from memory successfully."
        )

    def queue_script_across_project(self, path_dialogues_map: dict, replace_existing: bool = True) -> int:
        if replace_existing:
            self.mw.pending_page_texts.clear()
            self.mw.canvas.pending_texts.clear()

        queued_count = 0
        for path, lines in path_dialogues_map.items():
            if not lines:
                continue

            if replace_existing or path not in self.mw.pending_page_texts:
                self.mw.pending_page_texts[path] = list(lines)
            else:
                self.mw.pending_page_texts[path].extend(lines)

            queued_count += 1

        if self.mw.current_img_path:
            self.mw.canvas.pending_texts = list(self.mw.pending_page_texts.get(self.mw.current_img_path, []))
            self.mw.refresh_page_text_list()

        return queued_count

    def refresh_active_page_preview(self):
        """Displays the remaining queued lines for the active page so Translator & Typesetter stay 100% synced."""
        self.dialogue_list.clear()
        curr_path = self.mw.current_img_path
        if not curr_path:
            self.lbl_page_lines.setText("3. ACTIVE PAGE QUEUED DIALOGUES (0)")
            return

        lines = self.mw.canvas.pending_texts
        fname = os.path.basename(curr_path)
        self.lbl_page_lines.setText(f"3. [{fname}] QUEUED ({len(lines)})")

        for i, line in enumerate(lines):
            preview = line.replace("\n", " // ")
            item = QListWidgetItem(f"[ + ] {i + 1}. {preview}")
            item.setData(Qt.UserRole, i)
            self.dialogue_list.addItem(item)

    def on_spawn_selected_button(self):
        curr = self.dialogue_list.currentItem()
        if curr:
            self.on_spawn_single_dialogue(curr)

    def on_spawn_single_dialogue(self, list_item):
        if self.mw.canvas.cv_img is None or self.mw.canvas.is_locked:
            return
        p_idx = list_item.data(Qt.UserRole)
        if p_idx is not None:
            self.mw.spawn_pending_text_by_index(int(p_idx))