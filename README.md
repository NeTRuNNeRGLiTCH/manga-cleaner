# 🌌 MANGA CLEANER STUDIO v3.3.2: The Workspaces & Typesetting Update

**High-Fidelity AI-Powered Scanlation Restoration Suite**

[![Download v3.3.2](https://img.shields.io/badge/DOWNLOAD-v3.3.2-00d4ff?style=for-the-badge&logo=github)](https://github.com/NeTRuNNeRGLiTCH/manga-cleaner/releases)
[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Downloads](https://img.shields.io/github/downloads/NeTRuNNeRGLiTCH/manga-cleaner/total?color=blue)](https://github.com/NeTRuNNeRGLiTCH/manga-cleaner/releases)

Building on the modular Studio engine introduced in v3.0.0 and the toolkit expansion in v3.2.0, **Manga Cleaner Studio v3.3.2** expands Manga Cleaner into a multi-workspace scanlation tool. Four dedicated workspaces—**Cleaner**, **Typesetter**, **Stitcher**, and **Translator**—help users move from scan restoration to text placement and page assembly without leaving the application.

---

## 🖥️ Studio Preview (v3.3.2 UI)

![Manga Cleaner Studio v3.3.2 UI](.github/assets/ui.png)

*Featuring the Obsidian Dark Theme, the two-column tool layout, live file-queue locking, and the four-workspace switcher (Cleaner · Typesetter · Stitcher · Translator). The screenshot shows the workspace layout used by v3.3.2.*

---

## 🎓 Installation & Setup Tutorial

For recommended installation and setup instructions, see [Running from Source](#-running-from-source). This section covers:

- Linux users with NVIDIA GPUs (recommended)
- CPU-only installations
- Downloading and setting up the required AI models
- Running Manga Cleaner directly from the repository

### 🎥 Video Tutorial

Prefer a visual walkthrough? Follow the video tutorial:

[![Watch the Video Tutorial](https://img.youtube.com/vi/9psnwpJG3aE/hqdefault.jpg)](https://www.youtube.com/watch?v=9psnwpJG3aE)

The video provides a step-by-step walkthrough of setting up and using Manga Cleaner. **Note:** The video was recorded with version 3.2.0, so some newer Studio features are not shown.

---

## ✨ What's New in v3.3.2

Everything after the cleaning step—including translating, typesetting, and stitching—can now be handled in the same window.

- **Four Workspaces:** Switch between **CLEANER**, **TYPESETTER**, **STITCHER**, and **TRANSLATOR** using the 2×2 selector at the top of the right panel. Each workspace shows the controls relevant to that task.
- **Photoshop-Style Typesetter:** Add text directly to the page with a transform gizmo. Corner handles scale the font, side handles resize the text box with automatic word wrapping, and the top handle rotates text. Hold `Shift` while rotating to snap to 15° increments. The panel also includes bold, italic, centering, an **Angle** field, a `0°` reset, and **Fit Box** auto-width.
- **Vector Outside Stroke:** Apply an outer text stroke with adjustable width and opacity. The text fill is rendered over the stroke to keep the outline outside the letter fill. Switch modes with **Mode: Normal / Stroke (Outside)**. Color swatches and a one-click fill/stroke color swap (`⇄`) are included.
- **Font Manager:** Search fonts by family name or alias, filter to favorites with **★ Only**, toggle favorites, and assign custom aliases while keeping the system font name visible (`Alias [Family]`). Preferences are saved to `font_presets.json`.
- **Page Text Layers:** View placed text boxes and queued script lines for the active page. Select a placed entry to select and center the corresponding text item. Queued dialogue entries are displayed in the same list.
- **Manual Cleaner (`MANUAL` + `PICKER`):** Paint directly onto the page for touch-ups that the AI misses. Draw straight lines with `Shift + Click`, resize the brush with `Alt + Right-Click Drag`, and sample a pixel with `PICKER` or `Alt + Left-Click` while Manual Cleaner is active. A color swatch and quick **White** reset are available.
- **Smart Undo/Redo:** While `MANUAL` or `PICKER` is active, `Ctrl+Z` and `Ctrl+Shift+Z` undo and redo direct image painting. With mask tools active, those shortcuts continue to operate on mask edits.
- **Translator Workspace:** Generate a `.txt` script template for the loaded pages and import a completed translation. Dialogues can be matched by `[filename]` or image order, and unmatched pages are reported. Imported dialogue is queued as text entries instead of being rasterized into the page at import time. Click a queued `[ + ]` entry to place it using the currently selected font and style. See [Translator Script Format](#-translator-script-format).
- **Stitcher:** Join pages vertically while preserving the current cleaning edits and text layers. Group pages manually (`From → To`), by pages per output file, or by a maximum number of output files. Optional **Max Height** protection can be synchronized with **Max Tile Size**. PNG output is lossless; JPG output is compressed even when exported at high quality.
- **Natural Filename Sorting:** Imported page filenames are sorted naturally, so numbered names such as `001`, `002`, `010`, and `100` appear in numerical order rather than lexicographic order.
- **Project Reset:** Use **RESET** to clear the current in-memory project and return to an empty workspace without restarting the application. It clears loaded-page sessions, masks, text layers, pending dialogue entries, project histories, Stitcher blocks, and Translator script state. It does not delete source image files or persistent font preferences. Reset is blocked while an AI task or batch process is active. Actual memory usage after reset depends on the operating system and the memory retained by Python, Qt, OpenCV, and ONNX Runtime; the feature does not guarantee a fixed RAM baseline.
- **Native-Resolution Export Compositing:** Text layers are composited at the image's native resolution for individual exports, batch processing, and the Photoshop / Photopea bridges.

<details>
<summary><b>Previously introduced in v3.2.0</b></summary>

The v3.0.0-to-v3.2.0 evolution expanded mask controls and workflow options:

- **Expanded Toolkit:** Polygonal Lasso for precise geometric selections and Bucket Fill for filling the mask.
- **Canvas Controls:** Zoom with `Alt + Scroll`, pan the image, draw straight lines using `Shift + Click`, and dynamically resize the brush with `Alt + Right-Click Drag`.
- **Transparency Scanning (`T`):** Detect and mask transparent/alpha areas with a single keystroke.
- **Photopea Integration:** Send originals and cleaned pages to Photopea, the web-based editor, through the application bridge.
- **Linux Support:** Native Linux execution for the standard CPU edition.
- **Smart Queue UI:** Status indicators and padlocks show which pages are being processed in the background.
- **Mask Opacity Slider:** Change the visibility of the mask overlay without changing the underlying mask data.

</details>

---

## 💎 Core Engine Features

- **Resolution-Invariant Tiling:** The Dynamic ROI Engine uses Snap-to-8 reflection padding to process high-resolution images without downscaling the source image.
- **AI Core:** OCR-based text detection and an ONNX-based LaMa inpainting pipeline for scan restoration.
- **Hardware Options:** GPU and CPU packages are available. Package size and performance depend on the selected build, hardware, and installed runtime dependencies.

---

## 📸 Before & After Comparison

| Original Scan | AI Restored |
| :---: | :---: |
| ![Before 1](.github/assets/before_1.jpg) | ![After 1](.github/assets/after_1.jpg) |
| ![Before 2](.github/assets/before_2.jpg) | ![After 2](.github/assets/after_2.jpg) |

---

## 📦 Version Comparison: GPU vs. CPU

| Feature | ⚡ CUDA GPU Edition | ☁️ Standard CPU Edition |
| :--- | :--- | :--- |
| **Ideal For** | NVIDIA GPUs with a compatible CUDA runtime | Laptops and integrated graphics |
| **Package Size** | Approximately 900 MB (build dependent) | Approximately 260 MB (build dependent) |
| **Cleaning Speed** | Hardware and model dependent | Hardware and model dependent; the first run may take longer while the model loads |
| **Hardware** | Compatible NVIDIA GPU and CUDA dependencies | Modern x64 CPU |

---

## 🎨 Professional Studio Features

- **Batch Engine:** Process selected chapter pages in one workflow: load, scan, clean, and export.
- **Selection Toolkit:** Rectangular Selection, Lasso, Polygon, Bucket Fill, Brush, and Eraser tools for mask refinement.
- **Photoshop Bridge:** On supported Windows configurations, send cleaned pages to Adobe Photoshop.
- **Photopea Bridge:** Send page content to Photopea through its web workflow.
- **Integrated Help System:** Built-in usage instructions and shortcut reference.

---

## 📝 Translator Script Format

The **TRANSLATOR** workspace uses a plain UTF-8 `.txt` file. Click **Generate .TXT Template** to create a block for each image in Project Assets, fill in the dialogue, then select **Import .TXT & Queue in Layers**.

```text
### SERIES TITLE: My Series
### CHAPTER: 12

<translation>

Image 1 [001.jpg]
- First speech bubble
- Second bubble//with a manual line break

Image 2 [002.jpg]
-
-

</translation>
```

- Only text between `<translation>` and `</translation>` is read. Do not modify or delete these tags.
- Each `-` line represents one speech bubble or text box. Empty `-` lines are ignored and can be left on pages without dialogue.
- Use `//` for a manual line break inside a bubble.
- Lines beginning with `#` are comments and are ignored, as is content outside the translation tags.
- **Match pages by filename (default):** Put the exact filename in square brackets, such as `[001.jpg]`. Matching is case-insensitive and can fall back to the filename without its extension. Unmatched pages are reported after import. Disable filename matching to match strictly by image order (`Image 1`, `Image 2`, and so on).
- **Replace pending layers on import:** Replaces previously queued dialogue lines. Text already placed on the canvas is not removed.

Imported lines appear as `[ + ]` entries in **TYPESETTER → PAGE TEXT LAYERS**. Choose a font and style, then click an entry to place it; placed text appears as `[ ✓ ]`.

---

## ⌨️ Professional Shortcuts

| Key | Action |
| :--- | :--- |
| `O` | Run OCR text scan |
| `T` | Scan transparent areas |
| `C` | Execute AI cleaning / inpainting |
| `B` / `E` / `M` | Select Brush / Eraser / Move tools |
| `R` / `L` / `P` | Select Rectangle / Lasso / Polygon tools |
| `G` | Select Bucket Fill |
| `D` / `I` | Select Manual Cleaner / Color Picker |
| `Shift + Click` | Draw a straight line between points |
| `Double-Click` | Commit a polygon selection |
| `Alt + Right-Click Drag` | Resize the brush dynamically |
| `Alt + Left-Click` | Sample a page color while Manual Cleaner is active |
| `Ctrl + Scroll` | Change text font size (Typesetter) |
| `Ctrl + Shift + Scroll` | Rotate text (Typesetter) |
| Hold `Shift` while rotating | Snap rotation to 15° increments |
| Hold `Alt` | Temporarily switch between Brush and Eraser where supported |
| Hold `Space` | Temporarily pan / move the canvas |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo; applies to direct image painting in Manual Cleaner and to mask edits in mask tools |
| `Alt+Z` / `Alt+Shift+Z` | Undo / redo image-state actions, including AI cleaning |

---

## 🛠️ Technical Stack (For Developers)

- **Language:** Python 3.10, 3.11, and 3.12 (see the requirements files for the supported environment)
- **GUI:** PySide6 (Qt 6), with the Obsidian Dark theme
- **Image Processing:** OpenCV and NumPy
- **AI Inference:** ONNX Runtime with LaMa-based inpainting
- **Concurrency:** QThread-based workers and background processing to keep the interface responsive during AI tasks
- **Telemetry:** RAM and GPU information displayed through the application's system-monitoring utilities

---

## 🗺️ Roadmap: The Future of Manga Cleaner

### Python version

- **v3.4.0 (planned):** Community-contributed multi-language support through translation files.
- **v3.5.0 (under investigation):** Potential watermark-removal support using an AI model, subject to implementation feasibility and attribution to the model developer.

The Python roadmap may change if development of the C++ version progresses faster than expected.

### C++ version

- **v4.0.0 (in development):** Planned AMD GPU support through DirectML execution providers and other community-requested improvements.

---

## 📜 Community & Usage Policy

**Copyright © 2024-2026 NeTRuNNeRGLiTCH. All Rights Reserved.**

This project is built to empower the scanlation community. I want this tool to help you work faster and more professionally.

- **Profit from your Work:** You are 100% free to use this tool to clean manga for your scanlation groups, even if those groups accept donations or work on paid platforms. The output you create is yours.
- **Open for Learning:** You are welcome to study the source code, fork the repo, and modify it for your own personal use or to suggest improvements to this project.
- **Strict Commercial Restriction:** You are strictly prohibited from selling this software, its source code, or any modified versions of it. You cannot "re-skin" this app and put it behind a paywall.
- **Attribution:** While not required, a shout-out to this repo helps the project grow!

---

## 🚀 Running from Source

Running Manga Cleaner directly from the repository is the recommended method for Linux users with NVIDIA GPUs. A source environment can use CUDA/cuDNN libraries provided through Python packages without requiring a system-wide CUDA toolkit configuration, provided the installed versions are compatible.

### 1. Clone the Repository

```bash
git clone https://github.com/NeTRuNNeRGLiTCH/manga-cleaner.git
cd manga-cleaner
```

For a fork, replace the URL with your fork's URL and select the relevant branch.

### 2. Download the AI Models

Download `models.zip` from the latest project release and extract it into the repository root:

```text
manga-cleaner/
├── models/
├── src/
├── assets/
└── main.py
```

The archive is available on the project's [Releases page](https://github.com/NeTRuNNeRGLiTCH/manga-cleaner/releases).

### 3. Linux — NVIDIA GPU

Create a virtual environment and install the Linux GPU dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_linux_gpu.txt
```

Then launch the application:

```bash
python main.py
```

Manga Cleaner uses ONNX Runtime's `CUDAExecutionProvider` when it is available and compatible with the installed environment.

> **Recommended for Linux NVIDIA users:** Running from source may provide a simpler dependency environment than the packaged Linux GPU build and can allow ONNX Runtime to load compatible CUDA/cuDNN libraries installed through Python packages.

### 4. CPU / Other Platforms

For CPU-only usage, install the appropriate requirements file for your platform and launch the application:

```bash
python main.py
```

When CUDA is unavailable, the application can use the CPU execution provider.

---

## ⚙️ Development & Compilation (Source Only)

These instructions are intended for developers building distributable packages from source. Verify the spec file and requirements for the target platform before building.

### 1. Clone the Repository

```bash
git clone https://github.com/NeTRuNNeRGLiTCH/manga-cleaner.git
cd manga-cleaner
```

### 2. Windows Compilation

```cmd
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller MangaCleaner_CPU_clean.spec --noconfirm --clean
```

Copy the `models` directory into the generated application's expected location as required by the selected spec file.

### 3. Linux Compilation

The Linux build uses the relevant Linux spec file and requirements file. The following example shows a Docker-based environment; ensure that the spec filename and output directory match the build you intend to produce.

```bash
docker run --rm -v "$(pwd):/workspace" -w /workspace python:3.12-bookworm bash -c "
  apt-get update && apt-get install -y libgl1 libglib2.0-0 zip
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements_linux_gpu.txt pyinstaller
  pyinstaller --clean --noconfirm MangaCleaner_GPU_linux.spec
  chown -R $(id -u):$(id -g) dist/ build/
"
```

Copy the `models` directory into the generated application's expected location as required by the selected spec file.
