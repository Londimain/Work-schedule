# -*- mode: python ; coding: utf-8 -*-
import os
import glob
from kivy import kivy_data_dir
from PyInstaller.utils.hooks import collect_submodules
from kivy_deps import sdl2, angle

kivy_bins = []
if os.path.isfile('opengl32.dll'):
    kivy_bins.append(('opengl32.dll', '.'))

def _expand(dep_list):
    out = []
    for dep in dep_list:
        if isinstance(dep, (tuple, list)) and len(dep) == 2:
            src, dest = dep
        else:
            src, dest = dep, '.'
        if os.path.isdir(src):
            for f in glob.glob(os.path.join(src, '*')):
                out.append((f, dest))
        elif any(ch in src for ch in '*?['):
            for f in glob.glob(src):
                out.append((f, dest))
        elif os.path.isfile(src):
            out.append((src, dest))
    return out

kivy_bins += _expand(sdl2.dep_bins)
kivy_bins += _expand(angle.dep_bins)

datas = [(kivy_data_dir, 'kivy/data')]
datas += [('ico', 'ico')]

hiddenimports = collect_submodules(
    'kivy', filter=lambda name: not name.startswith('kivy.garden')
)

# --- ДОБАВЛЕНЫ ВАЖНЫЕ БИБЛИОТЕКИ ДЛЯ ЯРЛЫКОВ И ВЫБОРА ПАПОК ---
hiddenimports += [
    'openpyxl',
    'openpyxl.styles',
    'openpyxl.utils',
    'filelock',
    'filelock._unix',
    'filelock._windows',
    'urllib.request',
    'urllib.error',
    'ssl',
    'http.client',
    'tkinter',
    'tkinter.filedialog',
    'win32com',
    'win32com.client',
    'pythoncom',
    'pywintypes',
    'win32file'
]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=kivy_bins,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'pandas', 'matplotlib', 'scipy',
              'PIL', 'wx', 'gi', 'gst'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Work schedule',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ico/tabel.ico',
    version='version_info.txt',
)