# -*- mode: python ; coding: utf-8 -*-
# onefile: dist/KazLauncher.exe
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
VERSION_FILE = os.path.join(SPEC_DIR, 'packaging', 'KazLauncher_version.txt')
APP_MANIFEST = os.path.join(SPEC_DIR, 'packaging', 'app.manifest')

datas_requests = collect_data_files('requests')

# DLLs del runtime de Visual C++ y de Python incluidas de forma explícita.
# Evita el error "Failed to load Python DLL / LoadLibrary: el módulo especificado
# no se puede encontrar" en equipos sin el redistribuible de VC instalado.
runtime_dlls = []
system32 = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32'
for _dll_name in ('vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll'):
    for _candidate in (system32 / _dll_name, Path(sys.base_prefix) / _dll_name, Path(sys.base_prefix) / 'DLLs' / _dll_name):
        if _candidate.is_file():
            runtime_dlls.append((str(_candidate), '.'))
            break
for _dll in sorted(Path(sys.base_prefix).glob('python*.dll')):
    if _dll.is_file():
        runtime_dlls.append((str(_dll), '.'))

EXCLUDES = [
    'setuptools', 'distutils', 'wheel', 'pkg_resources',
    'tkinter', 'matplotlib', 'numpy', 'pandas', 'PIL', 'IPython',
    'pytest', 'unittest', 'test', 'lib2to3', 'pydoc', 'doctest',
    'xmlrpc', 'feedparser',
]

a = Analysis(
    ['kaz_launcher/main.py'],
    pathex=[],
    binaries=runtime_dlls,
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
