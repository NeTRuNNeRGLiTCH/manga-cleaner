# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets'), ('src/frontend/styles.qss', 'src/frontend')]
binaries = []
hiddenimports = [
    'PySide6.QtCore', 
    'PySide6.QtGui', 
    'PySide6.QtWidgets', 
    'simple_lama_inpainting', 
    'pywin32', 
    'numpy', 
    'packaging',
    'torch.utils.data', # Necessary for AI data loading
    'nvidia' 
]

for lib in ['easyocr', 'torch', 'cv2', 'scipy']:
    tmp_ret = collect_all(lib)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # REMOVED 'unittest' from excludes below
    excludes=['matplotlib', 'notebook', 'jedi', 'Tkinter', 'IPython'], 
    noarchive=False,
    optimize=1,
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
    upx=False, 
    console=False,
    icon=['assets/icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='TitanMangaStudio',
)