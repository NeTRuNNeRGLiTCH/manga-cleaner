# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all
from importlib.util import find_spec

# 1. PYTHON MODULE EXCLUDES
block_list = [
    'tkinter', 'unittest', 'pydoc', 'xmlrpc', 
    'matplotlib', 'scipy', 'PyQt5', 'PyQt6', 'IPython',
    'win32com', 'winreg', 'pywin32'
]

# NVIDIA CUDA packages used by ONNX Runtime
nvidia_package_candidates = {
    'nvidia-cublas': ['nvidia.cublas', 'nvidia_cublas'],
    'nvidia-cuda-nvrtc': ['nvidia.cuda_nvrtc', 'nvidia_cuda_nvrtc'],
    'nvidia-cuda-runtime': ['nvidia.cuda_runtime', 'nvidia_cuda_runtime'],
    'nvidia-cudnn': ['nvidia.cudnn', 'nvidia_cudnn'],
    'nvidia-cufft': ['nvidia.cufft', 'nvidia_cufft'],
    'nvidia-nvjitlink': ['nvidia.nvjitlink', 'nvidia_nvjitlink'],
}

nvidia_binaries = []
nvidia_datas = []
nvidia_hiddenimports = []
missing_nvidia_packages = []

for dependency_name, module_candidates in nvidia_package_candidates.items():
    collected = False
    for package in module_candidates:
        if find_spec(package) is None:
            continue
        try:
            binaries, datas, hiddenimports = collect_all(package)
            nvidia_binaries.extend(binaries)
            nvidia_datas.extend(datas)
            nvidia_hiddenimports.extend(hiddenimports)
            collected = True
            break
        except Exception as exc:
            missing_nvidia_packages.append(f"{dependency_name} via {package}: {exc}")
            collected = True
            break
    if not collected:
        missing_nvidia_packages.append(
            f"{dependency_name}: module not found ({', '.join(module_candidates)})"
        )

if missing_nvidia_packages:
    raise RuntimeError(
        "Missing required NVIDIA packages for Linux GPU build:\n"
        + "\n".join(missing_nvidia_packages)
    )


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=nvidia_binaries,
    datas=[
        ('assets', 'assets'),
        ('locales', 'locales'),
    ] + nvidia_datas,
    hiddenimports=[
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi.onnxruntime_pybind11_state',
        'PySide6.QtSvg',
    ] + nvidia_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=block_list,
    noarchive=False,
    optimize=1,
)

# 2. BLOAT FILTER
forbidden_keywords = [
    # Strip TensorRT provider (saves ~30MB and avoids missing TensorRT error)
    'libonnxruntime_providers_tensorrt',
    
    # Strip Heavy Unused PySide6 Modules
    'libqt6opengl',
    'libqt6pdf',
    'libqt6qml',
    'libqt6quick',
    'libqt6virtualkeyboard',
    'translations',

    # Strip Unused CUDA / cuDNN bloat
    'libcudnn_adv',       # RNN / Attention module (~250MB)
    'libcurand',          # Random number generator (~80MB)
    'libnvblas',          # NVBLAS (~10MB)
]

filtered_binaries = []
for b in a.binaries:
    dest_path = b[0].lower()
    if not any(kw.lower() in dest_path for kw in forbidden_keywords):
        filtered_binaries.append(b)
a.binaries = filtered_binaries

filtered_datas = []
for d in a.datas:
    dest_path = d[0].lower()
    # Strip development headers, cmake scripts, and pkgconfig
    if any(dest_path.endswith(ext) for ext in ('.h', '.hpp', '.cmake', '.pc', '.a')):
        continue
    if not any(kw.lower() in dest_path for kw in forbidden_keywords):
        filtered_datas.append(d)
a.datas = filtered_datas

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MangaCleaner_GPU',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MangaCleaner_GPU',
)
