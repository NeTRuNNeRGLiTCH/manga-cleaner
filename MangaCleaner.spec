# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

#////////////////////////#
#  COLLECT AI BINARIES   #
#////////////////////////#
datas = [('assets', 'assets'), ('src/frontend/styles.qss', 'src/frontend')]
binaries = []
hiddenimports = ['simple_lama_inpainting', 'easyocr', 'torch', 'cv2', 'PIL', 'pywin32']

# Explicitly collect the heavy lifters
for lib in ['easyocr', 'torch', 'cv2', 'scipy', 'skimage']:
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
    excludes=['matplotlib', 'notebook', 'jedi', 'Tkinter'], 
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True, # We want the folder, not a single file
    name='MangaCleaner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False, # DISABLED FOR GITHUB COMPATIBILITY
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