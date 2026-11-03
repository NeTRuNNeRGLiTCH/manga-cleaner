# -*- mode: python ; coding: utf-8 -*-

import os

# 1. PYTHON MODULE EXCLUDES
block_list = [
    'tkinter', 'unittest', 'pydoc', 'xmlrpc', 
    'matplotlib', 'scipy', 'PyQt5', 'PyQt6', 'IPython',
    'win32com', 'winreg', 'pywin32'
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('src', 'src'), ('locales', 'locales')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=block_list,
    noarchive=False,
    optimize=1, # Preserves docstrings for NumPy
)

# 2. LINUX SHARED LIBRARY (.so) FILTER
forbidden_keywords = [
    # Strip ONNX GPU Providers for CPU build
    'libonnxruntime_providers_cuda.so',
    'libonnxruntime_providers_tensorrt.so',
    
    # Strip Heavy Unused PySide6 Modules
    'libQt6OpenGL',
    'libQt6Pdf',
    'libQt6Qml',
    'libQt6Quick',
    'libQt6VirtualKeyboard',
    'translations',
]

# Filter Binaries (.so files)
filtered_binaries = []
for b in a.binaries:
    dest_path = b[0].lower()
    if not any(kw.lower() in dest_path for kw in forbidden_keywords):
        filtered_binaries.append(b)
a.binaries = filtered_binaries

# Filter Datas (.qm translations, assets, etc.)
filtered_datas = []
for d in a.datas:
    dest_path = d[0].lower()
    if not any(kw.lower() in dest_path for kw in forbidden_keywords):
        filtered_datas.append(d)
a.datas = filtered_datas

# ---------------------------------------------------------

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MangaCleaner_CPU',
    debug=False,
    bootloader_ignore_signals=False,
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
    name='MangaCleaner_CPU',
)
