from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout

from src.utils.config import Config
from src.utils.i18n import tr


class BatchSetupDialog(QDialog):
    """Choose the batch processing mode and export format."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("main.batch_setup"))
        self.setStyleSheet(f"background-color: {Config.COLOR_PANEL}; color: {Config.COLOR_TEXT};")

        self.scan_mode = QComboBox()
        for item_id, key in (
            ("none", "main.none"),
            ("Mask", "main.mask_cleanup"),
            ("OCR Scan", "main.ocr_scan"),
            ("Transparency Scan", "main.transparency_scan"),
        ):
            self.scan_mode.addItem(tr(key), item_id)
        self.scan_mode.setStyleSheet(
            f"background-color: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 4px;"
        )

        self.export_fmt = QComboBox()
        for item_id, key in (
            ("none", "main.none"),
            ("png", "main.png"),
            ("jpg", "main.jpg"),
            ("photoshop", "main.photoshop"),
            ("photopea", "main.photopea"),
        ):
            self.export_fmt.addItem(tr(key), item_id)
        self.export_fmt.setStyleSheet(
            f"background-color: {Config.COLOR_BG}; border: 1px solid #2a2a32; padding: 4px;"
        )

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet(
            f"QPushButton {{ background-color: {Config.COLOR_BG}; "
            "border: 1px solid #2a2a32; padding: 6px; }"
        )

        layout = QFormLayout(self)
        layout.addRow(tr("main.processing_mode"), self.scan_mode)
        layout.addRow(tr("main.export_format"), self.export_fmt)
        layout.addWidget(buttons)

    def get_results(self):
        return self.scan_mode.currentData(), self.export_fmt.currentData()
