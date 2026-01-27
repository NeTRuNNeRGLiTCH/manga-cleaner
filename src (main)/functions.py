import cv2
import torch
import numpy as np
import os
import gc
import psutil
import easyocr
import logging
from typing import List, Tuple, Optional
from PIL import Image
from simple_lama_inpainting import SimpleLama

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TitanFunctions")

_OCR_CACHE = {}

def get_device() -> str:
    """Returns the best available compute device."""
    return "cuda" if torch.cuda.is_available() else "cpu"

def initialize_lama() -> SimpleLama:
    """Initializes the LaMa inpainting model."""
    return SimpleLama()

def get_ocr_reader(lang: str = 'en') -> easyocr.Reader:
    """
    Returns a cached OCR reader or creates a new one if it doesn't exist.
    Prevents memory bloat from repeated initializations.
    """
    global _OCR_CACHE
    langs = ['en']
    if lang != 'en':
        langs.append(lang)
    
    cache_key = tuple(sorted(langs))
    if cache_key not in _OCR_CACHE:
        logger.info(f"Initializing OCR Reader for: {langs}")
        _OCR_CACHE[cache_key] = easyocr.Reader(langs, gpu=torch.cuda.is_available())
    return _OCR_CACHE[cache_key]

def is_strict_language_match(text: str, target_lang: str) -> bool:
    """Checks if text contains characters from the target language."""
    if not text.strip():
        return False
        
    has_korean = any(0xAC00 <= ord(c) <= 0xD7AF for c in text)
    has_japanese = any(0x3040 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF for c in text)
    has_latin = any(c.isalpha() for c in text)

    if target_lang == "ko": return has_korean
    if target_lang == "ja": return has_japanese
    if target_lang == "en": return has_latin and not (has_korean or has_japanese)
    return True

def run_pro_scan(cv_img: np.ndarray, lang: str) -> np.ndarray:
    """
    Advanced text detection logic.
    - Captures text boxes.
    - Detects 'glow' using HSV saturation.
    - Fills hollow centers via contour analysis.
    """
    reader = get_ocr_reader(lang)
    h, w = cv_img.shape[:2]
    full_mask = np.zeros((h, w), dtype=np.uint8)
    
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    
    chunk_h = 2000
    for y in range(0, h, chunk_h):
        y_end = min(y + chunk_h, h)
        results = reader.readtext(cv_img[y:y_end, :])
        
        for (bbox, text, prob) in results:
            if not is_strict_language_match(text, lang) and prob < 0.3:
                continue
            
            pts = np.array(bbox, np.int32)
            rect_mask = np.zeros((y_end - y, w), dtype=np.uint8)
            cv2.fillPoly(rect_mask, [pts], 255)
            
            roi_gray = gray[y:y_end, :]
            roi_sat = sat[y:y_end, :]
            
            _, m_ink = cv2.threshold(roi_gray, 200, 255, cv2.THRESH_BINARY_INV)
            _, m_glow = cv2.threshold(roi_sat, 45, 255, cv2.THRESH_BINARY)
            
            combined = cv2.bitwise_and(cv2.bitwise_or(m_ink, m_glow), rect_mask)
            
            contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                if cv2.contourArea(cnt) > 5:
                    cv2.drawContours(full_mask[y:y_end, :], [cnt], -1, 255, thickness=-1)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    full_mask = cv2.dilate(full_mask, kernel, iterations=1)
    return cv2.medianBlur(full_mask, 3)

def run_ai_clean_tiled(cv_img: np.ndarray, mask: np.ndarray, lama: SimpleLama, 
                       device: str, progress_callback) -> np.ndarray:
    """
    Tiled AI Inpainting logic.
    Divides the image into chunks to avoid OOM (Out of Memory) errors on GPUs.
    """
    h, w = cv_img.shape[:2]
    target_h = 2000 
    num_tiles = max(1, int(np.ceil(h / target_h)))
    tile_h = int(np.ceil(h / num_tiles))
    
    overlap = 64
    new_img = cv_img.copy().astype(np.float32)

    for i in range(num_tiles):
        y_start = i * tile_h
        y_end = min(y_start + tile_h, h)
        
        if np.any(mask[y_start:y_end, :] > 0):
            y_s_ov = max(0, y_start - overlap)
            y_e_ov = min(y_end + overlap, h)
            
            t_img = cv_img[y_s_ov:y_e_ov, :]
            t_mask = mask[y_s_ov:y_e_ov, :]

            with torch.no_grad():
                res_pil = lama(Image.fromarray(cv2.cvtColor(t_img, cv2.COLOR_BGR2RGB)), 
                               Image.fromarray(t_mask).convert('L'))
                res_cv = cv2.cvtColor(np.array(res_pil), cv2.COLOR_RGB2BGR).astype(np.float32)

                if res_cv.shape[0] != (y_e_ov - y_s_ov):
                    res_cv = cv2.resize(res_cv, (w, y_e_ov - y_s_ov), interpolation=cv2.INTER_LANCZOS4)

                offset = y_start - y_s_ov
                res_tile = res_cv[offset : offset + (y_end - y_start), :]

                local_mask = mask[y_start:y_end, :].astype(np.float32) / 255.0
                local_mask = cv2.GaussianBlur(local_mask, (3, 3), 0)
                local_mask = np.expand_dims(local_mask, axis=-1)

                orig_tile = cv_img[y_start:y_end, :].astype(np.float32)
                new_img[y_start:y_end, :] = (res_tile * local_mask) + (orig_tile * (1.0 - local_mask))
        
        gc.collect()
        if device == "cuda": torch.cuda.empty_cache()
        progress_callback(int(((i + 1) / num_tiles) * 100))

    return np.clip(new_img, 0, 255).astype(np.uint8)

def get_mem_usage() -> int:
    """Returns current RSS memory usage in MB."""
    return int(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))