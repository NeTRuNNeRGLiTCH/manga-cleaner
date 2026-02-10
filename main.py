import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, qInstallMessageHandler
from src.frontend.main_window import MainWindow
from src.utils.logger import setup_logger

#////////////////////////#
#  QT MESSAGE FILTER     #
#////////////////////////#

def qt_message_handler(mode, context, message):
    """
    Intercepts C++ level engine warnings. 
    Filters out persistent DPI/Font calculation noise.
    """
    # List of "noise" strings to ignore
    noise = [
        "setPointSize", 
        "Point size <= 0", 
        "setPointSizeF"
    ]
    if any(n in message for n in noise):
        return # Ignore this message
    
    # Otherwise, let the message pass through (or ignore all warnings if preferred)
    if "Warning" in str(mode):
        return

#////////////////////////#
#    APP ENTRY POINT     #
#////////////////////////#

def main():
    # Install the filter BEFORE creating the QApplication
    qInstallMessageHandler(qt_message_handler)

    app = QApplication(sys.argv)
    
    # Set a robust default font
    app.setFont(QFont("Segoe UI", 9))
    app.setApplicationName("Titan Manga Cleaner")
    
    # Load diagnostic services
    logger = setup_logger()
    logger.info("Titan Studio Initializing...")

    # Load UI Styles
    qss_path = os.path.join("src", "frontend", "styles.qss")
    if os.path.exists(qss_path):
        try:
            with open(qss_path, "r") as f:
                app.setStyleSheet(f.read())
        except Exception as e:
            logger.error(f"Failed to load QSS: {e}")
    
    # Launch Main Studio
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()