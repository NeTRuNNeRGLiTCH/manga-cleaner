import os
import re
import unicodedata
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem, 
                             QFileDialog, QMessageBox, QCheckBox)
from PySide6.QtCore import Qt
from src.utils.config import Config
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
        """
        Strips '#' comment lines first, then extracts content strictly between
        standalone <translation> and </translation> tags.
        """
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

            # Only standard ASCII hyphen-minus '-' counts as a valid dialogue bullet
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
        self.init_ui()

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

        # --- SECTION 2: IMPORT SCRIPT ---
        lbl_imp = QLabel("2. IMPORT TRANSLATED SCRIPT")
        lbl_imp.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold; margin-top: 6px;")
        lay.addWidget(lbl_imp)

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

        self.btn_load_txt = QPushButton("📥 Import .TXT && Queue in Layers")
        self.btn_load_txt.setObjectName("PrimaryBtn")
        self.btn_load_txt.setFixedHeight(38)
        self.btn_load_txt.clicked.connect(self.on_import_script)
        lay.addWidget(self.btn_load_txt)

        self.lbl_script_status = QLabel("Loaded Script: None")
        self.lbl_script_status.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
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

    def _get_all_project_paths(self) -> list:
        return [self.mw.file_list.item(i).data(Qt.UserRole) for i in range(self.mw.file_list.count())]

    def _resolve_entries_to_paths(self, project_paths: list, entries: list, use_brackets: bool) -> tuple:
        """
        Maps parsed script entries to actual project file paths using NFC Unicode normalization.
        - If use_brackets is True: strictly requires [filename] brackets and matches by NFC basename or stem.
          Any entry missing brackets or not matching a loaded file is skipped and reported in unmatched.
        - If use_brackets is False: ignores brackets and maps strictly by 1-based image order.
        """
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
                    # Strictly reject entries without brackets when [filename] mode is active
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

    def on_generate_template(self):
        paths = self._get_all_project_paths()
        if not paths:
            QMessageBox.warning(
                self,
                "No Images Loaded",
                "Please import a folder with at least 1 image before generating the translation template."
            )
            return

        default_dir = os.path.dirname(paths[0])
        default_file = os.path.join(default_dir, "translation_script.txt")
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
            QMessageBox.information(
                self,
                "Template Generated",
                f"Created translation template for {len(paths)} images:\n{save_path}"
            )
        except Exception as e:
            logger.error(f"[TRANSLATOR] Failed to generate template: {e}")
            QMessageBox.critical(self, "Error", f"Could not save template:\n{e}")

    def on_import_script(self):
        paths = self._get_all_project_paths()
        if not paths:
            QMessageBox.warning(
                self,
                "No Images Loaded",
                "Please import a folder with at least 1 image before importing a translation script."
            )
            return

        default_dir = os.path.dirname(paths[0])
        open_path, _ = QFileDialog.getOpenFileName(
            self, "Import Translation Script (.txt)", default_dir, "Text Files (*.txt)"
        )
        if not open_path:
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
                f"Queued {total_lines} dialogue lines across {queued_pages} pages (0 MB extra RAM used)."
                f"{unmatched_msg}\n"
                f"In TYPESETTER -> PAGE TEXT LAYERS, simply click any '[ + ]' line to spawn it on the canvas with your currently selected font!"
            )

        except Exception as e:
            logger.error(f"[TRANSLATOR] Script import error: {e}")
            QMessageBox.critical(self, "Script Import Error", str(e))

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

            # Highlight page indicator in Project Assets so user sees which pages have dialogues!
            self.mw.file_list.update_item_state(path, "modified")
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
        """Uses the exact same pop-and-spawn pipeline as Typesetter so lines are never duplicated."""
        if self.mw.canvas.cv_img is None or self.mw.canvas.is_locked:
            return
        p_idx = list_item.data(Qt.UserRole)
        if p_idx is not None:
            self.mw.spawn_pending_text_by_index(int(p_idx))