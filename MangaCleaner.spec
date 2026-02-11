# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

#////////////////////////#
#  STRICT DEPENDENCIES   #
#////////////////////////#
datas = [('assets', 'assets'), ('src/frontend/styles.qss', 'src/frontend')]
binaries = []
hiddenimports = ['PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'simple_lama_inpainting', 'pywin32']

# Explicitly collect EVERYTHING for the core libraries
for lib in ['PySide6', 'easyocr', 'torch', 'cv2', 'scipy', 'skimage']:
    tmp_ret = collect_all(lib)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

a = Analysis(
    ['main.py'],
    pathex=[os.getcwd()], # Force current directory into path
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'notebook', 'jedi', 'Tkinter', 'unittest'], 
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