"""Descarga e instala Java portable (Adoptium) en la carpeta del launcher."""
from __future__ import annotations
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from typing import Callable, Optional
from kaz_launcher.utils.download import download_file_with_retries, request_with_retries
from kaz_launcher.utils.paths import get_launcher_data_dir
StatusCallback = Optional[Callable[[str], None]]
_ADOPTIUM_API = 'https://api.adoptium.net/v3/assets/latest/{major}/hotspot?architecture=x64&image_type=jdk&os={os_name}&heap_size=normal'
def _runtime_base_dir() -> str:
    path = os.path.join(get_launcher_data_dir(), 'runtime')
    os.makedirs(path, exist_ok=True)
    return path
def get_bundled_java_root(major: int) -> str:
    return os.path.join(_runtime_base_dir(), f'jdk-{major}')
def _subprocess_flags() -> int:
    if sys.platform == 'win32':
        return subprocess.CREATE_NO_WINDOW
    else:
        return 0
def validate_java_executable(exe: str, min_major: int) -> tuple[bool, Optional[int]]:
    """\n    Comprueba que el ejecutable funciona, es 64 bits (Windows) y cumple la versión mínima.\n    Devuelve (válido, major_detectada).\n    """
    if not exe or not os.path.isfile(exe):
        return (False, None)
    java_cmd = exe
    if exe.lower().endswith('javaw.exe'):
        java_cmd = os.path.join(os.path.dirname(exe), 'java.exe')
        if not os.path.isfile(java_cmd):
            java_cmd = exe
    root = _java_install_root_from_exe(exe)
    try:
        if root:
            from minecraft_launcher_lib import java_utils
            info = java_utils.get_java_information(root)
            if sys.platform == 'win32' and (not info.get('is_64bit', True)):
                return (False, None)
            version_str = str(info.get('version', ''))
            match = re.match('(\\d+)', version_str.replace('_', '.'))
            if match:
                major = int(match.group(1))
                return (major >= min_major, major)
    except Exception:
        pass
    try:
        result = subprocess.run([java_cmd, '-version'], capture_output=True, text=True, timeout=20, creationflags=_subprocess_flags())
        output = f"{result.stderr or ''}\n{result.stdout or ''}"
        lower = output.lower()
        if sys.platform == 'win32':
            if '32-bit' in lower or '32 bit' in lower:
                return (False, None)
            if '64-bit' not in lower and '64 bit' not in lower:
                return (False, None)
        match = re.search('version "(\\d+)', output)
        if not match:
            return (False, None)
        major = int(match.group(1))
        return (major >= min_major, major)
    except Exception as exc:
        logging.debug('validate_java_executable(%s): %s', exe, exc)
        return (False, None)
def _java_install_root_from_exe(exe_path: str) -> Optional[str]:
    if not exe_path:
        return
    else:
        exe_path = os.path.normpath(exe_path)
        bin_dir = os.path.dirname(exe_path)
        if os.path.basename(bin_dir).lower() == 'bin':
            return os.path.dirname(bin_dir)
        else:
            return None
def _find_javaw_in_tree(root: str) -> Optional[str]:
    if sys.platform == 'win32':
        names = ('javaw.exe', 'java.exe')
    else:
        names = ('java',)
    for dirpath, _, filenames in os.walk(root):
        for name in names:
            if name in filenames:
                full = os.path.join(dirpath, name)
                if name == 'java.exe' and sys.platform == 'win32':
                    javaw = os.path.join(dirpath, 'javaw.exe')
                    if os.path.isfile(javaw):
                        return javaw
                return full
    return
def get_bundled_java_executable(major: int) -> Optional[str]:
    root = get_bundled_java_root(major)
    if not os.path.isdir(root):
        return
    else:
        exe = _find_javaw_in_tree(root)
        if exe and validate_java_executable(exe, major)[0]:
            return exe
        else:
            return None
def _adoptium_os_name() -> str:
    if sys.platform == 'win32':
        return 'windows'
    else:
        if sys.platform == 'darwin':
            return 'mac'
        else:
            return 'linux'
def _fetch_adoptium_download_url(major: int) -> tuple[str, str]:
    api_url = _ADOPTIUM_API.format(major=major, os_name=_adoptium_os_name())
    response = request_with_retries('GET', api_url, timeout=60)
    assets = response.json()
    if not assets:
        raise RuntimeError('Adoptium no devolvió ningún JDK.')
    else:
        asset = assets[0]
        link = asset['binary']['package']['link']
        name = asset['binary']['package']['name']
        return (link, name)
def install_portable_jdk(major: int, on_status: StatusCallback=None) -> str:
    """\n    Descarga JDK portable (zip) de Adoptium y lo extrae en runtime/jdk-{major}.\n    No requiere permisos de administrador.\n    """
    if on_status:
        on_status(f'Buscando Eclipse Temurin (Adoptium) Java {major}...')
    download_url, package_name = _fetch_adoptium_download_url(major)
    target_root = get_bundled_java_root(major)
    if os.path.isdir(target_root):
        shutil.rmtree(target_root, ignore_errors=True)
    os.makedirs(target_root, exist_ok=True)
    if on_status:
        on_status(f'Descargando Eclipse Temurin (Adoptium) — {package_name}...')
    tmp_zip = os.path.join(tempfile.gettempdir(), f'kazlauncher-jdk-{major}.zip')
    try:
        def _report(current: int, total: int):
            if on_status and total > 0:
                pct = min(99, int(current * 100 / total))
                on_status(f'Descargando Java {major}... {pct}%')
        download_file_with_retries(download_url, tmp_zip, timeout=300, chunk_size=262144, on_progress=_report)
        if on_status:
            on_status(f'Instalando Java {major}...')
        with zipfile.ZipFile(tmp_zip, 'r') as zf:
            zf.extractall(target_root)
        exe = _find_javaw_in_tree(target_root)
        if not exe:
            raise RuntimeError('No se encontró javaw.exe tras extraer el JDK.')
        else:
            ok, detected = validate_java_executable(exe, major)
            if not ok:
                raise RuntimeError(f"El JDK descargado no es válido (detectado: Java {detected or '?'}).")
            else:
                marker = os.path.join(target_root, '.kazlauncher-java.json')
                with open(marker, 'w', encoding='utf-8') as f:
                    json.dump({'major': major, 'exe': exe, 'package': package_name, 'vendor': 'Eclipse Temurin (Adoptium)'}, f)
                if on_status:
                    on_status(f'Java {major} Adoptium listo.')
                return exe
    finally:
        if os.path.isfile(tmp_zip):
            try:
                os.remove(tmp_zip)
            except OSError:
                pass
def ensure_java_for_minecraft(mc_version: str, preferred_exe: Optional[str], on_status: StatusCallback, min_major: Optional[int], versions_dir: Optional[str]=None) -> tuple[Optional[str], Optional[str]]:
    """\n    Resuelve Java compatible; si no existe, la descarga e instala en runtime/.\n    La versión de Java se obtiene del JSON oficial de Mojang (javaVersion.majorVersion)\n    y, si no se puede, de la heurística local. Devuelve (ruta_javaw, mensaje_error).\n    """
    from kaz_launcher.utils.java_resolver import get_java_major_from_mojang, required_java_major, resolve_java_for_minecraft
    required = min_major or get_java_major_from_mojang(mc_version, versions_dir=versions_dir) or required_java_major(mc_version)
    preferred = (preferred_exe or '').strip() or None
    if on_status:
        on_status(f'Buscando Java {required} compatible...')
    path, _, _ = resolve_java_for_minecraft(mc_version, preferred_exe=preferred, required_hint=required)
    if path and validate_java_executable(path, required)[0]:
        return (path, None)
    else:
        bundled = get_bundled_java_executable(required)
        if bundled:
            return (bundled, None)
        else:
            try:
                if on_status:
                    on_status(f'Instalando Eclipse Temurin (Adoptium) Java {required}...')
                installed = install_portable_jdk(required, on_status=on_status)
                return (installed, None)
            except Exception as exc:
                logging.exception('Error instalando Java portable')
                return (None, str(exc))