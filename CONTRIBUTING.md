# Contributing to Manga Cleaner Studio

Thank you for your interest in contributing to **Manga Cleaner Studio**! We welcome bug fixes, architecture optimizations, translation models, and new features from the scanlation and developer communities.

---

## 📜 Licensing Notice (Apache 2.0)

Starting with **v3.3.2**, Manga Cleaner Studio is licensed under the **Apache License 2.0**.

By submitting a Pull Request, you agree that your contributions will be licensed under the Apache 2.0 terms. Key implications:
* **Patent Grant:** Express grant of patent rights from contributors to users.
* **Open Source Continuity:** Ensures the core restoration suite remains free and accessible to the scanlation community while protecting creators against patent claims.
* **State Changes:** Any modified files must carry prominent notices stating that you changed the files.

---

## 🛠️ Development Setup

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone [https://github.com/NeTRuNNeRGLiTCH/manga-cleaner.git](https://github.com/NeTRuNNeRGLiTCH/manga-cleaner.git)
   cd manga-cleaner
3. **Create and activate a virtual environment:**
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate

```


4. **Install runtime dependencies:**
```bash
pip install -r requirements.txt
```


*(For Linux GPU development, use `pip install -r requirements_linux_gpu.txt`)*

5. **Download the models:** Extract `models.zip` into the root repository directory prior to launching.

---

## ⚙️ Development & Compilation (Packaging)

These instructions are intended for developers compiling standalone binary releases from source. Verify that your platform dependencies match the target build.

### 1. Windows Compilation (PyInstaller)

```cmd
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller MangaCleaner_CPU_clean.spec --noconfirm --clean

```

Copy the `models/` directory into the generated application's expected folder as configured in the spec file.

### 2. Linux Compilation (Docker)

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

---

## 🌿 Git Branching Strategy

To keep the repository clean and avoid merge conflicts with upstream:

* **`main`**: Production-ready code matching active public releases. Do **not** commit directly to `main`.
* **Feature Branches**: Branch off from `main` using descriptive names:
* `feat/<feature-name>` for new workspaces, UI modules, or AI pipelines.
* `fix/<bug-description>` for bug patches and stability adjustments.
* `refactor/<module>` for performance refactoring or cleanups.

```bash
git checkout main
git pull upstream main
git checkout -b fix/text-gizmo-sensitivity

```

---

## 📐 Coding Standards & Guidelines

### 1. Architecture & Separation of Concerns

* **`src/frontend/`**: PySide6 GUI views, canvas rendering, gizmos, and interactive widgets. Keep heavy computation out of the GUI thread.
* **`src/backend/`**: File parsers, AI model workers (`QThread`), export engines, and external bridges (Photoshop/Photopea).
* **`src/utils/`**: Configuration, paths, logging, and history management.

### 2. Path Resolution & Environment Integrity

* Always reference paths via `src.utils.paths.Paths` (`Paths.CACHE`, `Paths.TRANSLATIONS`, `Paths.MODELS`, etc.).
* **Never hardcode relative paths** like `./cache` or write directly inside `_internal/`.
* Verify that temporary files or user-generated scripts reside in directories ignored by `.gitignore`.

### 3. Unicode & Multi-Language Compatibility

* Enforce **NFC normalization** (`unicodedata.normalize("NFC", text)`) when handling image filenames or dialogue strings to ensure consistent cross-platform behavior between Windows, Linux, and macOS.

### 4. Code Quality & Formatting

* Write clean, self-documenting code.
* Keep internal code comments and docstrings in **English**.
* Clean up redundant debug print statements before opening a PR (`src.utils.logger` should be used for diagnostics).

---

## 🏷️ Versioning Scheme & Policy (SemVer)

Manga Cleaner Studio follows a structured versioning format: **`v<MAJOR>.<MINOR>.<PATCH>`** (e.g., `v3.3.3`).

When submitting bug fixes or new features, update `VERSION` in `src/utils/config.py` according to these rules:

1. **PATCH (3rd number, 0–9):**
   * **When to bump:** Bug fixes, stability patches, minor UI refinements, or sensitivity corrections (e.g., `v3.3.2` ➔ `v3.3.3`).
   * Bumping this number leaves the `MAJOR` and `MINOR` numbers untouched.

2. **MINOR (2nd number, 0–9):**
   * **When to bump:** Major feature releases, new Studio workspaces, broad platform integrations, or multi-language system additions (e.g., upcoming `v3.4.0`).
   * **Reset rule:** Incrementing `MINOR` automatically resets the `PATCH` number to `0` (e.g., `v3.3.3` ➔ `v3.4.0`).

3. **MAJOR (1st number):**
   * Reserved for core engine rewrites, breaking API changes, or complete architectural transitions (e.g., moving from Python `v3.x` to the planned C++ / DirectML `v4.0.0` engine).

---

## 🚀 Submitting a Pull Request (PR)

1. **Commit your changes**: Write clear, imperative commit messages:
```bash
git commit -m "fix(canvas): stabilize text transform gizmo center and sensitivity"

```


2. **Push to your fork:**
```bash
git push -u origin <your-branch-name>

```


3. **Open the Pull Request:**
* Target the upstream repository's default branch.
* Provide a concise description of the problem solved and testing steps performed.
* Include screenshots or recordings if the change modifies the interface or visual tools.



---

## 💬 Community & Questions

If you encounter bugs, have suggestions, or want to discuss upcoming roadmap milestones, please open an **Issue** on GitHub.