# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets'), ('src/frontend/styles.qss', 'src/frontend')]
binaries = []
hiddenimports = ['simple_lama_inpainting', 'PIL', 'PIL._imagingtk', 'PIL._tkinter_finder']

# Collect heavy AI dependencies
for lib in ['easyocr', 'scipy', 'torch', 'cv2', 'skimage']:
    tmp_ret = collect_all(lib)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'notebook', 'jedi'], # Shrink size
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MangaCleaner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # Compress the result
    console=False, # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'], # THE DESKTOP ICON
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TitanMangaStudio',
)