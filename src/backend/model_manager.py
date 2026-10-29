"""Download and locate the ONNX models used by Manga Cleaner Studio."""

import os
import urllib.error
import urllib.request

from PySide6.QtCore import QThread, Signal

from src.utils.config import Config
from src.utils.i18n import tr
from src.utils.paths import Paths


MODEL_REPO_ID = "SVD-MKU-DEV/manga-cleaner-models"
MODEL_REPO_REVISION = "main"

MODEL_SPECS = {
    "lama": {
        "filename": "lama.onnx",
        "name_key": "models.lama_name",
        "description_key": "models.lama_description",
    },
    "ocr": {
        "filename": "ocr.onnx",
        "name_key": "models.ocr_name",
        "description_key": "models.ocr_description",
    },
}


class DownloadCancelledError(Exception):
    """Raised when the user cancels an in-progress model download."""


class ModelManager:
    """Resolve model paths and stream public model files into the app's models folder."""

    @staticmethod
    def model_path(model_key):
        """Return the local file path for a known model key."""
        spec = MODEL_SPECS.get(model_key)
        if spec is None:
            raise ValueError(f"Unknown model: {model_key}")
        return Paths.get_model(spec["filename"])

    @staticmethod
    def model_name(model_key):
        """Return the localized display name for a known model."""
        spec = MODEL_SPECS.get(model_key)
        if spec is None:
            raise ValueError(f"Unknown model: {model_key}")
        return tr(spec["name_key"])

    @staticmethod
    def repository_url():
        """Return the public model repository URL without a branch-specific path."""
        return f"https://huggingface.co/{MODEL_REPO_ID}"

    @staticmethod
    def is_available(model_key):
        """Check whether a non-empty model file is already installed."""
        try:
            path = ModelManager.model_path(model_key)
            return os.path.isfile(path) and os.path.getsize(path) > 0
        except OSError:
            return False

    @staticmethod
    def download_url(model_key):
        """Build the public Hugging Face URL for the requested model file."""
        spec = MODEL_SPECS.get(model_key)
        if spec is None:
            raise ValueError(f"Unknown model: {model_key}")
        return (
            f"https://huggingface.co/{MODEL_REPO_ID}/resolve/"
            f"{MODEL_REPO_REVISION}/{spec['filename']}?download=true"
        )

    @staticmethod
    def download(model_key, progress_callback, cancel_check):
        """Download a model to a temporary file, then atomically install it."""
        destination = ModelManager.model_path(model_key)
        temporary_path = destination + ".download"
        os.makedirs(os.path.dirname(destination), exist_ok=True)

        request = urllib.request.Request(
            ModelManager.download_url(model_key),
            headers={
                "User-Agent": f"MangaCleanerStudio/{Config.VERSION}",
                "Accept-Encoding": "identity",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.headers.get_content_type() == "text/html":
                    raise IOError("Hugging Face returned a web page instead of the model file.")
                total_size = int(
                    response.headers.get("Content-Length")
                    or response.headers.get("X-Linked-Size")
                    or 0
                )
                downloaded = 0
                progress_callback(downloaded, total_size)

                with open(temporary_path, "wb") as model_file:
                    while True:
                        if cancel_check():
                            raise DownloadCancelledError("Download cancelled by the user.")
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        model_file.write(chunk)
                        downloaded += len(chunk)
                        progress_callback(downloaded, total_size)

            if downloaded == 0:
                raise IOError("The server returned an empty model file.")
            if total_size and downloaded != total_size:
                raise IOError(
                    f"Incomplete download: received {downloaded} of {total_size} bytes."
                )

            os.replace(temporary_path, destination)
            return destination
        except (urllib.error.URLError, TimeoutError) as exc:
            raise IOError(str(exc)) from exc
        finally:
            if os.path.exists(temporary_path):
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass


class ModelDownloadThread(QThread):
    """Download one model without blocking the GUI thread."""

    progress = Signal(str, int, int)
    succeeded = Signal(str, str)
    failed = Signal(str, str)
    cancelled = Signal(str)

    def __init__(self, model_key, parent=None):
        """Store the model key to be downloaded by this worker thread."""
        super().__init__(parent)
        self.model_key = model_key

    def run(self):
        """Stream the model and report progress, completion, or failure."""
        try:
            path = ModelManager.download(
                self.model_key,
                lambda downloaded, total: self.progress.emit(
                    self.model_key, downloaded, total
                ),
                self.isInterruptionRequested,
            )
        except DownloadCancelledError:
            self.cancelled.emit(self.model_key)
        except Exception as exc:
            self.failed.emit(self.model_key, str(exc))
        else:
            self.succeeded.emit(self.model_key, path)
