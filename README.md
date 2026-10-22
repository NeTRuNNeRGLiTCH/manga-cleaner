# 🌌 MANGA CLEANER STUDIO v3.3.0: The Workspaces & Typesetting Update
**High-Fidelity AI-Powered Scanlation Restoration Suite**

[![Download v3.3.0](https://img.shields.io/badge/DOWNLOAD-v3.3.0-00d4ff?style=for-the-badge&logo=github)](https://github.com/NeTRuNNeRGLiTCH/manga-cleaner/releases)
[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Downloads](https://img.shields.io/github/downloads/NeTRuNNeRGLiTCH/manga-cleaner/total?color=blue)](https://github.com/NeTRuNNeRGLiTCH/manga-cleaner/releases)

Building upon the modular "Studio" engine introduced in v3.0.0 and the toolkit expansion of v3.2.0, **Manga Cleaner Studio v3.3.0** grows from a cleaning tool into a complete scanlation studio. The interface now has four dedicated workspaces — **Cleaner**, **Typesetter**, **Stitcher** and **Translator** — so you can go from raw scans to a finished chapter without leaving the app.

---

## 🖥️ Studio Preview (v3.3.0 UI)
![Manga Cleaner v3.3 UI](.github/assets/ui.png)
*Featuring the Obsidian Dark Theme, the two-column tool layout, live file-queue locking, and the new four-workspace switcher (Cleaner · Typesetter · Stitcher · Translator).*

Note: The screenshot was taken from a beta version, The UI doesn't change.

---
## 🎓 Installation & Setup Tutorial

For the recommended installation and setup instructions, see the **[Running from Source](#-running-from-source)** section below.

This includes instructions for:

* Linux users with NVIDIA GPUs — **recommended**
* CPU-only installations
* Downloading and setting up the required AI models
* Running Manga Cleaner directly from the repository

### 🎥 Video Tutorial

Prefer a visual walkthrough? You can follow the video tutorial instead:

[![Watch the Video Tutorial](https://img.youtube.com/vi/9psnwpJG3aE/hqdefault.jpg)](https://www.youtube.com/embed/9psnwpJG3aE)  

The video provides a step-by-step walkthrough of setting up and using Manga Cleaner.

Note: The video was recorded in version 3.2.0 (Manga Cleaner).

---

## ✨ What's New in v3.3.2 Beta

Everything that happens after the cleaning step — translating, typesetting and stitching — now lives in the same window:

*   **Four Workspaces:** Switch between **CLEANER**, **TYPESETTER**, **STITCHER** and **TRANSLATOR** from the 2×2 selector at the top of the right panel. Each workspace only shows the controls it needs.
*   **Photoshop-Style Typesetter:** Add text directly on the page with a full transform gizmo — corner nodes scale the font, side nodes resize the text box with automatic word wrap, and the top node rotates freely (hold `Shift` to snap every 15°). Includes bold, italic, centering, an **Angle** field, a `0°` reset and **Fit Box** auto-width.
*   **Vector Outside Stroke:** Text can use a true `Stroke (Outside)` mode with adjustable width and opacity. The clean fill is drawn on top of the stroke, so the outline never eats into the letters. Toggle it with the single **Mode: Normal / Stroke (Outside)** button. Pure color swatches and a one-click White/Black swap (`⇄`) keep styling fast.
*   **Font Manager:** Live search by font name or alias, a **★ Only** favorites filter, one-click favorites, and custom aliases (`✎`) that keep the original system name visible (`Alias [Family]`). Everything is saved automatically to `font_presets.json`.
*   **Page Text Layers:** A live list of every text box on the current page. Click an entry to select it and center the view on it. Queued script lines appear in the same list.
*   **Manual Cleaner (`MANUAL` + `PICKER`):** Paint directly onto the page for the touch-ups the AI misses. Draw straight lines with `Shift + Click`, resize the brush with `Alt + Right-Click Drag`, and sample any pixel with `PICKER` (or `Alt + Left-Click` while painting). A color swatch and a quick `White` reset are included.
*   **Smart Undo:** While `MANUAL` or `PICKER` is active, `Ctrl+Z` / `Ctrl+Shift+Z` undo and redo the painted image directly, so a stray shortcut can't wipe your page. With every other tool they keep undoing mask edits.
*   **Translator Workspace:** Generate a `.txt` script template that matches the pages you loaded, hand it to your translator, then import the result. Dialogues are matched to pages by `[filename]` or by image order, and pages that couldn't be matched are reported. Lines are queued instead of rendered, so importing uses **no extra RAM**. Click a queued `[ + ]` line (or click directly on a speech bubble on the canvas) and the text is created on the spot with your currently selected font. See [Translator Script Format](#-translator-script-format).
*   **Lossless Stitcher:** Join pages vertically with no seams, keeping your cleaning edits and text layers. Group pages manually (`From → To`), by pages per file, or by a maximum number of output files (for example, reduce 150 pages to 100 files). Optional **Max Height** protection (can be synced with Max Tile Size) and export to `PNG` or `JPG (100% quality, 4:4:4)`.
*   **1:1 Export Compositing:** Text layers are flattened at native resolution for single exports, the Batch Engine and the Photoshop / Photopea bridges.

<details>
<summary><b>Previously in v3.2.0</b></summary>

<br>

The evolution from v3.0.0 to v3.2.0 focused heavily on giving you granular control over your masks and workflow:

*   **Expanded Toolkit:** We've added a **Polygonal Lasso** for precise geometric selections and a **Bucket Fill** tool that intelligently analyzes your mask layer. 
*   **Pro Canvas Controls:** Navigate like a pro. Zoom in/out with `Alt + Scroll`, pan the image smoothly, draw perfectly straight lines using `Shift + Click`, and dynamically resize your brush on the fly with `Alt + Right-Click Drag`.
*   **Transparency Scanning [T]:** Instantly detect and mask transparent/alpha areas with a single keystroke.
*   **Photopea Integration:** Don't have Photoshop? v3.2.0 introduced a seamless bridge to **Photopea** (the free web editor). Cleaned pages and originals are injected directly into your browser as layered documents.
*   **Linux Support:** The standard CPU edition now officially supports native execution on Linux environments!
*   **Smart Queue UI:** The file list now displays real-time status icons and padlocks, so you always know exactly which pages the background AI is actively processing.
*   **Mask Opacity Slider:** Dynamically adjust the visibility of your red mask overlay without altering the underlying data.

</details>

---

## 💎 Core Engine Features

*   **Resolution-Invariant Tiling:** Our Dynamic ROI Engine utilizes "Snap-to-8" reflection padding to process ultra-high 4K+ resolutions without downscaling. The output remains 1:1 perfectly sharp with no Gaussian blurring at the seams.
*   **Advanced AI Core:** High-frequency heatmap OCR for pinpoint text detection in Japanese, Korean, English and Chinese, paired with an ONNX-quantized LaMa core for ultra-fast, seamless inpainting.
*   **Hardware Optimized:** The GPU package provides real-time cleaning for NVIDIA devices (~900MB), while the Ultra-Lite CPU edition (~260MB) is perfectly pruned for laptops and integrated graphics.

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
| **Ideal For** | High-end NVIDIA Gaming PCs | Laptops & Integrated Graphics |
| **Package Size** | ~900MB (Optimized) | ~260MB (Ultra-Lite) |
| **Cleaning Speed** | Instant / Real-time | 3-8 seconds per page | (takes time to load model first)
| **Hardware** | NVIDIA GPU (CUDA Required) | Any modern x64 Processor |

---

## 🎨 Professional Studio Features
*   **Batch Engine:** Process entire chapters in one click. Load -> Auto-Scan -> AI Clean -> Export.
*   **Selection Toolkit:** Added professional **Rectangular Selection** and **Lasso Tools** for manual mask refinement.
*   **Photoshop® Bridge:** Direct COM Interop. Cleaned pages are injected directly into Adobe Photoshop as layered documents.
*   **Integrated Help System:** A built-in manual and shortcut legend for a zero-friction learning curve.

---

## 📝 Translator Script Format

The **TRANSLATOR** workspace reads a plain UTF-8 `.txt` file. Click **Generate .TXT Template** to create one with a block for every image loaded in Project Assets, fill in the dialogues, then use **Import .TXT & Queue in Layers**.

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

*   Only text between `<translation>` and `</translation>` is read. Do not modify or delete the tags.
*   Each `-` line is one speech bubble or text box on that page. Empty `-` lines are ignored, so you can leave them on pages without text.
*   Use `//` for a manual line break inside a bubble.
*   Lines starting with `#` are comments and are ignored, as is anything outside the tags.
*   **Match pages by [filename] brackets** (default): dialogues go to the file named in the brackets. The match ignores letter case and falls back to the name without its extension. Pages that can't be matched are listed after the import. Uncheck the option to match strictly by image order (`Image 1`, `Image 2`, …), ignoring the brackets.
*   **Replace existing pending layers on import** replaces previously queued lines. Text you have already placed on the canvas is never touched.

Imported lines show up as `[ + ]` in **TYPESETTER → PAGE TEXT LAYERS**. Pick your font and style, then click a line to place it; placed text switches to `[ ✓ ]`.

---

## ⌨️ Professional Shortcuts

Master the studio workflow with these refined v3.3.2 keybinds:

| Key | Action |
| :--- | :--- |
| `[O]` | Auto-Detect Text Bubbles (OCR Scan) |
| `[T]` | Auto-Detect Transparent Areas |
| `[C]` | Execute AI Clean (Inpainting) |
| `[B] / [E] / [M]` | Equip Brush / Eraser / Move Tools |
| `[R] / [L] / [P]` | Equip Rect / Lasso / Poly Tools |
| `[G]` | Equip Bucket Fill Tool |
| `[D] / [I]` | Equip Manual Cleaner / Color Picker |
| `[Shift] + Click` | Draw a perfectly straight line between points |
| `Double-Click` | Commit Polygonal Selection |
| `Alt + Right-Click Drag` | Dynamically Resize Brush (Left: Smaller, Right: Bigger) |
| `Alt + Left-Click` | Sample a color from the page (while Manual Cleaner is active) |
| `Ctrl + Scroll` | Change text font size (Typesetter) |
| `Ctrl + Shift + Scroll` | Rotate text (Typesetter) |
| `Hold [Shift]` while rotating | Snap text rotation to 15° steps |
| `Hold [Alt]` | Temporary Erase Mode (for Brush, Rect, Lasso, Poly, Bucket) |
| `Hold [Space]` | Quick Toggle Pan/Move Image |
| `[Ctrl+Z] / [Ctrl+Shift+Z]` | Undo / Redo Manual Mask Painting (or the painted image directly while Manual Cleaner / Picker is active) |
| `[Alt+Z] / [Alt+Shift+Z]`| Undo / Redo AI Clean (Image State) |

---

## 🛠️ Technical Stack (For Developers)
*   **Language:** Python 3.12.7 (Strict OOP Architecture)
*   **GUI:** PySide6 (Qt6) with Obsidian Dark styling.
*   **Processing:** OpenCV 4.11 + NumPy 1.26.
*   **Async Logic:** Multi-threaded QThread workers to maintain 60FPS UI responsiveness during AI tasks.
*   **Telemetery:** Real-time RAM and VRAM monitoring via `psutil` and `onnxruntime` provider telemetry.

---

## 🗺️ Roadmap: The Future of Manga Cleaner

Python version
*   **v3.4.0 (Planned):** **multi-language support** via translation files created by the community
*   **v3.5.0 (Planned/under investigation):** **Marklees** Watermark removal by an AI model created by another developer (credit will be given if possible)

Version 3.5.0 will likely be the final version for Python, in the event that the C++ version surpasses it.

C++ version 
*   **v4.0.0 (in development):** **AMD GPU Support** via DirectML Execution Providers and some of the community suggestions

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

Running Manga Cleaner Studio directly from the repository is the **recommended method for Linux users with NVIDIA GPUs**. The source build allows ONNX Runtime to use the CUDA libraries provided through Python packages without requiring a system-wide CUDA toolkit configuration.

### 1. Clone the Repository

```bash
git clone https://github.com/NeTRuNNeRGLiTCH/manga-cleaner.git
cd manga-cleaner
```

### 2. Download the AI Models

Download `models.zip` from the latest release and extract it into the repository root:

```text
manga-cleaner/
├── models/
├── src/
├── assets/
└── main.py
```

The `models.zip` file is available in the project's [Releases](https://github.com/NeTRuNNeRGLiTCH/manga-cleaner/releases).

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

Manga Cleaner will automatically use the NVIDIA GPU through ONNX Runtime's `CUDAExecutionProvider` when available.

> **Recommended for Linux NVIDIA users:** Running directly from source is currently preferred over the packaged Linux GPU build. It provides a simpler dependency environment and allows the CUDA/cuDNN libraries installed through pip to be loaded directly by ONNX Runtime.

### 4. CPU / Other Platforms

For CPU-only usage, use the appropriate platform requirements and launch the application normally:

```bash
python main.py
```

The application will fall back to the CPU execution provider when CUDA is unavailable.

---

## ⚙️ Development & Compilation (Source Only)

The following instructions are intended for developers who want to create distributable builds from the source.

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

cp -R .\models\ .\dist\MangaCleaner_CPU\models
```

### 3. Linux Compilation

The Linux GPU build uses `MangaCleaner_GPU_linux.spec` instead and currently supports NVIDIA GPUs with CUDA.

```bash
docker run --rm -v $(pwd):/workspace -w /workspace python:3.12-bookworm bash -c "

  apt-get update && apt-get install -y libgl1 libglib2.0-0 zip

  python -m venv venv

  source venv/bin/activate

  pip install -r requirements_linux_gpu.txt pyinstaller

  pyinstaller --clean --noconfirm MangaCleaner_CPU_linux.spec

  chown -R $(id -u):$(id -g) dist/ build/

"

cp -r ./models/ ./dist/MangaCleaner_GPU/models/
```