"""Build a selected native Manga Cleaner Studio PyInstaller target."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import site
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYINSTALLER_VERSION = "6.18.0"

TARGETS = {
    "windows-cpu": {
        "label": "Windows CPU",
        "platform": "win32",
        "spec": "MangaCleaner_CPU.spec",
        "bundle": "MangaCleaner_CPU",
    },
    "windows-cpu-clean": {
        "label": "Windows CPU Clean",
        "platform": "win32",
        "spec": "MangaCleaner_CPU_clean.spec",
        "bundle": "MangaCleaner_CPU",
    },
    "windows-gpu": {
        "label": "Windows GPU",
        "platform": "win32",
        "spec": "MangaCleaner_GPU.spec",
        "bundle": "MangaCleaner_GPU",
    },
    "linux-cpu": {
        "label": "Linux CPU",
        "platform": "linux",
        "spec": "MangaCleaner_CPU_linux.spec",
        "bundle": "MangaCleaner_CPU",
    },
    "linux-gpu": {
        "label": "Linux GPU",
        "platform": "linux",
        "spec": "MangaCleaner_GPU_linux.spec",
        "bundle": "MangaCleaner_GPU",
    },
}


def current_platform():
    """Return the platform family supported by this build script."""
    if sys.platform == "win32":
        return "win32"
    if sys.platform.startswith("linux"):
        return "linux"
    return None


def available_targets():
    """Return targets that can be built natively on this operating system."""
    platform = current_platform()
    return [
        (target_id, target)
        for target_id, target in TARGETS.items()
        if target["platform"] == platform
    ]


# Essential CUDA and cuDNN DLLs required for ONNX Runtime GPU inference (CNN / Inpainting / OCR)
ESSENTIAL_GPU_DLLS = {
    "cublas64_12.dll",
    "cublasLt64_12.dll",
    "cudart64_12.dll",
    "cufft64_11.dll",
    "cudnn64_9.dll",
    "cudnn_cnn64_9.dll",
    "cudnn_ops64_9.dll",
    "cudnn_heuristic64_9.dll",
    "cudnn_graph64_9.dll",
    "cudnn_engines_runtime_compiled64_9.dll",
    "cudnn_engines_tensor_ir64_9.dll",
    "cudnn_engines_precompiled64_9.dll",
    "cudnn_ext64_9.dll",
}


def collect_windows_gpu_dlls(bundle_dir: Path):
    """Copy essential NVIDIA CUDA and cuDNN DLLs beside the executable and into _internal."""
    internal_dir = bundle_dir / "_internal"
    if not internal_dir.is_dir():
        raise RuntimeError(
            f"PyInstaller's bundle support directory was not found: {internal_dir}"
        )

    found_dlls = {}
    for package_dir in site.getsitepackages():
        nvidia_dir = Path(package_dir) / "nvidia"
        if nvidia_dir.is_dir():
            for dll_path in nvidia_dir.rglob("*.dll"):
                found_dlls[dll_path.name.lower()] = dll_path

    if not found_dlls:
        raise RuntimeError(
            "No NVIDIA CUDA DLLs were found in this Python environment. "
            "Install the Windows GPU dependencies listed in README.md, then retry."
        )

    # Filter to essential DLLs, discarding bloat (NVRTC, cuRAND, cuDNN Adv, JIT linkers)
    copied_count = 0
    for essential_name in ESSENTIAL_GPU_DLLS:
        source = found_dlls.get(essential_name.lower())
        if source and source.is_file():
            # Place directly beside MangaCleaner_GPU.exe
            shutil.copy2(source, bundle_dir / source.name)
            # Remove from _internal if already present to avoid duplicating 2GB of binaries
            internal_copy = internal_dir / source.name
            if internal_copy.exists():
                internal_copy.unlink()
            copied_count += 1
        else:
            print(f"[WARN] Essential GPU DLL not found: {essential_name}")

    print(
        f"Placed {copied_count} essential CUDA/cuDNN DLL(s) directly beside the application executable "
        f"in {bundle_dir}"
    )


def build_target(target_id, target, accept_overwrite=False):
    """Run PyInstaller for one target and return whether it succeeded."""
    spec_path = ROOT / target["spec"]
    if not spec_path.is_file():
        print(f"[ERROR] Spec file not found: {spec_path}")
        return False

    dist_dir = ROOT / "dist" / target_id
    work_dir = ROOT / "build" / target_id
    bundle_dir = dist_dir / target["bundle"]

    if bundle_dir.exists() and not accept_overwrite:
        answer = input(f"Replace existing output at {bundle_dir}? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print(f"[SKIP] Kept existing {target['label']} output.")
            return True

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec_path),
        "--noconfirm",
        "--clean",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
    ]

    print(f"\nBuilding {target['label']} with {target['spec']}...")
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        print(f"[ERROR] {target['label']} build failed (exit code {result.returncode}).")
        return False

    # Move src directory directly beside the executable
    src_source = ROOT / "src"
    src_target = bundle_dir / "src"
    if src_source.is_dir():
        if src_target.exists():
            shutil.rmtree(src_target)
        shutil.copytree(src_source, src_target)
        internal_src = bundle_dir / "_internal" / "src"
        if internal_src.exists():
            shutil.rmtree(internal_src)
        print(f"Placed src/ directly beside the executable in {bundle_dir}")

    # Ensure locales directory is also beside the executable for user customizations
    locales_source = ROOT / "locales"
    locales_target = bundle_dir / "locales"
    if locales_source.is_dir():
        if locales_target.exists():
            shutil.rmtree(locales_target)
        shutil.copytree(locales_source, locales_target)

    if target_id == "windows-gpu":
        try:
            collect_windows_gpu_dlls(bundle_dir)
        except (OSError, RuntimeError) as exc:
            print(f"[ERROR] Windows GPU runtime setup failed: {exc}")
            return False

    print(f"[OK] {target['label']} build completed: {bundle_dir}")
    return True


def ensure_pyinstaller():
    """Install the pinned PyInstaller release into the active Python environment if needed."""
    if importlib.util.find_spec("PyInstaller") is not None:
        return True

    print(f"PyInstaller {PYINSTALLER_VERSION} is missing from this Python environment.")
    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if pip_check.returncode != 0:
        print("pip is unavailable; trying to enable it with Python's ensurepip...")
        pip_bootstrap = subprocess.run(
            [sys.executable, "-m", "ensurepip", "--upgrade"],
            cwd=ROOT,
            check=False,
        )
        if pip_bootstrap.returncode != 0:
            print("[ERROR] Could not enable pip for the active Python environment.")
            return False

    print(f"Installing PyInstaller {PYINSTALLER_VERSION} into {sys.executable}...")
    install = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            f"pyinstaller=={PYINSTALLER_VERSION}",
        ],
        cwd=ROOT,
        check=False,
    )
    if install.returncode != 0:
        print(
            "[ERROR] PyInstaller installation failed. Check your network connection "
            "and pip configuration, then retry."
        )
        return False

    if importlib.util.find_spec("PyInstaller") is None:
        print("[ERROR] Installation completed, but PyInstaller is still unavailable.")
        return False

    print("PyInstaller is ready.")
    return True


def choose_targets(targets):
    """Show a menu and return the selected target identifiers."""
    print("\nManga Cleaner Studio — build selector")
    print("Choose a target for this operating system:")
    for index, (target_id, target) in enumerate(targets, start=1):
        print(f"  {index}. {target['label']} ({target['spec']})")
    print("  A. Build all listed targets")
    print("  Q. Quit")

    while True:
        choice = input("Selection: ").strip().lower()
        if choice == "q":
            return []
        if choice == "a":
            return [target_id for target_id, _ in targets]
        if choice.isdigit() and 1 <= int(choice) <= len(targets):
            return [targets[int(choice) - 1][0]]
        print("Choose a listed number, A, or Q.")


def main():
    """Parse build options, select compatible targets, and run the builds."""
    parser = argparse.ArgumentParser(
        description="Select and build a native Manga Cleaner Studio PyInstaller target."
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--target", choices=TARGETS, help="Build one named target.")
    selection.add_argument("--all", action="store_true", help="Build all targets for this OS.")
    selection.add_argument("--list", action="store_true", help="List targets for this OS.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Replace existing output without asking (useful for automation).",
    )
    args = parser.parse_args()

    targets = available_targets()
    platform = current_platform()
    if platform is None:
        print("[ERROR] Only native Windows and Linux builds are configured.")
        return 2

    if not targets:
        print(f"[ERROR] No build targets are configured for {platform}.")
        return 2

    if args.list:
        for target_id, target in targets:
            print(f"{target_id}: {target['label']} ({target['spec']})")
        return 0

    if args.target:
        target = TARGETS[args.target]
        if target["platform"] != platform:
            print(
                f"[ERROR] {target['label']} must be built on its native platform. "
                "PyInstaller does not cross-compile Windows and Linux applications."
            )
            return 2
        selected = [args.target]
    elif args.all:
        selected = [target_id for target_id, _ in targets]
    else:
        selected = choose_targets(targets)

    if not selected:
        print("No build selected.")
        return 0

    if not ensure_pyinstaller():
        return 2

    try:
        return 0 if all(
            build_target(target_id, TARGETS[target_id], accept_overwrite=args.yes)
            for target_id in selected
        ) else 1
    except KeyboardInterrupt:
        print("\nBuild selection interrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
