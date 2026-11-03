import os
import gc
from src.backend.onnx_engine import ONNXEngine
from src.utils.paths import Paths
from src.utils.logger import logger

#/////////////////////////////////#
#     AI MODEL RESOURCE MGMT      #
#/////////////////////////////////#

class AIManager:
    _ocr_engine = None
    _lama_engine = None

    @staticmethod
    def set_persistence(enabled: bool):
        if not enabled:
            AIManager.flush()

    @staticmethod
    def get_ocr():
        if AIManager._ocr_engine is None:
            path = Paths.get_model("ocr.onnx")
            if os.path.exists(path):
                logger.info(f"[+] Lazy loading OCR model into VRAM: {path}")
                AIManager._ocr_engine = ONNXEngine(path)
            else:
                raise FileNotFoundError(f"OCR model is missing: {path}")
        return AIManager._ocr_engine

    @staticmethod
    def get_lama():
        if AIManager._lama_engine is None:
            path = Paths.get_model("lama.onnx")
            if os.path.exists(path):
                logger.info(f"[+] Lazy loading LaMa model into VRAM: {path}")
                AIManager._lama_engine = ONNXEngine(path)
            else:
                raise FileNotFoundError(f"LaMa model is missing: {path}")
        return AIManager._lama_engine

    @staticmethod
    def flush():
        AIManager._ocr_engine = None
        AIManager._lama_engine = None
        gc.collect()
        logger.info("[i] VRAM Flushed: Model Memory Released")
