import torch
import easyocr
from simple_lama_inpainting import SimpleLama
from typing import List

#////////////////////////#
#   MODEL RESOURCE MGMT  #
#////////////////////////#

class AIManager:
    _ocr_reader = None
    _lama_model = None
    _current_langs = []

    @staticmethod
    def get_ocr(langs: List[str] = ['en']):
        if AIManager._ocr_reader is None or set(langs) != set(AIManager._current_langs):
            AIManager._ocr_reader = easyocr.Reader(langs, gpu=torch.cuda.is_available())
            AIManager._current_langs = langs
        return AIManager._ocr_reader

    @staticmethod
    def get_lama():
        if AIManager._lama_model is None:
            AIManager._lama_model = SimpleLama()
        return AIManager._lama_model
    
    @staticmethod
    def flush_vram():
        if torch.cuda.is_available():
            torch.cuda.empty_cache()