"""In-memory project reset controller for Manga Cleaner Studio.

Place this module at: src/frontend/project_reset.py
The MainWindow integration is intentionally kept to one import and a small button hookup.
"""

from __future__ import annotations

import ctypes
import gc
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainterPath, QPixmap
from PySide6.QtWidgets import QMessageBox

from src.utils.config import Config
from src.utils.history import HistoryManager
from src.utils.logger import logger


class ProjectResetController:
    """Clear project-specific data while keeping the application window open."""

    @staticmethod
    def reset(main_window) -> bool:
        """Ask for confirmation, clear project state, and return whether it reset."""
        mw = main_window

        # Do not reset while the worker, a batch, or queued work can still reference
        # the current project. The caller can try again after processing finishes.
        if (
            getattr(mw, "worker_thread", None) is not None
            or getattr(mw, "is_batching", False)
            or bool(getattr(mw, "task_queue", []))
        ):
            QMessageBox.warning(
                mw,
                "Studio Busy",
                "Cannot reset the project while an AI task or batch process is active.\n\n"
                "Wait for processing to finish, then try again.",
            )
            return False

        stitcher = getattr(mw, "stitcher_page", None)
        translator = getattr(mw, "translator_page", None)
        canvas = mw.canvas

        has_project_data = bool(
            mw.file_list.count()
            or getattr(mw, "current_img_path", None)
            or getattr(mw, "image_sessions", {})
            or getattr(mw, "pending_page_texts", {})
            or getattr(stitcher, "stitch_blocks", [])
            or getattr(translator, "loaded_script_path", None)
            or getattr(translator, "parsed_entries", [])
        )
        if not has_project_data and canvas.cv_img is None:
            return False

        answer = QMessageBox.question(
            mw,
            "Reset Project",
            "Clear the current project from memory?\n\n"
            "This removes loaded pages, masks, text layers, pending dialogues, histories, "
            "and Stitcher/Translator project data. Original image files and saved font "
            "preferences will not be deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return False

        # Important: clear the active path before canvas signals can refresh the
        # page-text list; otherwise they could reinsert the old page into the queue.
        mw.current_img_path = None

        # Drop all per-page references and history stacks.
        mw.image_sessions.clear()
        mw.pending_page_texts.clear()
        mw.page_states.clear()
        mw.task_queue.clear()
        mw.history = HistoryManager(Config.MAX_HISTORY)
        mw.batch_scan_type = "ocr"
        mw.is_batching = False
        mw.total_tasks = 0
        mw.completed_tasks = 0
        mw.total_lama_tasks = 0
        mw.completed_lama_tasks = 0

        # Reset batch-engine metadata without replacing its QObject/signals.
        batch = getattr(mw, "batch_engine", None)
        if batch is not None:
            batch.files.clear()
            batch.current_index = 0
            batch.output_dir = ""
            batch.export_format = "jpg"

        # Clear Project Assets selection/list.
        if hasattr(mw, "chk_all"):
            mw.chk_all.blockSignals(True)
            mw.chk_all.setChecked(False)
            mw.chk_all.blockSignals(False)
        mw.file_list.clear()

        # Clear the canvas without emitting page/text signals while its data is
        # being dismantled. QImage()/QPixmap() detach the large pixel buffers.
        canvas.blockSignals(True)
        try:
            canvas.clear_texts()
            canvas.cv_img = None
            canvas.mask = QImage()
            canvas.image_item.setPixmap(QPixmap())
            canvas.mask_item.setPixmap(QPixmap())
            canvas.preview_item.setPath(QPainterPath())
            canvas.scene.clearSelection()
            canvas.scene.setSceneRect(0, 0, 0, 0)
            canvas.resetTransform()

            canvas.poly_points.clear()
            canvas.last_pt = None
            canvas.last_drawn_pt = None
            canvas._stroke_pre_img = None
            canvas.is_drawing = False
            canvas.is_resizing_brush = False
            canvas.resize_start_pos = None
            canvas.resize_start_cursor_pos = None
            canvas._active_gizmo_item = None
            canvas._active_gizmo_mode = None
            canvas.lasso_path = QPainterPath()
            canvas.cursor_item.hide()
            canvas.set_locked(False)
        finally:
            canvas.blockSignals(False)

        # Drop the completed worker's retained NumPy arguments and its Manager.
        # The worker thread is already finished (checked above), so it is safe to
        # release these references without interrupting an inference task.
        worker = getattr(mw, "worker", None)
        if worker is not None:
            try:
                worker.args = None
                manager = getattr(worker, "manager", None)
                if manager is not None:
                    manager.shutdown()
                    worker.manager = None
            except Exception as exc:
                logger.warning(f"[RESET] Could not fully release the previous worker: {exc}")
            mw.worker = None

        # Reset category/tool state to the same initial workspace, but preserve
        # user preferences such as the selected font and slider settings.
        mw.last_cleaner_tool = "BRUSH"
        mw.is_alt_erasing = False
        mw.is_alt_brushing = False
        mw.is_space_moving = False
        mw.pre_space_tool = "NONE"
        mw.set_category("CLEANER")

        # Clear Stitcher and Translator's project-level data and visible lists.
        if stitcher is not None:
            stitcher.clear_blocks()
        if translator is not None:
            translator.loaded_script_path = None
            translator.parsed_entries.clear()
            translator.path_dialogues_map.clear()
            translator.lbl_script_status.setText("Loaded Script: None")
            translator.refresh_active_page_preview()

        mw.refresh_page_text_list()
        mw.progress_bar.setValue(0)
        mw._update_queue_ui()
        mw.setCursor(Qt.ArrowCursor)

        # Python-side memory reclamation. On glibc Linux, malloc_trim may return
        # free heap pages to the OS; it is optional and intentionally best-effort.
        gc.collect()
        ProjectResetController._trim_linux_heap()

        # Flush cached ONNX sessions in the already-existing AI child process only.
        # Do NOT call get_pool() here: that would start a new process just to reset.
        ProjectResetController._flush_existing_ai_pool()
        gc.collect()

        try:
            mw.update_telemetry()
        except Exception as exc:
            logger.debug(f"[RESET] Telemetry refresh skipped: {exc}")

        logger.info("[STUDIO] Project reset complete; project-specific in-memory state cleared.")
        QMessageBox.information(
            mw,
            "Project Reset Complete",
            "The studio is ready for a new project.\n\n"
            "Memory usage should decrease as resources are released, although the operating "
            "system and native libraries may retain some reserved memory.",
        )
        return True

    @staticmethod
    def _flush_existing_ai_pool() -> None:
        """Flush ONNX model caches only if the background pool already exists."""
        try:
            import src.backend.workers as workers

            pool = getattr(workers, "_pool", None)
            if pool is None:
                return

            # ProcessPoolExecutor exposes submit(), not multiprocessing.Pool.apply().
            pool.submit(workers._run_flush_process, False).result(timeout=15)
            # Restore the normal persistent-model setting for the next task.
            pool.submit(workers._run_flush_process, True).result(timeout=15)
            logger.info("[RESET] Existing AI worker model cache flushed.")
        except Exception as exc:
            # Resetting the project should still succeed if model cleanup fails.
            logger.warning(f"[RESET] AI model cache could not be fully flushed: {exc}")

    @staticmethod
    def _trim_linux_heap() -> None:
        """Best-effort glibc heap trim; unavailable on Windows and some Linux builds."""
        if not sys.platform.startswith("linux"):
            return
        try:
            libc = ctypes.CDLL("libc.so.6")
            trim = getattr(libc, "malloc_trim", None)
            if trim is not None:
                trim.argtypes = [ctypes.c_size_t]
                trim.restype = ctypes.c_int
                trim(0)
        except (OSError, AttributeError):
            pass
