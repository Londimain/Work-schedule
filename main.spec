# -*- mode: python ; coding: utf-8 -*-
import os
import glob
from kivy import kivy_data_dir
from PyInstaller.utils.hooks import collect_submodules
from kivy_deps import sdl2, angle

# 1. Собираем DLL как 2-кортежи (источник, папка_назначения_в_архиве)
kivy_bins = []
for p in (sdl2.dep_bins + angle.dep_bins):
    if os.path.isdir(p):
        for f in glob.glob(os.path.join(p, '*')):
            kivy_bins.append((f, '.'))  # <--- Именно 2 элемента!

# 2. Данные Kivy и иконки
datas = [(kivy_data_dir, 'kivy/data')]
datas += [('ico', 'ico')]

# 3. Скрытые импорты
hiddenimports = collect_submodules('kivy', filter=lambda name: not name.startswith('kivy.garden'))
hiddenimports += [
    'openpyxl',
    'openpyxl.styles',
    'openpyxl.utils',
]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=kivy_bins,  # <--- Передаем сюда
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'pandas', 'matplotlib', 'scipy', 'tkinter', 'PIL', 'wx', 'gi', 'gst'],
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
    icon='ico/tabel.ico'
)