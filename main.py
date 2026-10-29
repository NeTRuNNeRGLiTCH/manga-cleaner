import sys
import os
import ctypes
import multiprocessing
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt, qInstallMessageHandler, QLocale
from src.frontend.main_window import MainWindow
from src.utils.logger import logger
from src.utils.paths import Paths
from src.utils.config import Config
from src.utils import i18n

#/////////////////////////////////#
#      QT MESSAGE FILTER          #
#/////////////////////////////////#

def qt_message_handler(mode, context, message):
    noise = ["setPointSize", "Point size <= 0", "setPointSizeF"]
    if any(n in message for n in noise): return 
    if "Warning" in str(mode): return

#/////////////////////////////////#
#      STUDIO ENTRY POINT         #
#/////////////////////////////////#

def main():

    # Taskbar Icon Fix for Windows
    if os.name == 'nt':
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("mangacleaner.app")
        except Exception:
            pass

    # 0. Hidden Console Fix
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    # 1. Initialize System Paths & Localization Engine
    Paths.initialize()
    i18n.init(
        bundled_dir=Paths.LOCALES_BUNDLED,
        user_dir=Paths.LOCALES_USER,
        settings_path=os.path.join(Paths.CACHE, "settings.json"),
        system_locale=QLocale.system().name(),
    )
    
    # 2. Setup Logging & Filters
    qInstallMessageHandler(qt_message_handler)
    
    # 3. Initialize App
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))
    app.setApplicationName(Config.APP_NAME)
    app.setLayoutDirection(
        Qt.RightToLeft if i18n.current_language().lower().startswith("ar") else Qt.LeftToRight
    )
    
    logger.info(f"--- {Config.APP_NAME.upper()} STARTUP ---")

    # 4. Inject Theme Styles
    # PyInstaller hides bundled files in an internal folder. sys._MEIPASS safely locates it.
    if getattr(sys, 'frozen', False):
        bundle_dir = sys._MEIPASS
    else:
        bundle_dir = Paths.BASE_DIR

    icon_path = os.path.join(bundle_dir, "assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    qss_path = os.path.join(bundle_dir, "src", "frontend", "styles.qss")

    if os.path.exists(qss_path):
        try:
            with open(qss_path, "r") as f:
                app.setStyleSheet(f.read())
            logger.info("[+] Stylesheet loaded successfully.")
        except Exception as e:
            logger.error(f"Styles Load Failed: {e}")
    else:
        logger.warning(f"Stylesheet missing at: {qss_path}")    

    # Warn every launch if the English source catalog is missing from all locations.
    if not i18n.has_english_source_catalog():
        searched_paths = sorted({
            os.path.join(folder, "en.json")
            for folder in (Paths.LOCALES_BUNDLED, Paths.LOCALES_USER)
            if folder
        })
        warning = QMessageBox()
        warning.setIcon(QMessageBox.Critical)
        warning.setWindowTitle("Critical: English source catalog missing")
        warning.setText(
            "The English source catalog (locales/en.json) is missing."
        )
        warning.setInformativeText(
            "English is the source of truth for the application's translations. "
            "Without it, some interface text or localization tools may fail. "
            "Restore en.json from a clean copy of the project. The application "
            "will continue after you acknowledge this warning.\n\n"
            "Searched locations:\n" + "\n".join(searched_paths)
        )
        warning.setStandardButtons(QMessageBox.Ok)
        warning.button(QMessageBox.Ok).setText("OK — Continue")
        warning.exec()

    catalog_issue = i18n.catalog_warning()
    if catalog_issue and i18n.has_english_source_catalog():
        warning = QMessageBox()
        warning.setIcon(QMessageBox.Warning)
        warning.setWindowTitle(i18n.tr("localization.verification_required_title"))
        warning.setText(i18n.tr(
            "localization.verification_required_message",
            language=catalog_issue["language"],
            reason=catalog_issue["reason"],
        ))
        warning.setInformativeText(i18n.tr(
            "localization.verification_required_instructions",
            language=catalog_issue["language"],
        ))
        warning.setStandardButtons(QMessageBox.Ok)
        warning.exec()

    # 5. Launch Main Studio
    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"FATAL SYSTEM CRASH: {e}", exc_info=True)
    finally:
        logger.info(f"--- {Config.APP_NAME.upper()} SHUTDOWN ---")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
