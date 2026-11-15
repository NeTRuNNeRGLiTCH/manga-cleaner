# -*- mode: python ; coding: utf-8 -*-

# 1. PYTHON EXCLUDES
block_list = [
    'tkinter', 'unittest', 'pydoc', 'xmlrpc', 
    'matplotlib', 'scipy', 'PyQt5', 'PyQt6', 'IPython'
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
    optimize=1,
)

# 2. BLOAT FILTER
forbidden_keywords = [
    # Strip ONNX GPU Providers for CPU build
    'onnxruntime_providers_cuda',
    'onnxruntime_providers_tensorrt',
    
    # Strip CUDA and cuDNN libraries for CPU build
    'cublas',
    'cufft',
    'cudart',
    'cudnn',
    'curand',
    'nvrtc',
    'nvjitlink',
    'nvblas',
    
    # Strip Heavy Unused PySide6 Modules
    'opengl32sw',
    'qt6opengl',
    'qt6pdf',
    'qt6qml',
    'qt6quick',
    'qt6virtualkeyboard',
    'qtvirtualkeyboardplugin',
    
    # Strip PySide6 Language Translations (100+ .qm files)
    'translations',
    
    # Strip PyWin32 UI components
    'pythonwin',
    'win32ui',
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
    if not any(kw.lower() in dest_path for kw in forbidden_keywords):
        filtered_datas.append(d)
a.datas = filtered_datas

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
    icon=['assets\\icon.ico'],
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
