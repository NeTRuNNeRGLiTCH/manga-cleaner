import cv2
import time
import numpy as np
import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor
from PySide6.QtCore import QObject, Signal, Slot
from src.backend.processor import ImageProcessor
from src.utils.logger import logger

# Keep a single background process alive so models stay in VRAM
_pool = None
_progress_manager = None
_progress_manager_lock = threading.Lock()


def get_pool():
    global _pool
    if _pool is None:
        logger.info("[+] Initializing new ProcessPoolExecutor for background AI tasks.")
        _pool = ProcessPoolExecutor(max_workers=1)
    return _pool


def get_progress_manager():
    """Lazily create one manager for progress queues used by LaMa tasks."""
    global _progress_manager
    if _progress_manager is None:
        with _progress_manager_lock:
            if _progress_manager is None:
                logger.info("[+] Initializing shared progress queue manager.")
                _progress_manager = multiprocessing.Manager()
    return _progress_manager

# Top-level functions so Windows can send them to the background process
def _run_ocr_process(cv_img, language):
    return ImageProcessor.run_ocr_logic(cv_img, language)

def _run_clean_process(cv_img, mask_img, max_tile_w, queue):
    def cb(prog):
        queue.put(prog)
    return ImageProcessor.run_clean_logic(cv_img, mask_img, max_tile_w, progress_callback=cb)

def _run_flush_process(persistent):
    from src.backend.ai_manager import AIManager
    AIManager.set_persistence(persistent)
    if not persistent:
        AIManager.flush()
    return True

#/////////////////////////////////#
#     AI ASYNC TASK WORKER        #
#/////////////////////////////////#

class AIWorker(QObject):
    finished = Signal(object, object)
    progress = Signal(int)
    error = Signal(str)

    def __init__(self, task=None, args=None):
        super().__init__()
        self.task = task
        self.args = args
        logger.info(f"[i] AIWorker initialized for task: {self.task}")

    @Slot()
    def process(self):
        if self.task == "ocr":
            self.run_ocr(self.args[0], "ENG")
        elif self.task == "clean":
            self.run_clean(self.args[0], self.args[1], self.args[2])
        elif self.task == "transparency":
            self.run_transparency(self.args[0])

    def run_ocr(self, cv_img, language):
        try:
            logger.info("[i] Submitting OCR task to background OS process...")
            future = get_pool().submit(_run_ocr_process, cv_img, language)
            
            # Poll the background process without blocking the GUI
            while not future.done():
                time.sleep(0.05)
                
            logger.info("[+] OCR background task completed successfully.")
            self.finished.emit(future.result(), None)
        except Exception as e:
            logger.error(f"[X] OCR Task crashed in background process: {e}")
            self.error.emit(str(e))

    def run_clean(self, cv_img, mask_img, max_tile_w):
        try:
            logger.info("[i] Submitting LaMa Clean task to background OS process...")
            # Only LaMa cleanup reports progress through a manager-backed queue.
            # Reuse one lazily started manager instead of starting a helper
            # process for every AIWorker (including OCR and transparency scans).
            progress_queue = get_progress_manager().Queue()
            future = get_pool().submit(
                _run_clean_process, cv_img, mask_img, max_tile_w, progress_queue
            )

            # Poll the background process and update UI progress.
            while not future.done():
                while not progress_queue.empty():
                    self.progress.emit(progress_queue.get())
                time.sleep(0.05)

            res = future.result()
            while not progress_queue.empty():
                self.progress.emit(progress_queue.get())

            logger.info("[+] LaMa Clean background task completed successfully.")
            self.finished.emit(res[0], res[1])
        except Exception as e:
            logger.error(f"[X] LaMa Clean Task crashed in background process: {e}")
            self.error.emit(str(e))

    def run_transparency(self, cv_img):
        try:
            logger.info("[i] Executing Transparency scan in QThread...")

            if cv_img is not None and len(cv_img.shape) == 3 and cv_img.shape[2] == 4:
                # Grab EVERYTHING that isn't 100% solid opaque (catches the soft fringes)
                mask = (cv_img[:, :, 3] < 255).astype(np.uint8) * 255
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                mask = cv2.dilate(mask, kernel, iterations=1)
            else:
                h, w = cv_img.shape[:2] if cv_img is not None else (100, 100)
                mask = np.zeros((h, w), dtype=np.uint8)

            logger.info("[+] Transparency scan completed.")
            self.finished.emit(mask, None)

        except Exception as e:
            logger.error(f"[X] Transparency Task crashed: {e}")
            self.error.emit(str(e))
