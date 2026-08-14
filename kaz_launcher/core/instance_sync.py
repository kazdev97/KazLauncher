"""Sincronización de archivos y mods para instancias remotas."""
from __future__ import annotations
import hashlib
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import urlparse
from . import mod_manager
from .clarodrive_share import download_share_file, expand_folder_mods, is_mod_folder_url, list_expected_mod_names, list_folder_mods
from .remote_url import resolve_download_url
from kaz_launcher.utils.download import download_file_with_retries, friendly_download_error, request_with_retries
StatusCallback = Optional[Callable[[str], None]]
@dataclass
class ModSyncReport:
    up_to_date: bool = True
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    downloaded: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    def summary(self) -> str:
        if self.errors:
            return 'Errores: ' + '; '.join(self.errors)
        else:
            if self.up_to_date and (not self.downloaded) and (not self.removed):
                return 'up_to_date'
            else:
                parts = []
                if self.downloaded:
                    parts.append(f'descargados: {len(self.downloaded)}')
                if self.removed:
                    parts.append(f'eliminados: {len(self.removed)}')
                if self.missing and (not self.downloaded):
                        parts.append(f'faltantes: {len(self.missing)}')
                return ', '.join(parts) if parts else 'ok'
    def format_diff_details(self, lang_dict: dict) -> str:
        lines = []
        if self.missing:
            lines.append(lang_dict.get('modpack_missing_mods', 'Faltan en mods/:'))
            lines.extend((f'  • {name}' for name in self.missing))
        if self.extra:
            lines.append(lang_dict.get('modpack_extra_mods', 'Sobran en mods/:'))
            lines.extend((f'  • {name}' for name in self.extra))
        return '\n'.join(lines)
def _normalize_clarodrive_url(url: str) -> str:
    """Compatibilidad: delega en el resolvedor unificado."""
    return resolve_download_url(url)
def _filename_from_url(url: str, fallback: str='mod.jar') -> str:
    path = urlparse(url).path
    name = os.path.basename(path.split('?')[0])
    return name or fallback
def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def download_to_path(url: str, dest_path: str, *, expected_sha256: str, on_status: StatusCallback) -> tuple[bool, str]:
    url = _normalize_clarodrive_url(url)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        if on_status:
            on_status(f'Descargando {os.path.basename(dest_path)}...')
        download_file_with_retries(url, dest_path, session=mod_manager.get_session(), timeout=60, chunk_size=65536)
        if expected_sha256:
            actual = _sha256_file(dest_path)
            if actual.lower() != expected_sha256.lower():
                os.remove(dest_path)
                return (False, f'Hash incorrecto para {os.path.basename(dest_path)}')
        return (True, '')
    except Exception as exc:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return (False, friendly_download_error(exc, f'Error descargando {os.path.basename(dest_path)}'))
def collect_manifest_files(manifest: dict) -> list[dict]:
    """Lista de archivos a sincronizar en la instancia (ruta relativa + url)."""
    files = []
    seen_paths = set()
    def add_entry(path: str, url: str, sha256: str=''):
        path = path.replace('\\', '/').lstrip('/')
        if not path or not url or path in seen_paths:
            return None
        else:
            seen_paths.add(path)
            files.append({'path': path, 'url': url, 'sha256': sha256 or ''})
    for entry in manifest.get('files') or []:
        if isinstance(entry, dict):
            add_entry(str(entry.get('path') or ''), str(entry.get('url') or ''), str(entry.get('sha256') or ''))
    files_url = str(manifest.get('files_url') or manifest.get('files_manifest_url') or '').strip()
    if files_url:
        try:
            response = request_with_retries('GET', _normalize_clarodrive_url(files_url), timeout=20)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                entries_src = payload.get('files') or []
            else:
                if isinstance(payload, list):
                    entries_src = payload
                else:
                    entries_src = []
            for entry in entries_src:
                if isinstance(entry, dict):
                    add_entry(str(entry.get('path') or ''), str(entry.get('url') or ''), str(entry.get('sha256') or ''))
        except Exception as exc:
            logging.warning('No se pudo cargar files_url: %s', exc)
    mods = manifest.get('mods') or []
    for entry in mods:
        if isinstance(entry, dict):
            url = str(entry.get('url') or '').strip()
            if not url or url.lower().endswith('.zip') or is_mod_folder_url(url):
                continue
            else:
                filename = str(entry.get('filename') or _filename_from_url(url))
                add_entry(f'mods/{filename}', url, str(entry.get('sha256') or ''))
    return files
def iter_mods_folder_urls(manifest: dict) -> list[str]:
    """URLs de carpetas remotas que contienen mods."""
    urls = []
    seen = set()
    def add(url: str):
        url = (url or '').strip()
        if url and url not in seen:
                seen.add(url)
                urls.append(url)
    add(str(manifest.get('mods_folder_url') or manifest.get('mods_url') or '').strip())
    for entry in manifest.get('mods') or []:
        if not isinstance(entry, dict):
            continue
        else:
            url = str(entry.get('url') or '').strip()
            if not url or url.lower().endswith('.zip'):
                continue
            else:
                if entry.get('folder') is True or is_mod_folder_url(url):
                    add(url)
    return urls
# return {'on_status': None}
def resolve_remote_mod_files(manifest: dict, game_version: str, loader: str, lang_dict: dict, *, on_status: StatusCallback) -> dict[str, dict]:
    """\n    Devuelve {nombre.jar: {url, token, base_url, path, source}} desde carpetas remotas,\n    URLs directas y Modrinth.\n    """
    expected = {}
    for folder_url in iter_mods_folder_urls(manifest):
        try:
            entries = list_folder_mods(folder_url, on_status=on_status)
            folder_expected = list_expected_mod_names(entries, on_status=on_status)
            for name, info in folder_expected.items():
                expected[name] = info
        except Exception as exc:
            logging.error('Error listando carpeta %s: %s', folder_url, exc)
            raise
    for entry in manifest.get('mods') or []:
        if not isinstance(entry, dict):
            continue
        else:
            url = str(entry.get('url') or '').strip()
            if url and (not url.lower().endswith('.zip')) and (not is_mod_folder_url(url)) and (entry.get('folder') is not True):
                filename = str(entry.get('filename') or _filename_from_url(url))
                expected[filename] = {'url': url, 'token': '', 'base_url': '', 'path': filename, 'source': 'url', 'sha256': str(entry.get('sha256') or '')}
                continue
            else:
                project_id = str(entry.get('project_id') or '').strip()
                if not project_id:
                    continue
                else:
                    version_info = mod_manager.get_latest_mod_version(project_id, game_version, loader, lang_dict)
                    if not version_info or not version_info.get('files'):
                        continue
                    else:
                        files = version_info.get('files', [])
                        primary = next((f for f in files if f.get('primary')), files[0])
                        if primary:
                            filename = primary['filename']
                            expected[filename] = {'url': primary['url'], 'token': '', 'base_url': '', 'path': filename, 'source': 'modrinth', 'project_id': project_id}
    return expected
# return {'folders_filter': None, 'exclude_folders': None, 'on_status': None}
def sync_instance_files(manifest: dict, instance_dir: str, *, folders_filter: Optional[set[str]], exclude_folders: Optional[set[str]], on_status: StatusCallback) -> tuple[bool, str]:
    """\n    Descarga archivos listados en manifest.files / files_url a la instancia.\n    folders_filter: ej. {\'mods\'} para sincronizar solo esa carpeta.\n    exclude_folders: ej. {\'mods\'} para omitir carpetas.\n    """
    entries = collect_manifest_files(manifest)
    if folders_filter:
        entries = [e for e in entries if e['path'].split('/')[0].lower() in folders_filter]
    if exclude_folders:
        entries = [e for e in entries if e['path'].split('/')[0].lower() not in exclude_folders]
    if not entries:
        return (True, '')
    else:
        total = len(entries)
        if on_status:
            on_status(f'Sincronizando {total} archivos en paralelo...')
        def _download_one(entry: dict) -> tuple[str, bool, str]:
            rel_path = entry['path']
            dest = os.path.join(instance_dir, *rel_path.split('/'))
            ok, err = download_to_path(entry['url'], dest, expected_sha256=entry.get('sha256') or '', on_status=None)
            return (rel_path, ok, err)
        workers = min(8, len(entries))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_download_one, e) for e in entries]
            for fut in as_completed(futures):
                rel_path, ok, err = fut.result()
                if not ok:
                    return (False, f'Error en {rel_path}: {err}')
        return (True, '')
def build_expected_mod_map(manifest: dict, game_version: str, loader: str, lang_dict: dict, *, on_status: StatusCallback=None) -> dict[str, dict]:
    """Devuelve {nombre_archivo: info descarga} esperados en mods/."""
    return resolve_remote_mod_files(manifest, game_version, loader, lang_dict, on_status=on_status)
def list_local_mod_filenames(mods_dir: str) -> set[str]:
    if not os.path.isdir(mods_dir):
        return set()
    else:
        return {name for name in os.listdir(mods_dir) if name.lower().endswith(('.jar', '.jar.disabled'))}
# return {'on_status': None}
def verify_remote_mods(manifest: dict, instance_dir: str, lang_dict: dict, *, on_status: StatusCallback = None) -> ModSyncReport:
    report = ModSyncReport()
    game_version = str(manifest.get('game_version') or '').strip()
    loader = str(manifest.get('loader') or 'forge').strip().lower()
    mods_dir = os.path.join(instance_dir, 'mods')
    try:
        expected = build_expected_mod_map(manifest, game_version, loader, lang_dict, on_status=on_status)
    except Exception as exc:
        report.errors.append(str(exc))
        report.up_to_date = False
        return report
    if not expected:
        report.errors.append('El manifest no define mods para verificar.')
        report.up_to_date = False
        return report
    else:
        local = list_local_mod_filenames(mods_dir)
        expected_names = set(expected.keys())
        report.missing = sorted(expected_names - local)
        report.extra = sorted(local - expected_names)
        report.up_to_date = not report.missing and (not report.extra)
        return report
# return {'on_status': None, 'apply_changes': True, 'prune_extra': True}
def sync_remote_mods(manifest: dict, instance_dir: str, lang_dict: dict, *, on_status: StatusCallback = None, apply_changes: bool, prune_extra: bool) -> tuple[ModSyncReport, bool, str]:
    """\n    Compara mods/ con el manifest. Si apply_changes, descarga faltantes y elimina sobrantes.\n    """
    report = verify_remote_mods(manifest, instance_dir, lang_dict, on_status=on_status)
    if report.errors:
        return (report, False, report.errors[0])
    else:
        if not apply_changes:
            return (report, True, report.summary())
        else:
            mods_dir = os.path.join(instance_dir, 'mods')
            os.makedirs(mods_dir, exist_ok=True)
            expected = build_expected_mod_map(manifest, str(manifest.get('game_version') or '').strip(), str(manifest.get('loader') or 'forge').strip().lower(), lang_dict, on_status=on_status)
            folder_urls = iter_mods_folder_urls(manifest)
            if apply_changes and folder_urls and report.missing:
                        for folder_url in folder_urls:
                            entries = list_folder_mods(folder_url, on_status=on_status)
                            if any((e.get('type') == 'archive' for e in entries)):
                                expand_folder_mods(entries, mods_dir, on_status=on_status)
                                for name in list(report.missing):
                                    if name in list_local_mod_filenames(mods_dir):
                                        report.downloaded.append(name)
                                report.missing = [name for name in report.missing if name not in list_local_mod_filenames(mods_dir)]
                                break
            missing_with_url = []
            for filename in list(report.missing):
                info = expected.get(filename)
                if not info or not info.get('url'):
                    report.errors.append(f'Sin URL para {filename}')
                else:
                    missing_with_url.append(filename)
            if missing_with_url:
                if on_status:
                    on_status(f'Descargando {len(missing_with_url)} mods...')
                def _download_one_mod(filename: str) -> tuple[str, bool, str]:
                    info = expected[filename]
                    dest = os.path.join(mods_dir, filename)
                    if info.get('source') in ['folder', 'folder_zip'] and info.get('token'):
                        ok, err = download_share_file(info, dest, on_status=None)
                        return (filename, ok, '' if ok else f'No se pudo descargar {filename}: {err}')
                    def prog(_p):
                        return
                    ok = mod_manager.download_file(info['url'], mods_dir, filename, prog, lang_dict)
                    return (filename, ok, '' if ok else f'No se pudo descargar {filename}')
                workers = min(8, len(missing_with_url))
                done_count = 0
                total_count = len(missing_with_url)
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [pool.submit(_download_one_mod, f) for f in missing_with_url]
                    for fut in as_completed(futures):
                        filename, ok, err = fut.result()
                        done_count += 1
                        if on_status:
                            on_status(f'Descargando mods ({done_count}/{total_count})...')
                        if ok:
                            report.downloaded.append(filename)
                            report.missing.remove(filename)
                        else:
                            report.errors.append(err)
            if prune_extra:
                for filename in report.extra:
                    path = os.path.join(mods_dir, filename)
                    try:
                        os.remove(path)
                        report.removed.append(filename)
                    except OSError as exc:
                        report.errors.append(f'No se pudo eliminar {filename}: {exc}')
            report.up_to_date = not report.missing and (not report.extra) and (not report.downloaded) and (not report.removed) and (not report.errors)
            if report.errors:
                return (report, False, report.errors[0])
            else:
                return (report, True, report.summary())