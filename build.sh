#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

usage() {
    cat <<'EOF'
Usage: bash build.sh [cpu|gpu|all]

Build Linux CPU, Linux GPU, or both native targets. If no target is supplied,
an interactive menu is shown. Separate virtual environments are created under
build/ for CPU and GPU dependencies.

Set PYTHON to select a specific Python 3.12 interpreter, for example:
  PYTHON=python3.12 bash build.sh cpu
EOF
}

build_variant() {
    local variant="$1"
    local target_id requirements_file environment_dir python_path

    case "$variant" in
        cpu)
            target_id="linux-cpu"
            requirements_file="$ROOT_DIR/requirements.txt"
            ;;
        gpu)
            target_id="linux-gpu"
            requirements_file="$ROOT_DIR/requirements_linux.txt"
            ;;
        *)
            echo "[ERROR] Unknown Linux build variant: $variant" >&2
            return 2
            ;;
    esac

    if [[ ! -f "$requirements_file" ]]; then
        echo "[ERROR] Requirements file not found: $requirements_file" >&2
        return 2
    fi

    environment_dir="$ROOT_DIR/build/env-linux-$variant"
    python_path="$environment_dir/bin/python"

    if [[ ! -x "$python_path" ]]; then
        echo "Creating Linux $variant build environment at $environment_dir"
        "$PYTHON_BIN" -m venv "$environment_dir"
    fi

    echo "Installing/updating dependencies for Linux $variant..."
    "$python_path" -m pip install --upgrade pip
    "$python_path" -m pip install -r "$requirements_file" "pyinstaller==6.18.0"

    echo "Starting the $target_id build..."
    "$python_path" "$ROOT_DIR/build.py" --target "$target_id"
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

if [[ "${OSTYPE:-}" != linux* ]]; then
    echo "[ERROR] build.sh must run in a Linux shell. Use build.py on Windows." >&2
    exit 2
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "[ERROR] Python interpreter not found: $PYTHON_BIN" >&2
    echo "Install Python 3.12 and its venv package, or set PYTHON=/path/to/python3.12." >&2
    exit 2
fi

if ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'; then
    echo "[ERROR] Python 3.12 is required by the current Linux build configuration." >&2
    echo "Set PYTHON to a Python 3.12 interpreter, for example: PYTHON=python3.12 bash build.sh cpu" >&2
    exit 2
fi

selection="${1:-}"
if [[ -z "$selection" ]]; then
    echo "Linux build targets:"
    echo "  1. CPU"
    echo "  2. GPU"
    echo "  A. Build both"
    echo "  Q. Quit"
    read -r -p "Selection: " selection
    case "${selection,,}" in
        1) selection="cpu" ;;
        2) selection="gpu" ;;
        a) selection="all" ;;
        q) echo "No build selected."; exit 0 ;;
        *) echo "[ERROR] Choose 1, 2, A, or Q." >&2; exit 2 ;;
    esac
fi

case "$selection" in
    cpu)
        build_variant cpu
        ;;
    gpu)
        build_variant gpu
        ;;
    all)
        build_variant cpu
        build_variant gpu
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
