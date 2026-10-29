"""Localized dialog for installing and managing the app's AI models."""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from src.backend.model_manager import MODEL_SPECS, ModelDownloadThread, ModelManager
from src.utils.config import Config
from src.utils.i18n import tr


class ModelManagerDialog(QDialog):
    """Offer optional model downloads and show per-model progress and paths."""

    def __init__(self, parent=None, model_keys=None, setup_mode=False):
        """Build the model list and download controls for the requested models."""
        super().__init__(parent)
        requested = model_keys if model_keys is not None else list(MODEL_SPECS)
        self.model_keys = [key for key in requested if key in MODEL_SPECS]
        self.setup_mode = setup_mode
        self.download_queue = []
        self.downloaded_models = set()
        self.download_thread = None
        self.close_after_cancel = False

        self.setWindowTitle(
            tr("models.setup_title") if setup_mode else tr("models.manager_title")
        )
        self.setMinimumWidth(460)
        self.setStyleSheet(
            f"background-color: {Config.COLOR_PANEL}; color: {Config.COLOR_TEXT};"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        intro_key = "models.setup_intro" if setup_mode else "models.manager_intro"
        intro = QLabel(tr(intro_key))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        source_label = QLabel(
            f'{tr("models.source_repository")}: '
            f'<a href="{ModelManager.repository_url()}">{ModelManager.repository_url()}</a>'
        )
        source_label.setOpenExternalLinks(True)
        source_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        source_label.setWordWrap(True)
        layout.addWidget(source_label)

        folder_label = QLabel(
            tr(
                "models.destination_folder",
                path=os.path.dirname(ModelManager.model_path(self.model_keys[0]))
                if self.model_keys else "",
            )
        )
        folder_label.setWordWrap(True)
        folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(folder_label)

        self.model_rows = {}
        for model_key in self.model_keys:
            row = QFrame()
            row.setStyleSheet(
                "QFrame { border: 1px solid #2a2a32; border-radius: 4px; }"
            )
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)

            controls_layout = QHBoxLayout()

            name_label = QLabel(ModelManager.model_name(model_key))
            name_label.setStyleSheet("border: none; font-weight: bold;")
            status_label = QLabel()
            status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            status_label.setStyleSheet("border: none; color: #8a8a90;")
            download_button = QPushButton(tr("models.download"))
            download_button.clicked.connect(
                lambda _checked=False, key=model_key: self.start_downloads([key])
            )
            controls_layout.addWidget(name_label, 1)
            controls_layout.addWidget(status_label)
            controls_layout.addWidget(download_button)
            row_layout.addLayout(controls_layout)

            description = QLabel(
                tr(
                    MODEL_SPECS[model_key]["description_key"],
                    filename=MODEL_SPECS[model_key]["filename"],
                )
            )
            description.setWordWrap(True)
            description.setStyleSheet("border: none; color: #b5b5bd;")
            row_layout.addWidget(description)
            layout.addWidget(row)
            self.model_rows[model_key] = (status_label, download_button)

        self.download_status = QLabel("")
        self.download_status.setWordWrap(True)
        self.download_status.setStyleSheet(f"color: {Config.COLOR_ACCENT};")
        layout.addWidget(self.download_status)

        self.destination_label = QLabel("")
        self.destination_label.setWordWrap(True)
        self.destination_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.destination_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        buttons_layout = QHBoxLayout()
        self.download_all_button = QPushButton(tr("models.download_all"))
        self.download_all_button.clicked.connect(
            lambda: self.start_downloads(self._missing_model_keys())
        )
        self.close_button = QPushButton(
            tr("models.not_now") if setup_mode else tr("common.cancel")
        )
        self.close_button.clicked.connect(self.cancel_or_close)
        buttons_layout.addWidget(self.download_all_button)
        buttons_layout.addWidget(self.close_button)
        layout.addLayout(buttons_layout)

        self._refresh_model_rows()

    @property
    def models_ready(self):
        """Return whether every model requested by this dialog is installed."""
        return bool(self.model_keys) and all(
            ModelManager.is_available(key) for key in self.model_keys
        )

    def _missing_model_keys(self):
        """Return requested model keys that do not currently have a local file."""
        return [key for key in self.model_keys if not ModelManager.is_available(key)]

    def _refresh_model_rows(self):
        """Update each row and the download-all action from current file state."""
        for model_key, (status_label, button) in self.model_rows.items():
            installed = ModelManager.is_available(model_key)
            status_label.setText(
                tr("models.installed") if installed else tr("models.not_installed")
            )
            button.setText(tr("models.installed") if installed else tr("models.download"))
            button.setEnabled(not installed and self.download_thread is None)

        missing = self._missing_model_keys()
        self.download_all_button.setEnabled(bool(missing) and self.download_thread is None)
        if not missing and self.download_thread is None:
            self.download_status.setText(tr("models.all_installed"))

    def start_downloads(self, model_keys):
        """Queue missing models and start downloading them one at a time."""
        if self.download_thread is not None:
            return
        self.download_queue = [
            key for key in model_keys
            if key in self.model_rows and not ModelManager.is_available(key)
        ]
        self.downloaded_models.clear()
        if not self.download_queue:
            self._refresh_model_rows()
            return
        self._start_next_download()

    def _start_next_download(self):
        """Start the next queued model or report the completed download batch."""
        if not self.download_queue:
            self.progress_bar.setVisible(False)
            self.download_thread = None
            self._refresh_model_rows()
            if self.downloaded_models:
                self.download_status.setText(tr("models.download_complete"))
            return

        model_key = self.download_queue.pop(0)
        self.download_status.setText(
            tr("models.downloading_model", model=ModelManager.model_name(model_key), percent=0)
        )
        self.destination_label.setText(
            tr("models.saving_to", path=ModelManager.model_path(model_key))
        )
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        thread = ModelDownloadThread(model_key, self)
        thread.progress.connect(self._on_download_progress)
        thread.succeeded.connect(self._on_download_succeeded)
        thread.failed.connect(self._on_download_failed)
        thread.cancelled.connect(self._on_download_cancelled)
        thread.finished.connect(thread.deleteLater)
        self.download_thread = thread
        self._refresh_model_rows()
        self.close_button.setText(tr("models.cancel_download"))
        thread.start()

    def _on_download_progress(self, model_key, downloaded, total):
        """Display the active model name and percentage while it downloads."""
        model_name = ModelManager.model_name(model_key)
        if total > 0:
            percent = min(100, int(downloaded * 100 / total))
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percent)
            self.download_status.setText(
                tr("models.downloading_model", model=model_name, percent=percent)
            )
        else:
            self.progress_bar.setRange(0, 0)
            self.download_status.setText(
                tr("models.downloading_unknown_size", model=model_name, mb=downloaded // (1024 * 1024))
            )

    def _on_download_succeeded(self, model_key, path):
        """Record a completed model and continue with the next queued download."""
        self.downloaded_models.add(model_key)
        self.download_status.setText(
            tr("models.model_downloaded", model=ModelManager.model_name(model_key))
        )
        self.destination_label.setText(tr("models.saved_to", path=path))
        self.download_thread = None
        self.close_button.setEnabled(True)
        self.close_button.setText(
            tr("models.not_now") if self.setup_mode else tr("common.cancel")
        )
        self._refresh_model_rows()
        if self.close_after_cancel:
            self.download_queue.clear()
            self.reject()
            return
        self._start_next_download()

    def _on_download_failed(self, model_key, error):
        """Keep the dialog open, show the error, and allow the user to retry."""
        self.download_thread = None
        self.download_queue.clear()
        self.progress_bar.setVisible(False)
        self.close_button.setEnabled(True)
        self.close_button.setText(
            tr("models.not_now") if self.setup_mode else tr("common.cancel")
        )
        self._refresh_model_rows()
        if self.close_after_cancel:
            self.reject()
            return
        QMessageBox.critical(
            self,
            tr("models.download_failed_title"),
            tr("models.download_failed", model=ModelManager.model_name(model_key), error=error),
        )

    def _on_download_cancelled(self, model_key):
        """Stop the download queue after the active transfer is cancelled."""
        self.download_thread = None
        self.download_queue.clear()
        self.progress_bar.setVisible(False)
        self.destination_label.clear()
        self.download_status.setText(tr("models.download_cancelled"))
        self.close_button.setEnabled(True)
        self.close_button.setText(
            tr("models.not_now") if self.setup_mode else tr("common.cancel")
        )
        self._refresh_model_rows()
        if self.close_after_cancel:
            self.reject()

    def cancel_or_close(self):
        """Request cancellation during a transfer, or close when idle."""
        if self.download_thread is not None:
            self.close_after_cancel = True
            self.close_button.setEnabled(False)
            self.download_status.setText(tr("models.cancelling_download"))
            self.download_thread.requestInterruption()
            return
        self.reject()

    def closeEvent(self, event):
        """Prevent closing during a transfer until its temporary file is cleaned up."""
        if self.download_thread is not None:
            self.close_after_cancel = True
            self.download_thread.requestInterruption()
            event.ignore()
            return
        super().closeEvent(event)
