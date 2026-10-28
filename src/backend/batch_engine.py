import os
import cv2
from PySide6.QtCore import QObject, Signal
from src.utils.config import Config
from src.utils.paths import Paths
from src.utils.logger import logger

#/////////////////////////////////#
#    BATCH PROCESSING CONTROLLER  #
#/////////////////////////////////#

class BatchEngine(QObject):
    page_started = Signal(str, int)

    def __init__(self):
        super().__init__()
        self.files = []
        self.current_index = 0
        self.output_dir = ""
        self.export_format = "jpg"

    def initialize_batch(self, file_paths, export_format):
        self.files = file_paths
        self.export_format = (export_format or "").strip().lower()
        self.current_index = 0

        if self.export_format and self.export_format != "none":
            batch_id = Config.get_next_batch_id()
            self.output_dir = os.path.join(Paths.PROCESSED, batch_id)
            os.makedirs(self.output_dir, exist_ok=True)
        else:
            self.output_dir = ""
            
        logger.info(f"Batch Engine Ready: {self.output_dir or 'memory only (no export)'}")
        return self.output_dir

    def get_next(self):
        if self.current_index < len(self.files):
            path = self.files[self.current_index]
            self.page_started.emit(path, self.current_index)
            return path
        return None

    def save_current(self, cv_img):
        if not self.export_format or self.export_format == "none":
            logger.info("[+] Page processed and kept in session memory.")
            self.current_index += 1
            return self.current_index >= len(self.files)

        ext = self.export_format if self.export_format not in ["photoshop", "photopea"] else "png"
        orig_name = os.path.splitext(os.path.basename(self.files[self.current_index]))[0]
        filename = f"{orig_name}_cleaned.{ext}"
        save_path = os.path.join(self.output_dir, filename)
        
        # Handle alpha channel conversions on export
        if len(cv_img.shape) == 3 and cv_img.shape[2] == 4:
            out_bgr = cv2.cvtColor(cv_img, cv2.COLOR_RGBA2BGRA)
            if ext.lower() in ['jpg', 'jpeg']:
                out_bgr = cv2.cvtColor(out_bgr, cv2.COLOR_BGRA2BGR)
        else:
            out_bgr = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)

        cv2.imwrite(save_path, out_bgr)
        
        logger.info(f"[+] Successfully Saved Cleaned: {filename}")
        self.current_index += 1
        return self.current_index >= len(self.files)
