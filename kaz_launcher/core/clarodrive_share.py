"""Listado y descarga de carpetas públicas en ClaroDrive (WebDAV OwnCloud)."""
from __future__ import annotations
import logging
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Callable, Optional
from urllib.parse import unquote, urlparse
from requests.auth import HTTPBasicAuth
from kaz_launcher.utils.download import download_file_with_retries, friendly_download_error, request_with_retries
StatusCallback = Optional[Callable[[str], None]]
MOD_EXTENSIONS = ('.jar', '.jar.disabled')
ARCHIVE_EXTENSIONS = ('.zip',)
DAV_NS = {'d': 'DAV:'}
def is_clarodrive_url(url: str) -> bool:
    return 'clarodrive.com' in (url or '').lower()
def is_mod_folder_url(url: str) -> bool:
    """True si la URL apunta a una carpeta compartida, no a un archivo suelto."""
    url = (url or '').strip()
    if not url:
        return False
    else:
        lower = url.lower().split('?')[0]
        if lower.endswith(('.jar', '.zip', '.jar.disabled', '.txt', '.json')):
            return False
        else:
            if is_clarodrive_url(url):
                return True
            else:
                if re.search('/s/[A-Za-z0-9]+/?$', url):
                    return True
                else:
                    return False
def resolve_share(url: str) -> tuple[str, str]:
    """\n    Resuelve enlace go.clarodrive.com o i0002.clarodrive.com/s/TOKEN.\n    Devuelve (base_url, token).\n    """
    url = (url or '').strip()
    if not url:
        raise ValueError('URL vacía')
    else:
        token_match = re.search('/s/([A-Za-z0-9]+)', url)
        if token_match and is_clarodrive_url(url) and ('go.clarodrive.com' not in url.lower()):
            parsed = urlparse(url)
            return (f'{parsed.scheme}://{parsed.netloc}', token_match.group(1))
        else:
            response = request_with_retries('GET', url, timeout=20, allow_redirects=True)
            final_url = response.url
            token_match = re.search('/s/([A-Za-z0-9]+)', final_url)
            if not token_match:
                raise ValueError(f'No se pudo obtener token de carpeta de la nube: {url}')
            else:
                parsed = urlparse(final_url)
                return (f'{parsed.scheme}://{parsed.netloc}', token_match.group(1))
def _webdav_propfind(base_url: str, token: str, depth: str='1') -> str:
    dav_url = f"{base_url.rstrip('/')}/public.php/webdav/"
    response = request_with_retries('PROPFIND', dav_url, auth=HTTPBasicAuth(token, ''), headers={'Depth': depth}, timeout=30)
    return response.text
def _parse_dav_entries(xml_text: str, base_url: str, token: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    entries = []
    prefix = '/public.php/webdav/'
    for response_node in root.findall('d:response', DAV_NS):
        href_el = response_node.find('d:href', DAV_NS)
        if href_el is None or not href_el.text:
            continue
        else:
            href = unquote(href_el.text)
            if not href.startswith(prefix):
                continue
            else:
                rel = href[len(prefix):].lstrip('/')
                if not rel or rel.endswith('/'):
                    continue
                else:
                    resource_type = response_node.find('.//d:resourcetype', DAV_NS)
                    if resource_type is not None and resource_type.find('d:collection', DAV_NS) is not None:
                            continue
                    filename = os.path.basename(rel.replace('\\', '/'))
                    lower_name = filename.lower()
                    if not lower_name.endswith(MOD_EXTENSIONS + ARCHIVE_EXTENSIONS):
                        continue
                    else:
                        download_url = f"{base_url.rstrip('/')}/public.php/webdav/{rel.replace(chr(92), '/')}"
                        entry_type = 'archive' if lower_name.endswith(ARCHIVE_EXTENSIONS) else 'mod'
                        entries.append({'name': filename, 'path': rel.replace('\\', '/'), 'url': download_url, 'token': token, 'base_url': base_url, 'type': entry_type})
    return entries
def list_expected_mod_names(entries: list[dict], *, on_status: StatusCallback=None) -> dict[str, dict]:
    """Convierte entradas WebDAV en mapa {nombre.jar: info}, expandiendo ZIPs remotos."""
    import tempfile
    expected = {}
    for entry in entries:
        if entry.get('type') == 'archive' or entry['name'].lower().endswith(ARCHIVE_EXTENSIONS):
            temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False).name
            try:
                ok, err = download_share_file(entry, temp_zip, on_status=on_status)
                if not ok:
                    raise RuntimeError(err)
                else:
                    with zipfile.ZipFile(temp_zip, 'r') as zf:
                        for member in zf.namelist():
                            base = os.path.basename(member)
                            if not base.lower().endswith(MOD_EXTENSIONS):
                                continue
                            else:
                                expected[base] = {**entry, 'source': 'folder_zip', 'archive_name': entry['name']}
            finally:
                if os.path.exists(temp_zip):
                    os.remove(temp_zip)
            continue
        else:
            expected[entry['name']] = {**entry, 'source': 'folder'}
    return expected
def expand_folder_mods(entries: list[dict], dest_dir: str, *, on_status: StatusCallback=None) -> list[str]:
    """\n    Descarga entradas de carpeta remota a dest_dir.\n    Si hay .zip, extrae solo .jar dentro. Devuelve nombres finales en mods/.\n    """
    os.makedirs(dest_dir, exist_ok=True)
    installed = []
    for entry in entries:
        name = entry['name']
        dest_path = os.path.join(dest_dir, name)
        if entry.get('type') == 'archive' or name.lower().endswith(ARCHIVE_EXTENSIONS):
            zip_path = dest_path
            ok, err = download_share_file(entry, zip_path, on_status=on_status)
            if not ok:
                raise RuntimeError(f'No se pudo descargar {name}: {err}')
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    for member in zf.namelist():
                        base = os.path.basename(member)
                        if base.lower().endswith(MOD_EXTENSIONS):
                            target = os.path.join(dest_dir, base)
                            with zf.open(member) as src:
                                with open(target, 'wb') as dst:
                                    dst.write(src.read())
                            installed.append(base)
            finally:
                try:
                    os.remove(zip_path)
                except OSError:
                    pass
            continue
        else:
            ok, err = download_share_file(entry, dest_path, on_status=on_status)
            if not ok:
                raise RuntimeError(f'No se pudo descargar {name}: {err}')
            installed.append(name)
    return installed
def list_folder_mods(folder_url: str, *, on_status: StatusCallback=None) -> list[dict]:
    """Lista archivos .jar de una carpeta pública ClaroDrive."""
    if on_status:
        on_status('Consultando carpeta de mods en la nube...')
    base_url, token = resolve_share(folder_url)
    xml_text = _webdav_propfind(base_url, token, depth='1')
    entries = _parse_dav_entries(xml_text, base_url, token)
    if on_status:
        on_status(f'Carpeta remota: {len(entries)} archivo(s) de mods.')
    return entries
def download_share_file(entry: dict, dest_path: str, *, on_status: StatusCallback=None) -> tuple[bool, str]:
    """Descarga un archivo listado desde WebDAV."""
    url = entry.get('url') or ''
    token = entry.get('token') or ''
    base_url = entry.get('base_url') or ''
    if not url and base_url and token:
                rel = entry.get('path') or entry.get('name') or ''
                url = f"{base_url.rstrip('/')}/public.php/webdav/{rel}"
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        if on_status:
            on_status(f'Descargando {os.path.basename(dest_path)}...')
        auth = HTTPBasicAuth(token, '') if token else None
        download_file_with_retries(url, dest_path, auth=auth, timeout=120, chunk_size=8192)
    except Exception as exc:
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        logging.error('Error descargando %s: %s', dest_path, exc)
        return (False, friendly_download_error(exc, f'Error descargando {os.path.basename(dest_path)}'))
    return (True, '')