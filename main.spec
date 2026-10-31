# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from kivy_deps import sdl2, glew, angle

datas = collect_data_files('kivy')
datas += [('ico', 'ico')]

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
    binaries=[('opengl32.dll', '.')],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# === РЕЖИМ ONE-FILE ===
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    *[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins + angle.dep_bins)],
    [],
    name='Work schedule',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,         # <--- ОБЯЗАТЕЛЬНО ИЗМЕНИТЬ НА FALSE
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