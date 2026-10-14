# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all
from importlib.util import find_spec

# NVIDIA CUDA 13 packages used by ONNX Runtime 1.29
nvidia_package_candidates = {
    'nvidia-cublas': ['nvidia.cublas', 'nvidia_cublas'],
    'nvidia-cuda-nvrtc': ['nvidia.cuda_nvrtc', 'nvidia_cuda_nvrtc'],
    'nvidia-cuda-runtime': ['nvidia.cuda_runtime', 'nvidia_cuda_runtime'],
    'nvidia-cudnn-cu13': ['nvidia.cudnn'],
    'nvidia-cufft': ['nvidia.cufft', 'nvidia_cufft'],
    'nvidia-curand': ['nvidia.curand', 'nvidia_curand'],
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
        ('src', 'src'),
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
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Keep CUDA/TensorRT providers!
# Only remove unused Qt components.
forbidden_keywords = [
    'libQt6OpenGL',
    'libQt6Pdf',
    'libQt6Qml',
    'libQt6Quick',
    'libQt6VirtualKeyboard',
    'translations',
]

a.binaries = [
    b for b in a.binaries
    if not any(k.lower() in b[0].lower() for k in forbidden_keywords)
]

a.datas = [
    d for d in a.datas
    if not any(k.lower() in d[0].lower() for k in forbidden_keywords)
]

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