
# -*- mode: python ; coding: utf-8 -*-

from importlib.metadata import distribution, PackageNotFoundError
from pathlib import Path
import sysconfig

# Collect the actual shared libraries installed by these CUDA 13 wheels.
# Distribution names do not necessarily correspond to importable modules.
nvidia_distributions = [
    'nvidia-cublas',
    'nvidia-cuda-nvrtc',
    'nvidia-cuda-runtime',
    'nvidia-cudnn-cu13',
    'nvidia-cufft',
    'nvidia-curand',
    'nvidia-nvjitlink',
]

site_packages = Path(sysconfig.get_paths()['purelib'])
nvidia_binaries = []
missing_packages = []
found_libraries = set()

for package_name in nvidia_distributions:
    try:
        dist = distribution(package_name)
    except PackageNotFoundError:
        missing_packages.append(f'{package_name}: distribution not installed')
        continue

    for entry in dist.files or []:
        # Include versioned and unversioned ELF shared libraries.
        if '.so' not in entry.name:
            continue

        source = Path(dist.locate_file(entry))

        if not source.is_file():
            continue

        try:
            relative_path = source.relative_to(site_packages)
        except ValueError:
            missing_packages.append(
                f'{package_name}: library outside site-packages: {source}'
            )
            continue

        # Preserve directories such as nvidia/cu13/lib.
        destination = relative_path.parent.as_posix()

        nvidia_binaries.append((str(source), destination))
        found_libraries.add(source.name)

    print(f'Collected NVIDIA distribution: {package_name}')

if missing_packages:
    raise RuntimeError(
        'NVIDIA dependency collection failed:\n'
        + '\n'.join(missing_packages)
    )

if not nvidia_binaries:
    raise RuntimeError('No NVIDIA shared libraries were collected.')

print(f'Collected {len(nvidia_binaries)} NVIDIA shared-library files.')
print(f'Unique library filenames: {len(found_libraries)}')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=nvidia_binaries,
    datas=[
        ('assets', 'assets'),
        ('src', 'src'),
    ],
    hiddenimports=[
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi.onnxruntime_pybind11_state',
        'PySide6.QtSvg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Keep CUDA and TensorRT providers. Remove only unwanted Qt components.
forbidden_keywords = [
    'libQt6OpenGL',
    'libQt6Pdf',
    'libQt6Qml',
    'libQt6Quick',
    'libQt6VirtualKeyboard',
    'translations',
]

a.binaries = [
    item for item in a.binaries
    if not any(k.lower() in item[0].lower()
               for k in forbidden_keywords)
]

a.datas = [
    item for item in a.datas
    if not any(k.lower() in item[0].lower()
               for k in forbidden_keywords)
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
