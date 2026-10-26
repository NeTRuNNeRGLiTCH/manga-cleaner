import os
import sys

#/////////////////////////////////#
#      FILESYSTEM ARCHITECT       #
#/////////////////////////////////#

class Paths:
    if getattr(sys, 'frozen', False):
        BASE_DIR = os.path.dirname(sys.executable)
        BUNDLE_DIR = getattr(sys, '_MEIPASS', BASE_DIR) # Points specifically to the _internal folder
    else:
        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        BUNDLE_DIR = BASE_DIR

    MODELS = os.path.join(BASE_DIR, "models")
    LOGS = os.path.join(BASE_DIR, "logs")
    CACHE = os.path.join(BASE_DIR, "cache")
    PROCESSED = os.path.join(BASE_DIR, "processed")
    TRANSLATIONS = os.path.join(BASE_DIR, "translations")
    ASSETS = os.path.join(BUNDLE_DIR, "assets")

    @staticmethod
    def initialize():
        for p in [Paths.MODELS, Paths.LOGS, Paths.CACHE, Paths.PROCESSED, Paths.TRANSLATIONS]:
            os.makedirs(p, exist_ok=True)

    @staticmethod
    def get_model(name):
        return os.path.join(Paths.MODELS, name)

# Inicialización preventiva de directorios
Paths.initialize()