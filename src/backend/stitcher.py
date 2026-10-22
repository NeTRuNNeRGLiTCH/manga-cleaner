import os
import math
import cv2
import numpy as np
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QComboBox, QSpinBox, 
                             QListWidget, QListWidgetItem, QFileDialog, 
                             QMessageBox, QCheckBox, QProgressDialog)
from PySide6.QtCore import Qt, QCoreApplication
from src.utils.config import Config
from src.utils.paths import Paths
from src.utils.logger import logger

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
            params = [int(cv2.IMWRITE_JPEG_QUALITY), 100, int(cv2.IMWRITE_JPEG_SAMPLING_FACTOR), int(cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444)]
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
        self.stitch_blocks = []  # List of lists: [[path1, path2, ...], [path3, path4, ...]]
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

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Manual Blocks (Checked / Range)",
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

        # Row for Manual Range (e.g. Page 1 to Page 10)
        self.manual_row = QWidget()
        m_lay = QHBoxLayout(self.manual_row)
        m_lay.setContentsMargins(0, 0, 0, 0)
        lbl_from = QLabel("From #:")
        lbl_from.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.spin_from = QSpinBox()
        self.spin_from.setRange(1, 9999)
        self.spin_from.setValue(1)

        lbl_to = QLabel("To #:")
        lbl_to.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.spin_to = QSpinBox()
        self.spin_to.setRange(1, 9999)
        self.spin_to.setValue(10)

        m_lay.addWidget(lbl_from)
        m_lay.addWidget(self.spin_from, 1)
        m_lay.addWidget(lbl_to)
        m_lay.addWidget(self.spin_to, 1)
        ctrl_lay.addWidget(self.manual_row)

        self.btn_add_checked = QPushButton("+ Add Checked Files as Block")
        self.btn_add_checked.setToolTip("Groups all currently checked files in Project Assets into one stitched output")
        self.btn_add_checked.clicked.connect(self.add_checked_as_block)
        ctrl_lay.addWidget(self.btn_add_checked)

        self.btn_add_range = QPushButton("+ Add Range (From -> To) as Block")
        self.btn_add_range.clicked.connect(self.add_range_as_block)
        ctrl_lay.addWidget(self.btn_add_range)

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
        self.lbl_queue = QLabel("2. STITCH QUEUE (0 OUTPUT FILES)")
        self.lbl_queue.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 9px; font-weight: bold; margin-top: 4px;")
        lay.addWidget(self.lbl_queue)

        self.block_list = QListWidget()
        self.block_list.setMinimumHeight(130)
        self.block_list.setStyleSheet(f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; font-size: 11px;")
        lay.addWidget(self.block_list, 1)

        row_q_btns = QHBoxLayout()
        btn_rem = QPushButton("REMOVE BLOCK")
        btn_rem.clicked.connect(self.remove_selected_block)
        btn_clr = QPushButton("CLEAR QUEUE")
        btn_clr.clicked.connect(self.clear_blocks)
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
        self.spin_max_h.setRange(2048, 65000)
        self.spin_max_h.setSingleStep(2048)
        self.spin_max_h.setSuffix(" px")
        self.spin_max_h.setValue(2048)  # Default
        btn_sync_tile = QPushButton("Use Tile x4")
        btn_sync_tile.setToolTip("Set Max Height to 4x current Max Tile Size slider")
        btn_sync_tile.setFixedWidth(72)
        btn_sync_tile.clicked.connect(self.sync_height_from_tile_slider)
        row_h.addWidget(lbl_max_h)
        row_h.addWidget(self.spin_max_h, 1)
        row_h.addWidget(btn_sync_tile)
        lay.addLayout(row_h)

        row_fmt = QHBoxLayout()
        lbl_f = QLabel("Format:")
        lbl_f.setStyleSheet(f"color: {Config.COLOR_TEXT_DIM}; font-size: 10px;")
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["PNG (100% Lossless)", "JPG (100% Quality 4:4:4)"])
        self.fmt_combo.setStyleSheet(f"background: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 4px; font-size: 11px;")
        row_fmt.addWidget(lbl_f)
        row_fmt.addWidget(self.fmt_combo, 1)
        lay.addLayout(row_fmt)

        self.btn_execute_stitch = QPushButton("EXECUTE STITCH & EXPORT")
        self.btn_execute_stitch.setObjectName("PrimaryBtn")
        self.btn_execute_stitch.setFixedHeight(42)
        self.btn_execute_stitch.clicked.connect(self.execute_stitch_export)
        lay.addWidget(self.btn_execute_stitch)

        self.on_mode_changed(0)

    def sync_height_from_tile_slider(self):
        tile_px = self.mw.t_slider.slider.value() * 512
        self.spin_max_h.setValue(min(65000, tile_px * 4))
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

    def _get_all_project_paths(self) -> list:
        return [self.mw.file_list.item(i).data(Qt.UserRole) for i in range(self.mw.file_list.count())]

    def _refresh_queue_ui(self):
        self.block_list.clear()
        total_outputs = len(self.stitch_blocks)
        self.lbl_queue.setText(f"2. STITCH QUEUE ({total_outputs} OUTPUT FILES)")

        for idx, block in enumerate(self.stitch_blocks, start=1):
            names = [os.path.basename(p) for p in block]
            if len(names) == 1:
                desc = f"{names[0]} (1 page)"
            else:
                desc = f"{names[0]} .. {names[-1]} ({len(names)} pages)"
            item = QListWidgetItem(f"Out_{idx:03d}  ⟵  [{desc}]")
            self.block_list.addItem(item)

    def add_checked_as_block(self):
        checked_paths = []
        for i in range(self.mw.file_list.count()):
            it = self.mw.file_list.item(i)
            if it.checkState() == Qt.Checked:
                checked_paths.append(it.data(Qt.UserRole))
                it.setCheckState(Qt.Unchecked)

        if not checked_paths:
            QMessageBox.information(self, "No Checked Pages", "Check the pages you want to combine in the left Project Assets list first.")
            return

        self.mw.chk_all.blockSignals(True)
        self.mw.chk_all.setChecked(False)
        self.mw.chk_all.blockSignals(False)

        self.stitch_blocks.append(checked_paths)
        self._refresh_queue_ui()

    def add_range_as_block(self):
        all_paths = self._get_all_project_paths()
        if not all_paths:
            QMessageBox.information(self, "Empty Project", "Import a folder of images first.")
            return

        start_idx = max(1, self.spin_from.value()) - 1
        end_idx = min(len(all_paths), self.spin_to.value())

        if start_idx >= len(all_paths) or start_idx >= end_idx:
            QMessageBox.warning(self, "Invalid Range", f"Please select a valid page range between 1 and {len(all_paths)}.")
            return

        block = all_paths[start_idx:end_idx]
        self.stitch_blocks.append(block)
        self._refresh_queue_ui()

        # Advance range spinboxes conveniently for the next block!
        next_from = end_idx + 1
        span = max(1, end_idx - start_idx)
        if next_from <= len(all_paths):
            self.spin_from.setValue(next_from)
            self.spin_to.setValue(min(len(all_paths), next_from + span - 1))

    def auto_generate_blocks(self):
        all_paths = self._get_all_project_paths()
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
                self.stitch_blocks.append(all_paths[i:i + chunk_size])

        elif mode_idx == 2:
            # Fit total pages into at most `val` output files (e.g. 150 pages -> 100 files)
            target_files = max(1, min(total, val))
            base_size = total // target_files
            remainder = total % target_files
            idx = 0
            for i in range(target_files):
                step = base_size + (1 if i < remainder else 0)
                self.stitch_blocks.append(all_paths[idx:idx + step])
                idx += step

        self._refresh_queue_ui()

    def remove_selected_block(self):
        row = self.block_list.currentRow()
        if 0 <= row < len(self.stitch_blocks):
            self.stitch_blocks.pop(row)
            self._refresh_queue_ui()

    def clear_blocks(self):
        self.stitch_blocks.clear()
        self._refresh_queue_ui()

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
            all_target_paths = [p for block in self.stitch_blocks for p in block]
        if hasattr(self.mw, "_confirm_unplaced_texts") and not self.mw._confirm_unplaced_texts(all_target_paths):
            return
            QMessageBox.information(
                self,
                "Queue Empty",
                "Add at least one block to the Stitch Queue (or click 'Auto-Generate Blocks') before exporting."
            )
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

        fmt = "png" if "PNG" in self.fmt_combo.currentText() else "jpg"
        max_h = self.spin_max_h.value() if self.chk_height_guard.isChecked() else 0

        progress = QProgressDialog("Stitching blocks losslessly...", "Cancel", 0, len(self.stitch_blocks), self)
        progress.setWindowTitle("Lossless Stitcher")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        saved_count = 0
        out_index = 1

        try:
            for b_idx, block_paths in enumerate(self.stitch_blocks):
                progress.setValue(b_idx)
                QCoreApplication.processEvents()
                if progress.wasCanceled():
                    break

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

                for sub_imgs, _ in sub_blocks:
                    stitched = np.vstack(sub_imgs) if len(sub_imgs) > 1 else sub_imgs[0]
                    out_name = f"stitched_{out_index:03d}.{fmt}"
                    out_path = os.path.join(out_dir, out_name)
                    if StitchEngine.save_lossless(stitched, out_path, fmt):
                        saved_count += 1
                        out_index += 1

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