# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Spec lives at repo root — keep all paths relative to that.
ROOT = SPECPATH
SRC = os.path.join(ROOT, 'src')
ASSETS = os.path.join(ROOT, 'assets')

icon_file = os.path.join(ASSETS, 'app-icon.ico')
if not os.path.exists(icon_file):
    icon_file = None

datas = [
    (os.path.join(SRC, 'index.html'), '.'),
]
if os.path.exists(os.path.join(ASSETS, 'app-icon.ico')):
    datas.append((os.path.join(ASSETS, 'app-icon.ico'), 'assets'))
if os.path.exists(os.path.join(ASSETS, 'app-icon.png')):
    datas.append((os.path.join(ASSETS, 'app-icon.png'), 'assets'))

binaries = []
hiddenimports = [
    'qtpy',
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtWidgets',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebEngineCore',
    'requests',
    'chardet',
    'charset_normalizer',
]

for pkg in ('charset_normalizer', 'chardet'):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

hiddenimports += collect_submodules('charset_normalizer')

a = Analysis(
    [os.path.join(SRC, 'CursorWidget.py')],
    pathex=[SRC, ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CursorWidget',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CursorWidget',
)
