# 🌌 MANGA CLEANER STUDIO v3.4.2

**AI-assisted manga and webtoon cleanup, typesetting, translation workflow, and page assembly.**

[![Download v3.4.2](https://img.shields.io/badge/DOWNLOAD-v3.4.2-00d4ff?style=for-the-badge&logo=github)](https://github.com/NeTRuNNeRGLiTCH/manga-cleaner/releases)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?style=for-the-badge)](https://www.python.org/)
[![Downloads](https://img.shields.io/github/downloads/NeTRuNNeRGLiTCH/manga-cleaner/total?color=blue&style=for-the-badge)](https://github.com/NeTRuNNeRGLiTCH/manga-cleaner/releases)
[![Sibling App](https://img.shields.io/badge/Sibling_Project-Manga_Translate-ff007f?style=for-the-badge)](https://github.com/santiagodvergara05-debug/manga-translate-studio)

**Manga Cleaner Studio** is a desktop toolkit for preparing manga and webtoon pages. It combines AI-assisted image cleanup and manual mask editing with OCR and transparency scanning, text placement and styling, script synchronization, and lossless vertical stitching. The interface supports multiple languages. See [`TRANSLATION.md`](TRANSLATION.md) for available languages, localization status, and the catalog workflow.

---

## 🖥️ Studio Preview (v3.4.0 UI)

![Manga Cleaner Studio v3.4.0 UI](.github/assets/ui.png)

*Featuring the Obsidian Dark Theme, the two-column tool layout, live file-queue locking, and the four-workspace switcher (Cleaner · Typesetter · Stitcher · Translator).*

---

## 🎓 Installation & Setup Tutorial

For quick setup, follow the [Running from Source](#-running-from-source) guide below.

### 🎥 Video Walkthrough

Prefer a visual guide? Watch the video walkthrough:

[![Watch the Video Tutorial](https://img.youtube.com/vi/9psnwpJG3aE/hqdefault.jpg)](https://www.youtube.com/watch?v=9psnwpJG3aE)

*Note: The tutorial was recorded using version 3.2.0. The current 3.4.0 interface and features may differ; use the sections below as the up-to-date reference.*

---

## 🛠️ Studio Workspaces & Capabilities

Manga Cleaner Studio unifies the complete scanlation pipeline into four specialized workspaces, allowing teams to restore, translate, typeset, and assemble webtoons and manga in a single application.

---

### 1. 🧹 Cleaner Workspace (AI Inpainting & Manual Touch-up)
* **LaMa AI Inpainting Engine:** High-resolution inpainting powered by ONNX Runtime, utilizing Snap-to-8 Dynamic ROI reflection padding to clean scans without downscaling or quality loss.
* **Automated Scanners:** Single-key OCR text detection (`O`) and transparency/alpha channel detection (`T`).
* **Complete Mask Toolkit:** Brush (`B`), Eraser (`E`), Rectangle (`R`), Freehand Lasso (`L`), Polygonal Selection (`P`), and Bucket Fill (`G`).
* **Manual Cleaner Brush (`D`):** Paint directly onto flat speech bubbles or backgrounds without triggering AI overhead.
* **Eyedropper Color Picker (`I`):** Sample page pixels on the fly with `Alt + Left-Click`, supported by quick color swatches and instant pure-white reset.
* **Smart History (Undo/Redo):** `Ctrl+Z` and `Ctrl+Shift+Z` intelligently differentiate between direct image strokes (in Manual mode) and selection mask edits.

---

### 2. 🔤 Typesetter Workspace (Typography & Styling)
* **Interactive Transform Gizmo:** Center-locked scaling corner handles prevent coordinate drift while resizing. Horizontal handles adjust word-wrap boundary width, and the top handle controls free rotation (hold `Shift` to snap to 15° increments).
* **Vector Outside Stroke:** Renders a clean outer outline beneath the letter fill with adjustable pixel width and alpha opacity. Includes one-click fill/stroke color swapping (`⇄`).
* **Font Manager & Preset Cache:** Search system fonts by family or alias, filter to favorites with **★ Only**, and assign custom use-case aliases (e.g., `★ Shout [Wild Words]`). Preferences persist automatically in `cache/font_presets.json`.
* **Show Outlines Toggle:** Switch between inspection mode (dashed cyan bounding boxes to locate accidental text placed on dark backgrounds) and a clean final preview.
* **Dual Layer Tracking:** View and center placed text items (`[ ✓ ]`) or review unplaced script dialogues (`[ + ]`) directly within **PAGE TEXT LAYERS**.

---

### 3. 📄 Translator Workspace (Script Sync & Sibling Ecosystem)
* **Shared Folder Hierarchy (`translations/`):** Two-tier folder organization (`translations/<Series>/`) shared natively with **Manga Translate Studio**.
* **Directory Management:** Create new series subfolders (`➕`) and open active directories in the native operating system file manager (`📁`).
* **Zero-RAM Lazy Queue:** Imports `.txt` scripts without pre-rendering or RAM bloat. Dialogue lines are queued as `[ + ]` items that spawn on the canvas using active font settings upon clicking.
* **Unload Script:** Clear all queued script lines across pages from memory with one click without resetting placed text or active page sessions.
* **Unicode NFC Normalization:** Guarantees character matching for Japanese, Korean, Chinese, and Latin filenames and text.

---

### 4. 🧩 Stitcher Workspace (Lossless Webtoon Assembly)
* **Vertical Page Stitching:** Combines webtoon strips into continuous files while preserving active cleanings and typeset layers.
* **Flexible Grouping Modes:** Group pages manually (`From ➔ To`), by fixed pages-per-file, or by automatic distribution into a target total file count.
* **Height Guard & Formats:** Configure automatic vertical splitting guards to prevent oversized outputs, with export options in lossless PNG or 100% 4:4:4 JPG.

---

### 5. ⚡ Studio Automation & Pipeline Integrations
* **Multi-Task Batch Processing:** Automated load ➔ scan ➔ clean ➔ export pipeline across entire chapters with live background lock indicators.
* **External Editor Bridges:** One-click direct transfer of original and cleaned layers to Adobe Photoshop or Photopea (web).
* **Natural Numerical Sorting:** Scans numbered `1`, `2`, `10`, `100` load in chronological order instead of alphabetical sequence.
* **Project Reset (`RESET`):** Safely wipe in-memory sessions, text layers, and masks to begin a new chapter without restarting the application.
---

## 🤝 Sibling Ecosystem: Manga Translate Studio

Manga Cleaner Studio is paired with **[Manga Translate Studio](https://github.com/santiagodvergara05-debug/manga-translate-studio)**, a companion desktop application for multimodal AI translation (Ollama, Gemini, Claude, OpenAI). 

Both tools share the same design language, file conventions, and root `translations/` directory, allowing teams to translate, clean, typeset, and stitch manga chapters with zero file conversion overhead.

---

## 📸 Before & After Restoration

| Original Scan | AI Restored |
| :---: | :---: |
| ![Before 1](.github/assets/before_1.jpg) | ![After 1](.github/assets/after_1.jpg) |
| ![Before 2](.github/assets/before_2.jpg) | ![After 2](.github/assets/after_2.jpg) |

---

## 📦 Version Comparison: GPU vs. CPU

| Feature | ⚡ CUDA GPU Edition | ☁️ Standard CPU Edition |
| :--- | :--- | :--- |
| **Ideal For** | NVIDIA GPUs with compatible CUDA runtime | Laptops and integrated graphics |
| **Package Size** | ~900 MB (build dependent) | ~260 MB (build dependent) |
| **Cleaning Speed** | Sub-second per tile | Moderate CPU execution |
| **Hardware** | NVIDIA GPU (Compute Capability 6.0+) | Modern x64 CPU |

---

## 📝 Translator Script Format

The **TRANSLATOR** workspace processes UTF-8 `.txt` script templates:

```text
### SERIES TITLE: My Series
### CHAPTER: 12

<translation>

Image 1 [001.jpg]
- First dialogue bubble
- Second bubble//with a manual line break

Image 2 [002.jpg]
-
-

</translation>

```

* Only text enclosed within `<translation>` and `</translation>` is parsed.
* Each `-` denotes a text box. Empty `-` lines are ignored.
* Use `//` for manual line breaks within the same bubble.
* `[filename]` brackets allow matching dialogues to files regardless of sort order.

---

## ⌨️ Professional Shortcuts

| Key | Action |
| --- | --- |
| `O` | Run OCR text detection |
| `T` | Scan transparent areas |
| `C` | Execute AI inpainting clean |
| `B` / `E` / `M` | Select Brush / Eraser / Move tools |
| `R` / `L` / `P` | Select Rectangle / Lasso / Polygon tools |
| `G` | Bucket Fill tool |
| `D` / `I` | Select Manual Cleaner / Eyedropper Color Picker |
| `X` | Switch to Typesetter & activate Text mode |
| `Shift + Click` | Draw straight line between points |
| `Double-Click` | Commit polygon selection / Edit existing text box |
| `Alt + Right-Click Drag` | Dynamically resize brush |
| `Alt + Left-Click` | Sample color while Manual Cleaner is active |
| `Ctrl + Scroll` | Adjust selected text font size |
| `Ctrl + Shift + Scroll` | Rotate text in 5° steps |
| `Ctrl + Z` / `Ctrl + Shift + Z` | Smart undo / redo (Image stroke in Manual mode, Mask otherwise) |
| `Alt + Z` / `Alt + Shift + Z` | Image history undo / redo (AI clean patches) |

---

## 🗺️ Roadmap: The Future of Manga Cleaner

### Python version

- **v3.4.0:** Multi-language UI foundation with English fallback, a language selector, and community-maintained locale catalogs. See [`TRANSLATION.md`](TRANSLATION.md) for language support details.
- **v3.5.0 (under investigation):** Potential watermark-removal support using an AI model, subject to implementation feasibility and attribution to the model developer.

The Python roadmap may change if development of the C++ version progresses faster than expected.

### C++ version

- **v4.0.0 (in development):** Planned AMD GPU support through DirectML execution providers and other community-requested improvements.

---

## 🚀 Running from Source

Running directly from the repository is recommended for development and Linux NVIDIA GPU configurations.

### 1. Clone the Repository

```bash
git clone https://github.com/NeTRuNNeRGLiTCH/manga-cleaner.git
cd manga-cleaner

```

### 2. Download AI Models

On first launch, the application offers to download missing ONNX models from its configured Hugging Face repository. You can also open **AI Models** in the application to download them later. The files are saved to the `models/` directory beside the source checkout or executable; a separate `models.zip` is not required.

### 3. Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

# Install dependencies (CPU / Default):
pip install -r requirements.txt

# For Linux with NVIDIA GPU support:
pip install -r requirements_linux.txt

```

### 4. Launch the Application

```bash
python main.py
```

### 5. Build an Executable

`build.py` checks the active Python environment for PyInstaller and installs version `6.18.0` with `pip` if it is missing. The install needs an internet connection. It does not add PyInstaller to the application's runtime requirements.

On Linux, you can use `build.sh` instead of preparing the Python build environment manually. Install the Linux system libraries first (Debian/Ubuntu example):

```bash
sudo apt-get install python3.12-venv libgl1 libglib2.0-0 libegl1 libxkbcommon-x11-0 libdbus-1-3
```

Then run the interactive CPU/GPU selector, or pass `cpu`, `gpu`, or `all` directly:

```bash
bash build.sh
bash build.sh cpu
bash build.sh gpu
bash build.sh all
```

The helper creates separate Python 3.12 environments under `build/`, installs the matching requirements and PyInstaller, then invokes `build.py`. To choose a specific interpreter, set `PYTHON`, for example `PYTHON=python3.12 bash build.sh cpu`. It does not install system packages or use `sudo` itself.

On Windows, install the additional CUDA DLL packages before selecting the Windows GPU target:

```bash
python -m pip install nvidia-cuda-runtime-cu12 nvidia-cudnn-cu12 nvidia-cublas-cu12 nvidia-cufft-cu12 nvidia-curand-cu12
```

Run the interactive build selector. It lists only targets supported on the current operating system:

```bash
python build.py
```

You can also select a target directly. The target IDs are `windows-cpu`, `windows-cpu-clean`, `windows-gpu`, `linux-cpu`, and `linux-gpu`:

```bash
python build.py --list
python build.py --target windows-cpu-clean
python build.py --all --yes
```

`--all` builds every target supported on the current operating system; `--yes` allows it to replace existing outputs without prompting. Windows targets must be built on Windows and Linux targets on Linux; PyInstaller does not cross-compile between these platforms. Each target uses its own `build/` and `dist/` subdirectory so variants with the same executable name do not overwrite one another.

The selector invokes the corresponding `.spec`; those files remain separate because their CPU/GPU dependencies and platform settings differ. Models are not bundled and are downloaded by the application when needed.

---

## 👥 Contributing

Interested in contributing code, models, or optimizations? Please review **[CONTRIBUTING.md](CONTRIBUTING.md)** for development guidelines, coding standards, and compilation instructions (PyInstaller / Docker).

### Project Directory Structure

```text
manga-cleaner/
├── assets/                         # Application icons and bundled UI assets
├── .github/
│   └── workflows/
│       └── build.yml               # Validates locale approvals before release builds
├── locales/                        # Language JSON catalogs and index (see TRANSLATION.md)
├── src/
│   ├── backend/                    # Image processing, AI, batch, and export logic
│   │   ├── ai_manager.py           # AI model inference and cleanup
│   │   ├── batch_engine.py         # Batch job setup and processing queue
│   │   ├── model_manager.py        # AI model locations and Hugging Face downloads
│   │   ├── onnx_engine.py          # ONNX runtime setup and inference helpers
│   │   ├── photopea.py             # Photopea integration
│   │   ├── photoshop.py            # Adobe Photoshop integration
│   │   ├── processor.py            # Image processing pipeline
│   │   ├── stitcher.py             # Lossless page stitching
│   │   ├── translator.py           # Translation script parsing and synchronization
│   │   └── workers.py              # Background processing workers
│   ├── frontend/                   # PySide6 windows, widgets, canvas, and styles
│   │   ├── batch_setup_dialog.py   # Batch scan and export options
│   │   ├── canvas.py               # Image canvas and interactive text items
│   │   ├── help_system.py          # In-app help window and guides
│   │   ├── main_window.py          # Main application window and controller
│   │   ├── model_manager_dialog.py # Model information and download UI
│   │   ├── project_reset.py        # Project reset and cleanup controller
│   │   ├── styles.qss              # Application stylesheet
│   │   ├── typesetter_panel.py     # Typesetting controls and text queue
│   │   └── widgets.py              # Shared UI widgets
│   └── utils/                      # Configuration, localization, paths, and logging
│       ├── config.py               # Application constants and settings
│       ├── history.py              # Undo and redo history
│       ├── i18n.py                 # Single-catalog loader and verification checks
│       ├── logger.py               # Application logging
│       ├── paths.py                # Runtime and resource path handling
│       └── system_info.py          # System and hardware monitoring
├── tests/
│   └── test_i18n.py                # Catalog loading, approval, and fingerprint tests
├── tools/                          # Localization extraction, migration, and validation
│   ├── check_locales.py            # Compare, complete, approve, and release-check catalogs
│   ├── extract_strings.py          # Find visible strings in the source
│   ├── fix_leftovers.py            # Apply reviewed one-time migration fixes
│   └── migrate_to_tr.py            # Migrate visible text to translation calls
├── .gitignore                      # Excluded local, generated, and runtime files
├── build.py                        # Interactive native-platform PyInstaller target selector
├── build.sh                        # Linux CPU/GPU build setup and launcher
├── CONTRIBUTING.md                 # Development and contribution guidelines
├── DEVELOPMENT_NOTES.md            # Performance and maintenance review follow-ups
├── LICENSE                         # Apache 2.0 license
├── main.py                         # Application entry point
├── MangaCleaner_CPU.spec           # Windows CPU PyInstaller build
├── MangaCleaner_CPU_clean.spec     # Minimal Windows CPU PyInstaller build
├── MangaCleaner_CPU_linux.spec     # Linux CPU PyInstaller build
├── MangaCleaner_GPU.spec           # Windows GPU PyInstaller build
├── MangaCleaner_GPU_linux.spec     # Linux GPU PyInstaller build
├── README.md                       # Project overview and setup instructions
├── requirements.txt                # Windows and general Python dependencies
├── requirements_linux.txt          # Linux Python dependencies
└── TRANSLATION.md                  # Localization and catalog workflow
```

Runtime data, downloaded models, build outputs, and processed images are created or installed separately and are not part of the source tree shown above. See [Running from Source](#-running-from-source) and [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📜 License

Manga Cleaner Studio is open-source software licensed under the **[Apache License 2.0](LICENSE)**.

```text
Copyright © 2024-2026 NeTRuNNeRGLiTCH & Contributors.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    [http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0)

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

```
