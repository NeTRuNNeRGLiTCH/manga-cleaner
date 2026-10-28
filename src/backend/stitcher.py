import os
import re
import cv2
import numpy as np
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QComboBox, QSpinBox, 
                             QListWidget, QListWidgetItem, QFileDialog, 
                             QMessageBox, QCheckBox, QProgressDialog,
                             QInputDialog, QLineEdit)
from PySide6.QtCore import Qt, QCoreApplication
from src.utils.config import Config
from src.utils.logger import logger
from src.utils.i18n import tr


def _natural_sort_key(path: str) -> list:
    """
    Splits a filename into text and integer chunks so '2.jpg' comes before '10.jpg' and '100.jpg'.
    """
    basename = os.path.basename(path)
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", basename)]


#/////////////////////////////////#
#     LOSSLESS STITCH ENGINE      #
#/////////////////////////////////#

class StitchEngine:
    """Handles vertical image concatenation without seams or quality loss."""

    @staticmethod
    def align_widths_and_channels(images: list) -> list:
        """
        Ensures all numpy image arrays in a block share the exact same width and channel count
        before vertical stacking so np.vstack never fails or creates seams.
        """
        if not images:
            return []

        # Determine target width (max width in group to never downscale/lose detail)
        target_w = max(img.shape[1] for img in images)
        has_alpha = any(len(img.shape) == 3 and img.shape[2] == 4 for img in images)
        target_c = 4 if has_alpha else 3

        aligned = []
        for img in images:
            curr = img
            # Normalize channels
            if len(curr.shape) == 2:
                curr = cv2.cvtColor(curr, cv2.COLOR_GRAY2RGBA if target_c == 4 else cv2.COLOR_GRAY2RGB)
            elif curr.shape[2] == 3 and target_c == 4:
                curr = cv2.cvtColor(curr, cv2.COLOR_RGB2RGBA)
            elif curr.shape[2] == 4 and target_c == 3:
                curr = cv2.cvtColor(curr, cv2.COLOR_RGBA2RGB)

            # Match width using high-fidelity Lanczos4 interpolation if a page differs slightly
            h, w = curr.shape[:2]
            if w != target_w:
                scale = target_w / float(w)
                new_h = max(1, int(round(h * scale)))
                curr = cv2.resize(curr, (target_w, new_h), interpolation=cv2.INTER_LANCZOS4)

            aligned.append(curr)

        return aligned

    @staticmethod
    def split_by_max_height(images: list, paths: list, max_height: int) -> list:
        """
        If max_height > 0, splits a single block into sub-blocks whenever adding the next page
        would exceed max_height (unless it's a single page already taller than max_height).
        Returns list of (sub_images, sub_paths).
        """
        if max_height <= 0 or not images:
            return [(images, paths)]

        sub_blocks = []
        curr_imgs = []
        curr_paths = []
        curr_h = 0

        for img, p in zip(images, paths):
            h = img.shape[0]
            if curr_imgs and (curr_h + h > max_height):
                sub_blocks.append((curr_imgs, curr_paths))
                curr_imgs = [img]
                curr_paths = [p]
                curr_h = h
            else:
                curr_imgs.append(img)
                curr_paths.append(p)
                curr_h += h

        if curr_imgs:
            sub_blocks.append((curr_imgs, curr_paths))

        return sub_blocks

    @staticmethod
    def save_lossless(stitched_rgb: np.ndarray, out_path: str, fmt: str) -> bool:
        """Saves RGB/RGBA numpy array to disk with 0% quality loss."""
        fmt = fmt.lower()
        if len(stitched_rgb.shape) == 3 and stitched_rgb.shape[2] == 4:
            if fmt in ("jpg", "jpeg"):
                img_out = cv2.cvtColor(stitched_rgb, cv2.COLOR_RGBA2BGR)
            else:
                img_out = cv2.cvtColor(stitched_rgb, cv2.COLOR_RGBA2BGRA)
        else:
            img_out = cv2.cvtColor(stitched_rgb, cv2.COLOR_RGB2BGR)

        if fmt in ("jpg", "jpeg"):
            # 100% Quality + 4:4:4 Chroma (no color bleeding on sharp manga text)
            params = [
                int(cv2.IMWRITE_JPEG_QUALITY), 100,
                int(cv2.IMWRITE_JPEG_SAMPLING_FACTOR), int(cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444)
            ]
            ext = ".jpg"
        else:
            # Lossless PNG compression
            params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            ext = ".png"

        try:
            is_success, im_buf_arr = cv2.imencode(ext, img_out, params)
        except Exception:
            # Fallback if OpenCV build lacks sampling factor flag
            fallback_params = [int(cv2.IMWRITE_JPEG_QUALITY), 100] if ext == ".jpg" else [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            is_success, im_buf_arr = cv2.imencode(ext, img_out, fallback_params)

        if is_success:
            im_buf_arr.tofile(out_path)
            return True
        return False


#/////////////////////////////////#
#     STITCHER UI WORKSPACE       #
#/////////////////////////////////#

class StitcherPanel(QWidget):
    """Self-contained UI workspace for the STITCHER category."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        # Each block is a dict: {"name": "stitched_001", "paths": [path1, path2, ...]}
        self.stitch_blocks = []
        self.init_ui()

    def init_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 6, 4, 4)
        lay.setSpacing(6)

        title = QLabel("LOSSLESS IMAGE STITCHER")
        title.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-size: 11px; font-weight: bold;")
        lay.addWidget(title)

        # --- GROUPING MODE ---
        lbl_mode = QLabel("1. GROUPING / BLOCK BUILDER")
        lbl_mode.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold;")
        lay.addWidget(lbl_mode)

        self.chk_natural_sort = QCheckBox("Natural numeric sort (1, 2 ... 10, 100)")
        self.chk_natural_sort.setChecked(True)
        self.chk_natural_sort.setToolTip(
            "Automatically orders files numerically (e.g. 1.jpg, 2.jpg, 10.jpg, 100.jpg)\n"
            "even if the operating system loaded them out of order."
        )
        self.chk_natural_sort.setStyleSheet(f"color: {Config.COLOR_TEXT}; font-size: 10px;")
        self.chk_natural_sort.toggled.connect(self.refresh_file_combos)
        lay.addWidget(self.chk_natural_sort)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Manual Blocks (By Filename / Checked)",
            "Auto: Pages per Output File",
            "Auto: Fit to Max File Count"
        ])
        self.mode_combo.setStyleSheet(f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 4px; font-size: 11px;")
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        lay.addWidget(self.mode_combo)

        # Dynamic Controls Frame
        self.ctrl_frame = QFrame()
        ctrl_lay = QVBoxLayout(self.ctrl_frame)
        ctrl_lay.setContentsMargins(0, 2, 0, 2)
        ctrl_lay.setSpacing(4)

        # File Selectors (From File -> To File)
        self.manual_row = QWidget()
        m_lay = QVBoxLayout(self.manual_row)
        m_lay.setContentsMargins(0, 0, 0, 0)
        m_lay.setSpacing(4)

        row_from = QHBoxLayout()
        lbl_from = QLabel("From:")
        lbl_from.setFixedWidth(36)
        lbl_from.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.combo_from = QComboBox()
        self.combo_from.setStyleSheet(f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 3px; font-size: 11px;")
        row_from.addWidget(lbl_from)
        row_from.addWidget(self.combo_from, 1)

        row_to = QHBoxLayout()
        lbl_to = QLabel("To:")
        lbl_to.setFixedWidth(36)
        lbl_to.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.combo_to = QComboBox()
        self.combo_to.setStyleSheet(f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 3px; font-size: 11px;")
        row_to.addWidget(lbl_to)
        row_to.addWidget(self.combo_to, 1)

        m_lay.addLayout(row_from)
        m_lay.addLayout(row_to)
        ctrl_lay.addWidget(self.manual_row)

        self.btn_add_range = QPushButton("+ Add File Range (From ➔ To)")
        self.btn_add_range.setToolTip("Groups all files between 'From' and 'To' into one stitched block")
        self.btn_add_range.clicked.connect(self.add_range_as_block)
        ctrl_lay.addWidget(self.btn_add_range)

        self.btn_add_checked = QPushButton("+ Add Checked Files as Block")
        self.btn_add_checked.setToolTip("Groups all currently checked files in Project Assets into one stitched block")
        self.btn_add_checked.clicked.connect(self.add_checked_as_block)
        ctrl_lay.addWidget(self.btn_add_checked)

        # Row for Auto Modes (Pages per Strip OR Max Target Files)
        self.auto_row = QWidget()
        a_lay = QHBoxLayout(self.auto_row)
        a_lay.setContentsMargins(0, 0, 0, 0)
        self.lbl_auto_param = QLabel("Pages per File:")
        self.lbl_auto_param.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.spin_auto_val = QSpinBox()
        self.spin_auto_val.setRange(2, 9999)
        self.spin_auto_val.setValue(5)
        a_lay.addWidget(self.lbl_auto_param)
        a_lay.addWidget(self.spin_auto_val, 1)
        ctrl_lay.addWidget(self.auto_row)

        self.btn_auto_gen = QPushButton("⚡ Auto-Generate Blocks")
        self.btn_auto_gen.setObjectName("ActionBtn")
        self.btn_auto_gen.clicked.connect(self.auto_generate_blocks)
        ctrl_lay.addWidget(self.btn_auto_gen)

        lay.addWidget(self.ctrl_frame)

        # --- QUEUE LIST OF STITCH BLOCKS ---
        self.lbl_queue = QLabel("2. STITCH QUEUE (0 FILES) — Double-click to rename")
        self.lbl_queue.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold; margin-top: 4px;")
        lay.addWidget(self.lbl_queue)

        self.block_list = QListWidget()
        self.block_list.setMinimumHeight(120)
        self.block_list.setStyleSheet(f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; font-size: 11px;")
        self.block_list.itemDoubleClicked.connect(self.rename_selected_block)
        lay.addWidget(self.block_list, 1)

        row_q_btns = QHBoxLayout()
        btn_ren = QPushButton("RENAME")
        btn_ren.setToolTip("Set custom output filename for the selected block")
        btn_ren.clicked.connect(self.rename_selected_block)
        btn_rem = QPushButton("REMOVE")
        btn_rem.clicked.connect(self.remove_selected_block)
        btn_clr = QPushButton("CLEAR")
        btn_clr.clicked.connect(self.clear_blocks)
        row_q_btns.addWidget(btn_ren, 1)
        row_q_btns.addWidget(btn_rem, 1)
        row_q_btns.addWidget(btn_clr, 1)
        lay.addLayout(row_q_btns)

        # --- EXPORT & HEIGHT GUARD SETTINGS ---
        lbl_exp = QLabel("3. OUTPUT & HEIGHT GUARD")
        lbl_exp.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold; margin-top: 4px;")
        lay.addWidget(lbl_exp)

        self.chk_height_guard = QCheckBox("Split if height exceeds limit:")
        self.chk_height_guard.setStyleSheet(f"color: {Config.COLOR_TEXT}; font-size: 10px;")
        self.chk_height_guard.setChecked(False)
        lay.addWidget(self.chk_height_guard)

        row_h = QHBoxLayout()
        lbl_max_h = QLabel("Max Height:")
        lbl_max_h.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.spin_max_h = QSpinBox()
        self.spin_max_h.setRange(512, 4096)
        self.spin_max_h.setSingleStep(512)
        self.spin_max_h.setSuffix(" px")
        self.spin_max_h.setValue(2048)
        btn_sync_tile = QPushButton("Sync Tile")
        btn_sync_tile.setToolTip("Sync Max Height with current Max Tile Size (512px - 4096px)")
        btn_sync_tile.setFixedWidth(68)
        btn_sync_tile.clicked.connect(self.sync_height_from_tile_slider)
        row_h.addWidget(lbl_max_h)
        row_h.addWidget(self.spin_max_h, 1)
        row_h.addWidget(btn_sync_tile)
        lay.addLayout(row_h)

        row_fmt = QHBoxLayout()
        lbl_f = QLabel("Format:")
        lbl_f.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItem(tr("stitcher.png_100_lossless"), "png")
        self.fmt_combo.addItem(tr("stitcher.jpg_100_quality_4_4_4"), "jpg")
        self.fmt_combo.setStyleSheet(f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 4px; font-size: 11px;")
        row_fmt.addWidget(lbl_f)
        row_fmt.addWidget(self.fmt_combo, 1)
        lay.addLayout(row_fmt)

        # Use '&&' so Qt displays literal '&' instead of an underline shortcut
        self.btn_execute_stitch = QPushButton("EXECUTE STITCH && EXPORT")
        self.btn_execute_stitch.setObjectName("PrimaryBtn")
        self.btn_execute_stitch.setFixedHeight(42)
        self.btn_execute_stitch.clicked.connect(self.execute_stitch_export)
        lay.addWidget(self.btn_execute_stitch)

        self.on_mode_changed(0)

    def showEvent(self, event):
        """Automatically refreshes the filename dropdowns whenever the user opens the STITCHER tab."""
        super().showEvent(event)
        self.refresh_file_combos()

    def sync_height_from_tile_slider(self):
        tile_px = self.mw.t_slider.slider.value() * 512
        self.spin_max_h.setValue(max(512, min(4096, tile_px)))
        self.chk_height_guard.setChecked(True)

    def on_mode_changed(self, idx):
        is_manual = (idx == 0)
        self.manual_row.setVisible(is_manual)
        self.btn_add_checked.setVisible(is_manual)
        self.btn_add_range.setVisible(is_manual)
        self.auto_row.setVisible(not is_manual)
        self.btn_auto_gen.setVisible(not is_manual)

        if idx == 1:
            self.lbl_auto_param.setText("Pages per File:")
            self.spin_auto_val.setRange(2, 500)
            self.spin_auto_val.setValue(5)
        elif idx == 2:
            self.lbl_auto_param.setText("Max Output Files:")
            self.spin_auto_val.setRange(1, 5000)
            self.spin_auto_val.setValue(100)

    def _get_ordered_project_paths(self) -> list:
        paths = [self.mw.file_list.item(i).data(Qt.UserRole) for i in range(self.mw.file_list.count())]
        if self.chk_natural_sort.isChecked():
            paths = sorted(paths, key=_natural_sort_key)
        return paths

    def refresh_file_combos(self):
        paths = self._get_ordered_project_paths()
        prev_from = self.combo_from.currentData(Qt.UserRole)
        prev_to = self.combo_to.currentData(Qt.UserRole)

        self.combo_from.blockSignals(True)
        self.combo_to.blockSignals(True)
        self.combo_from.clear()
        self.combo_to.clear()

        for idx, p in enumerate(paths, start=1):
            label = f"{idx:03d}. {os.path.basename(p)}"
            self.combo_from.addItem(label, p)
            self.combo_to.addItem(label, p)

        if paths:
            from_idx = self.combo_from.findData(prev_from, Qt.UserRole)
            to_idx = self.combo_to.findData(prev_to, Qt.UserRole)
            self.combo_from.setCurrentIndex(max(0, from_idx))
            if to_idx >= 0:
                self.combo_to.setCurrentIndex(to_idx)
            else:
                self.combo_to.setCurrentIndex(min(len(paths) - 1, 9))

        self.combo_from.blockSignals(False)
        self.combo_to.blockSignals(False)

    def _next_default_block_name(self) -> str:
        return f"stitched_{len(self.stitch_blocks) + 1:03d}"

    def _refresh_queue_ui(self):
        self.block_list.clear()
        total_outputs = len(self.stitch_blocks)
        self.lbl_queue.setText(f"2. STITCH QUEUE ({total_outputs} FILES) — Double-click to rename")

        for block in self.stitch_blocks:
            out_name = block["name"]
            paths = block["paths"]
            names = [os.path.basename(p) for p in paths]
            if len(names) == 1:
                desc = f"{names[0]} (1 page)"
            else:
                desc = f"{names[0]} .. {names[-1]} ({len(names)} pages)"
            item = QListWidgetItem(f"{out_name}  ⟵  [{desc}]")
            item.setToolTip("Double-click to set a custom output filename for this stitched block")
            self.block_list.addItem(item)

    def add_checked_as_block(self):
        checked_paths = []
        for i in range(self.mw.file_list.count()):
            it = self.mw.file_list.item(i)
            if it.checkState() == Qt.Checked:
                checked_paths.append(it.data(Qt.UserRole))
                it.setCheckState(Qt.Unchecked)

        if not checked_paths:
            QMessageBox.information(
                self, "No Checked Pages",
                "Check the pages you want to combine in the left Project Assets list first."
            )
            return

        if self.chk_natural_sort.isChecked():
            checked_paths = sorted(checked_paths, key=_natural_sort_key)

        self.mw.chk_all.blockSignals(True)
        self.mw.chk_all.setChecked(False)
        self.mw.chk_all.blockSignals(False)

        self.stitch_blocks.append({
            "name": self._next_default_block_name(),
            "paths": checked_paths
        })
        self._refresh_queue_ui()

    def add_range_as_block(self):
        all_paths = self._get_ordered_project_paths()
        if not all_paths:
            QMessageBox.information(self, "Empty Project", "Import a folder of images first.")
            return

        if self.combo_from.count() != len(all_paths):
            self.refresh_file_combos()

        start_idx = self.combo_from.currentIndex()
        end_idx = self.combo_to.currentIndex()

        if start_idx < 0 or end_idx < 0 or start_idx > end_idx:
            QMessageBox.warning(
                self, "Invalid File Range",
                "Please select a 'From' file that comes before or equals the 'To' file."
            )
            return

        block_paths = all_paths[start_idx:end_idx + 1]
        self.stitch_blocks.append({
            "name": self._next_default_block_name(),
            "paths": block_paths
        })
        self._refresh_queue_ui()

        # Advance file dropdowns conveniently for the next block!
        span = max(1, (end_idx - start_idx) + 1)
        next_start = end_idx + 1
        if next_start < len(all_paths):
            self.combo_from.setCurrentIndex(next_start)
            self.combo_to.setCurrentIndex(min(len(all_paths) - 1, next_start + span - 1))

    def auto_generate_blocks(self):
        all_paths = self._get_ordered_project_paths()
        total = len(all_paths)
        if total == 0:
            QMessageBox.information(self, "Empty Project", "Import a folder of images first.")
            return

        self.stitch_blocks.clear()
        mode_idx = self.mode_combo.currentIndex()
        val = self.spin_auto_val.value()

        if mode_idx == 1:
            # Fixed N pages per output file
            chunk_size = max(1, val)
            for i in range(0, total, chunk_size):
                self.stitch_blocks.append({
                    "name": self._next_default_block_name(),
                    "paths": all_paths[i:i + chunk_size]
                })

        elif mode_idx == 2:
            # Fit total pages into at most `val` output files (e.g. 150 pages -> 100 files)
            target_files = max(1, min(total, val))
            base_size = total // target_files
            remainder = total % target_files
            idx = 0
            for i in range(target_files):
                step = base_size + (1 if i < remainder else 0)
                self.stitch_blocks.append({
                    "name": self._next_default_block_name(),
                    "paths": all_paths[idx:idx + step]
                })
                idx += step

        self._refresh_queue_ui()

    def rename_selected_block(self):
        row = self.block_list.currentRow()
        if not (0 <= row < len(self.stitch_blocks)):
            return

        curr_name = self.stitch_blocks[row]["name"]
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Stitched Output File",
            "Enter custom output filename (without extension):",
            QLineEdit.Normal,
            curr_name
        )
        if ok and new_name.strip():
            # Sanitize illegal filename characters
            clean_name = re.sub(r'[\\/*?:"<>|]', "_", new_name.strip())
            clean_name = os.path.splitext(clean_name)[0] or curr_name
            self.stitch_blocks[row]["name"] = clean_name
            self._refresh_queue_ui()
            self.block_list.setCurrentRow(row)

    def remove_selected_block(self):
        row = self.block_list.currentRow()
        if 0 <= row < len(self.stitch_blocks):
            self.stitch_blocks.pop(row)
            self._refresh_queue_ui()

    def clear_blocks(self):
        self.stitch_blocks.clear()
        self._refresh_queue_ui()
        self.refresh_file_combos()

    def _load_or_get_session_image(self, path: str) -> np.ndarray:
        """
        Fetches the latest cleaned + typesetted image from Studio RAM if modified/loaded,
        or decodes it losslessly from disk if untouched.
        """
        if path == self.mw.current_img_path and self.mw.canvas.cv_img is not None:
            return self.mw.canvas.get_composited_image()

        if path in self.mw.image_sessions:
            return self.mw._get_final_img_for_path(path)

        img_data = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(img_data, cv2.IMREAD_UNCHANGED)
        if img is not None:
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            elif len(img.shape) == 3 and img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img

    def execute_stitch_export(self):
        if not self.stitch_blocks:
            QMessageBox.information(
                self,
                "Queue Empty",
                "Add at least one block to the Stitch Queue (or click 'Auto-Generate Blocks') before exporting."
            )
            return

        # Warn if any page inside the queued blocks still has unplaced [ + ] dialogues
        all_target_paths = [p for block in self.stitch_blocks for p in block["paths"]]
        if hasattr(self.mw, "_confirm_unplaced_texts") and not self.mw._confirm_unplaced_texts(all_target_paths):
            return

        # Save current active canvas session first so latest edits/texts are included
        if self.mw.current_img_path and self.mw.canvas.cv_img is not None:
            self.mw.image_sessions[self.mw.current_img_path] = {
                "img": self.mw.canvas.cv_img.copy(),
                "mask": self.mw.canvas.mask.copy(),
                "history": self.mw.history,
                "texts": self.mw.canvas.get_texts_data()
            }

        out_dir = QFileDialog.getExistingDirectory(self, "Select Output Folder for Stitched Images")
        if not out_dir:
            return

        fmt = self.fmt_combo.currentData()
        max_h = self.spin_max_h.value() if self.chk_height_guard.isChecked() else 0

        progress = QProgressDialog("Stitching blocks losslessly...", "Cancel", 0, len(self.stitch_blocks), self)
        progress.setWindowTitle("Lossless Stitcher")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        saved_count = 0

        try:
            for b_idx, block in enumerate(self.stitch_blocks):
                progress.setValue(b_idx)
                QCoreApplication.processEvents()
                if progress.wasCanceled():
                    break

                base_name = block["name"]
                block_paths = block["paths"]

                raw_imgs = []
                valid_paths = []
                for p in block_paths:
                    img = self._load_or_get_session_image(p)
                    if img is not None:
                        raw_imgs.append(img)
                        valid_paths.append(p)

                if not raw_imgs:
                    continue

                aligned_imgs = StitchEngine.align_widths_and_channels(raw_imgs)
                sub_blocks = StitchEngine.split_by_max_height(aligned_imgs, valid_paths, max_h)

                for part_idx, (sub_imgs, _) in enumerate(sub_blocks, start=1):
                    stitched = np.vstack(sub_imgs) if len(sub_imgs) > 1 else sub_imgs[0]
                    if len(sub_blocks) > 1:
                        out_name = f"{base_name}_part{part_idx:02d}.{fmt}"
                    else:
                        out_name = f"{base_name}.{fmt}"
                    out_path = os.path.join(out_dir, out_name)
                    if StitchEngine.save_lossless(stitched, out_path, fmt):
                        saved_count += 1

            progress.setValue(len(self.stitch_blocks))
            logger.info(f"[STITCHER] Successfully exported {saved_count} stitched files to {out_dir}")
            QMessageBox.information(
                self,
                "Stitch Complete",
                f"Successfully exported {saved_count} lossless stitched files to:\n{out_dir}"
            )
        except Exception as e:
            logger.error(f"[STITCHER] Error during stitch export: {e}")
            QMessageBox.critical(self, "Stitcher Error", f"An error occurred while stitching:\n{e}")