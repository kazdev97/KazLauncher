# -*- mode: python ; coding: utf-8 -*-
# onefile: dist/KazLauncher.exe
import os
from PyInstaller.utils.hooks import collect_data_files

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
VERSION_FILE = os.path.join(SPEC_DIR, 'packaging', 'KazLauncher_version.txt')
APP_MANIFEST = os.path.join(SPEC_DIR, 'packaging', 'app.manifest')

datas_requests = collect_data_files('requests')

EXCLUDES = [
    'setuptools', 'distutils', 'wheel', 'pkg_resources',
    'tkinter', 'matplotlib', 'numpy', 'pandas', 'PIL', 'IPython',
    'pytest', 'unittest', 'test', 'lib2to3', 'pydoc', 'doctest',
    'xmlrpc', 'feedparser',
]

a = Analysis(
    ['kaz_launcher/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
    ] + datas_requests,
    hiddenimports=[
        'requests', 'pypresence',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineCore',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='KazLauncher',
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
    icon='assets/launcher-icon.ico',
    version=VERSION_FILE if os.path.isfile(VERSION_FILE) else None,
    manifest=APP_MANIFEST if os.path.isfile(APP_MANIFEST) else None,
    uac_admin=False,
)
