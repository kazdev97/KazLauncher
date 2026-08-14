"""Selección de Java según la versión de Minecraft."""
from __future__ import annotations
import glob
import json
import os
import re
import sys
import time
from typing import Optional
import minecraft_launcher_lib
from minecraft_launcher_lib import java_utils
from kaz_launcher.utils.download import request_with_retries
from kaz_launcher.utils.java_installer import get_bundled_java_executable, validate_java_executable
def parse_mc_version_tuple(mc_version: str) -> tuple[int, int, int]:
    """Extrae (major, minor, patch) de ids como \'1.21.1\' o \'1.21.1-forge-...\'."""
    match = re.search('(\\d+)\\.(\\d+)(?:\\.(\\d+))?', mc_version or '')
    if not match:
        return (1, 21, 0)
    else:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))
def required_java_major(mc_version: str) -> int:
    """\n    Java mínima recomendada por Mojang:\n    - < 1.17  -> 8\n    - 1.17–1.20.4 -> 17\n    - 1.20.5+ y 1.21+ -> 21\n    """
    major, minor, patch = parse_mc_version_tuple(mc_version)
    if major != 1:
        return 21
    else:
        if minor < 17:
            return 8
        else:
            if minor < 20:
                return 17
            else:
                if minor == 20 and patch < 5:
                    return 17
                else:
                    return 21
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
def _java_major_from_install_dir(java_dir: str) -> Optional[int]:
    try:
        info = java_utils.get_java_information(java_dir)
        version_str = str(info.get('version', ''))
        match = re.match('(\\d+)', version_str.replace('_', '.'))
        if match:
            return int(match.group(1))
    except Exception:
        return None
    return None
def _extra_search_directories() -> list[str]:
    extra_dirs = []
    if sys.platform != 'win32':
        return extra_dirs
    else:
        program_files = os.environ.get('ProgramFiles', 'C:\\Program Files')
        program_files_x86 = os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        for base in [program_files, program_files_x86]:
            if not base:
                continue
            else:
                extra_dirs.extend([os.path.join(base, 'Java'), os.path.join(base, 'Microsoft'), os.path.join(base, 'Eclipse Adoptium'), os.path.join(base, 'Adoptium'), os.path.join(base, 'AdoptOpenJDK'), os.path.join(base, 'Zulu'), os.path.join(base, 'Amazon Corretto')])
        if local_appdata:
            extra_dirs.extend([os.path.join(local_appdata, 'Programs', 'Eclipse Adoptium'), os.path.join(local_appdata, 'Programs', 'Microsoft'), os.path.join(local_appdata, 'Microsoft', 'OpenJDK'), os.path.join(local_appdata, 'Programs', 'Amazon Corretto')])
        java_home = os.environ.get('JAVA_HOME', '').strip()
        if java_home and os.path.isdir(java_home):
                extra_dirs.append(java_home)
        return extra_dirs
def _glob_jdk_install_dirs() -> list[str]:
    """Encuentra carpetas jdk-* (Microsoft, Adoptium, etc.)."""
    patterns = []
    if sys.platform == 'win32':
        for base in _extra_search_directories():
            if base and os.path.isdir(base):
                    patterns.append(os.path.join(base, 'jdk*'))
        for pf in [os.environ.get('ProgramFiles', 'C:\\Program Files'), os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')]:
            if pf:
                patterns.append(os.path.join(pf, 'Microsoft', 'jdk*'))
                patterns.append(os.path.join(pf, 'Eclipse Adoptium', 'jdk*'))
                patterns.append(os.path.join(pf, 'Java', 'jdk*'))
    dirs = []
    seen = set()
    for pattern in patterns:
        for path in glob.glob(pattern):
            norm = os.path.normcase(os.path.abspath(path))
            if os.path.isdir(path):
                if norm not in seen:
                    seen.add(norm)
                    dirs.append(path)
    return dirs
def _enumerate_java_install_dirs() -> list[str]:
    seen = set()
    dirs = []
    for java_dir in java_utils.find_system_java_versions(additional_directories=_extra_search_directories() or None):
        norm = os.path.normcase(os.path.abspath(java_dir))
        if norm not in seen and os.path.isdir(java_dir):
                seen.add(norm)
                dirs.append(java_dir)
    for java_dir in _glob_jdk_install_dirs():
        norm = os.path.normcase(os.path.abspath(java_dir))
        if norm not in seen and os.path.isdir(java_dir):
                seen.add(norm)
                dirs.append(java_dir)
    return dirs
def _executable_for_dir(java_dir: str) -> Optional[str]:
    bin_dir = os.path.join(java_dir, 'bin')
    if sys.platform == 'win32':
        javaw = os.path.join(bin_dir, 'javaw.exe')
        if os.path.isfile(javaw):
            return javaw
        else:
            java_exe = os.path.join(bin_dir, 'java.exe')
            if os.path.isfile(java_exe):
                return java_exe
            else:
                return None
    else:
        full = os.path.join(bin_dir, 'java')
        if os.path.isfile(full):
            return full
        else:
            return None
_MOJANG_MANIFEST_URL = 'https://launchermeta.mojang.com/mc/game/version_manifest_v2.json'
_java_major_cache: dict = {}
_java_major_fail_cache: dict = {}
def _java_major_from_local_version_json(mc_version: str, versions_dir: Optional[str]) -> Optional[int]:
    """Lee javaVersion.majorVersion del JSON oficial ya descargado de la versión (sin red)."""
    if not versions_dir:
        return None
    version_json = os.path.join(versions_dir, mc_version, f'{mc_version}.json')
    try:
        with open(version_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        major = data.get('javaVersion', {}).get('majorVersion')
        if major:
            return int(major)
    except Exception:
        return None
    return None
def _manifest_entry_for(manifest: dict, mc_version: str) -> Optional[dict]:
    """Busca la entrada exacta del manifest, o la versión base (1.21.1-forge-… → 1.21.1)."""
    for entry in manifest.get('versions', []):
        if entry.get('id') == mc_version:
            return entry
    match = re.match(r'(\d+\.\d+(?:\.\d+)?)', mc_version or '')
    if match:
        base = match.group(1)
        for entry in manifest.get('versions', []):
            if entry.get('id') == base:
                return entry
    return None
def get_java_major_from_mojang(mc_version: str, versions_dir: Optional[str]=None) -> Optional[int]:
    """\n    Java mayor oficial según Mojang (javaVersion.majorVersion del JSON de la versión).\n    Revisa primero el JSON local ya descargado (sin red) y luego el manifest oficial.\n    Devuelve None si no se puede determinar (se usará la heurística como respaldo).\n    """
    if mc_version in _java_major_cache:
        return _java_major_cache[mc_version]
    local = _java_major_from_local_version_json(mc_version, versions_dir)
    if local:
        _java_major_cache[mc_version] = local
        return local
    now = time.time()
    if mc_version in _java_major_fail_cache and now - _java_major_fail_cache[mc_version] < 60:
        return None
    try:
        manifest = request_with_retries('GET', _MOJANG_MANIFEST_URL, timeout=15, max_attempts=2).json()
        entry = _manifest_entry_for(manifest, mc_version)
        if entry and entry.get('url'):
            meta = request_with_retries('GET', entry['url'], timeout=15, max_attempts=2).json()
            major = meta.get('javaVersion', {}).get('majorVersion')
            if major:
                major = int(major)
                _java_major_cache[mc_version] = major
                return major
    except Exception:
        pass
    _java_major_fail_cache[mc_version] = now
    return None
def _add_candidate(candidates: list[tuple[int, str]], exe: Optional[str], required: int) -> None:
    if not exe or not os.path.isfile(exe):
        return None
    else:
        ok, major = validate_java_executable(exe, required)
        if ok and major is not None:
                candidates.append((major, exe))
def resolve_java_for_minecraft(mc_version: str, preferred_exe: Optional[str], required_hint: Optional[int]=None) -> tuple[Optional[str], int, Optional[int]]:
    """\n    Devuelve (ruta_javaw/java, java_requerida, java_encontrada).\n    Solo devuelve Java validada (64 bits y versión correcta).\n    required_hint: Java requerida ya calculada en el worker (p. ej. con el JSON oficial de Mojang).\n    Esta función nunca hace red: sin hint usa la heurística (puede llamarse desde la UI).\n    """
    required = required_hint or required_java_major(mc_version)
    candidates = []
    bundled = get_bundled_java_executable(required)
    if bundled:
        ok, major = validate_java_executable(bundled, required)
        if ok and major is not None:
            return (bundled, required, major)
    preferred = (preferred_exe or '').strip()
    if preferred:
        _add_candidate(candidates, preferred, required)
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_major, best_exe = candidates[0]
            return (best_exe, required, best_major)
    return (None, required, None)
_CLASS_TO_JAVA_MAJOR = {52: 8, 55: 11, 61: 17, 65: 21}
def _class_version_to_java_major(class_version: int) -> Optional[int]:
    return _CLASS_TO_JAVA_MAJOR.get(class_version)
def parse_required_major_from_class_error(output: str) -> Optional[int]:
    if not output:
        return
    else:
        match = re.search('class file version (\\d+)(?:\\.\\d+)?', output)
        if not match:
            return
        else:
            return _class_version_to_java_major(int(match.group(1)))
def parse_found_major_from_class_error(output: str) -> Optional[int]:
    if not output:
        return
    else:
        match = re.search('only recognizes class file versions up to (\\d+)(?:\\.\\d+)?', output)
        if not match:
            return
        else:
            return _class_version_to_java_major(int(match.group(1)))
def is_jni_java_error(output: str) -> bool:
    if not output:
        return False
    else:
        lower = output.lower()
        return 'jni error' in lower or 'a jni error' in lower