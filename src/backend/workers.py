from PySide6.QtCore import QObject, Signal, Slot
import numpy as np
from typing import List, Optional, Tuple
from src.backend.processor import ImageProcessor

#////////////////////////#
#  AI INFERENCE WORKER   #
#////////////////////////#

class AIWorker(QObject):
    finished = Signal(object, object)
    error = Signal(str)

    @Slot(object, list)
    def run_ocr(self, cv_img: np.ndarray, langs: List[str]) -> None:
        try:
            #////////////////////////#
            #   ASYNC OCR EXECUTION  #
            #////////////////////////#
            mask = ImageProcessor.run_ocr_logic(cv_img, langs)
            self.finished.emit(mask, None)
        except Exception as e:
            self.error.emit(str(e))

    @Slot(object, object, int)
    def run_clean(self, cv_img: np.ndarray, mask_img: np.ndarray, num_tiles: int) -> None:
        try:
            #////////////////////////#
            #  ASYNC TILING EXECUTION#
            #////////////////////////#
            result, patches = ImageProcessor.run_clean_logic(cv_img, mask_img, num_tiles)
            self.finished.emit(result, patches)
        except Exception as e:
            self.error.emit(str(e))