from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QTextEdit, QPushButton
from src.utils.system_info import SystemMonitor
from src.utils.i18n import tr

#/////////////////////////////////#
#    STUDIO KNOWLEDGE BASE        #
#/////////////////////////////////#

class HelpSystem(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("help.manga_cleaner_studio_manual"))
        self.resize(740, 560)
        self.setStyleSheet("background-color: #121217; color: #e0e0e0; font-family: 'Segoe UI';")
        
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        # ==========================================
        # TAB 1: KEYBOARD SHORTCUTS
        # ==========================================
        tab_shortcuts = QTextEdit()
        tab_shortcuts.setReadOnly(True)
        tab_shortcuts.setHtml(
            tr("help.tab_shortcuts_html")
        )

        # ==========================================
        # TAB 2: CLEANER & MANUAL BRUSH
        # ==========================================
        tab_cleaner = QTextEdit()
        tab_cleaner.setReadOnly(True)
        tab_cleaner.setHtml(
            tr("help.tab_cleaner_html")
        )

        # ==========================================
        # TAB 3: TYPESETTER & FONT MANAGER
        # ==========================================
        tab_typesetter = QTextEdit()
        tab_typesetter.setReadOnly(True)
        tab_typesetter.setHtml(
            tr("help.tab_typesetter_html")
        )

        # ==========================================
        # TAB 4: TRANSLATOR (.TXT SCRIPT)
        # ==========================================
        tab_translator = QTextEdit()
        tab_translator.setReadOnly(True)
        tab_translator.setHtml(
            tr("help.tab_translator_html")
        )

        # ==========================================
        # TAB 5: STITCHER & BATCHING
        # ==========================================
        tab_stitch_batch = QTextEdit()
        tab_stitch_batch.setReadOnly(True)
        tab_stitch_batch.setHtml(
            tr("help.tab_stitch_batch_html")
        )

        # ==========================================
        # TAB 6: HARDWARE DIAGNOSTICS
        # ==========================================
        specs = SystemMonitor.get_detailed_specs()
        tab_hardware = QTextEdit()
        tab_hardware.setReadOnly(True)
        tab_hardware.setHtml(
            tr("help.tab_hardware_html", engine=specs['engine'], ram=specs['ram'])
        )
        
        tabs.addTab(tab_shortcuts, tr("help.shortcuts"))
        tabs.addTab(tab_cleaner, tr("help.cleaner_manual"))
        tabs.addTab(tab_typesetter, tr("help.typesetter"))
        tabs.addTab(tab_translator, tr("help.translator_txt"))
        tabs.addTab(tab_stitch_batch, tr("help.stitcher_batch"))
        tabs.addTab(tab_hardware, tr("help.hardware"))
        layout.addWidget(tabs)
        
        close_btn = QPushButton(tr("help.close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    @staticmethod
    def show_guide(parent):
        dialog = HelpSystem(parent)
        dialog.exec()