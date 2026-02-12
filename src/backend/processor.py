import numpy as np
import cv2
import torch
from PIL import Image
from typing import Tuple, List, Optional
from src.backend.ai_manager import AIManager

#////////////////////////#
#   AI TILING ENGINE     #
#////////////////////////#

class ImageProcessor:
    @staticmethod
    def run_ocr_logic(cv_img: np.ndarray, langs: List[str]) -> np.ndarray:
        if cv_img is None:
            return np.array([])

        if len(cv_img.shape) == 3:
            gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
        else:
            gray = cv_img

        enhanced = cv2.equalizeHist(gray)
        reader = AIManager.get_ocr(langs)
        
        results = reader.readtext(enhanced, paragraph=False)
        
        h, w = gray.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)

        for (bbox, text, prob) in results:
            if prob < 0.15: 
                continue
            pts = np.array(bbox, np.int32)
            cv2.fillPoly(mask, [pts], 255)

        if np.any(mask):
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
            mask = cv2.dilate(mask, kernel, iterations=2)
            
        return mask

    @staticmethod
    def run_clean_logic(cv_img: np.ndarray, mask_img: np.ndarray, num_tiles: int) -> Tuple[np.ndarray, List]:
        #////////////////////////#
        #  VRAM & TILE PREP      #
        #////////////////////////#
        lama = AIManager.get_lama()
        h, w = cv_img.shape[:2]
        
        if h > 3000 and num_tiles < 2:
            num_tiles = 2

        _, mask_solid = cv2.threshold(mask_img, 10, 255, cv2.THRESH_BINARY)
        
        tile_h = (h // num_tiles) + 1
        overlap = 64
        output = cv_img.copy().astype(np.float32)
        history_patches = []

        if len(cv_img.shape) == 2:
            cv_img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_GRAY2RGB)
        else:
            cv_img_rgb = cv_img

        #////////////////////////#
        #  CORE TILING LOOP      #
        #////////////////////////#
        for i in range(num_tiles):
            y_start = i * (h // num_tiles)
            y_end = h if i == num_tiles - 1 else (i + 1) * (h // num_tiles)
            
            y1_crop = max(0, y_start - overlap)
            y2_crop = min(h, y_end + overlap)
            
            tile_mask = mask_solid[y1_crop:y2_crop, :]
            
            if not np.any(tile_mask > 0):
                continue
            
            history_patches.append((y_start, y_end, cv_img[y_start:y_end, :].copy()))
            
            img_tile = cv_img_rgb[y1_crop:y2_crop, :]
            
            res_pil = lama(Image.fromarray(img_tile), Image.fromarray(tile_mask).convert('L'))
            res_np = np.array(res_pil).astype(np.float32)

            if res_np.shape[:2] != img_tile.shape[:2]:
                res_np = cv2.resize(res_np, (img_tile.shape[1], img_tile.shape[0]), interpolation=4)

            if len(cv_img.shape) == 2:
                res_np = cv2.cvtColor(res_np.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)

            #////////////////////////#
            # GAUSSIAN SEAM BLENDING #
            #////////////////////////#
            tile_full_h = y2_crop - y1_crop
            weight_mask = np.ones((tile_full_h, w), dtype=np.float32)
            
            fade_dist = overlap
            if y1_crop > 0:
                for y in range(fade_dist):
                    weight_mask[y, :] *= (y / fade_dist)
            if y2_crop < h:
                for y in range(fade_dist):
                    weight_mask[-(y+1), :] *= (y / fade_dist)

            if len(cv_img.shape) == 3:
                weight_mask = np.expand_dims(weight_mask, axis=-1)

            target_slice = output[y1_crop:y2_crop, :]
            blended = (res_np * weight_mask) + (target_slice * (1.0 - weight_mask))
            output[y1_crop:y2_crop, :] = blended
            
        return np.clip(output, 0, 255).astype(np.uint8), history_patches