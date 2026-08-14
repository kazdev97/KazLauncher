# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
VERSION_FILE = os.path.join(SPEC_DIR, 'packaging', 'updater_version.txt')
APP_MANIFEST = os.path.join(SPEC_DIR, 'packaging', 'app.manifest')
ICON_FILE = os.path.join(SPEC_DIR, 'assets', 'launcher-icon.ico')

datas_requests = collect_data_files('requests')

a = Analysis(
    ['updater_gui.py'],
    pathex=[],
    binaries=[],
    datas=datas_requests + [('assets/loader.gif', 'assets')],
    hiddenimports=['requests'], 
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [], 
    a.binaries,
    a.datas,
    name='updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    version=VERSION_FILE if os.path.isfile(VERSION_FILE) else None,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE if os.path.isfile(ICON_FILE) else None,
    manifest=APP_MANIFEST if os.path.isfile(APP_MANIFEST) else None,
    uac_admin=False,
)
