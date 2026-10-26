import json
import os
from src.utils.paths import Paths

#/////////////////////////////////#
#    GLOBAL STUDIO CONFIGURATION  #
#/////////////////////////////////#

class Config:
    APP_NAME = "MANGA-CLEANER STUDIO"
    VERSION = "3.3.2"

    # Deep Obsidian Theme
    COLOR_BG = "#0b0b0e"
    COLOR_PANEL = "#121217"
    COLOR_ACCENT = "#00d4ff" 
    COLOR_TEXT = "#e0e0e0"
    COLOR_TEXT_DIM = "#808085"
    COLOR_ERROR = "#ff4d4d"
    
    DEFAULT_BRUSH_SIZE = 40
    MAX_HISTORY = 20
    DEFAULT_TILE_WIDTH = 1024 

    _ID_FILE = os.path.join(Paths.CACHE, "batch_id.json")

    @staticmethod
    def get_next_batch_id():
        current_id = 1
        if os.path.exists(Config._ID_FILE):
            try:
                with open(Config._ID_FILE, 'r') as f:
                    data = json.load(f)
                    current_id = data.get("last_id", 0) + 1
            except:
                pass
        
        if current_id > 65535:
            current_id = 1
            
        with open(Config._ID_FILE, 'w') as f:
            json.dump({"last_id": current_id}, f)
            
        return f"batch_{current_id:05d}"
