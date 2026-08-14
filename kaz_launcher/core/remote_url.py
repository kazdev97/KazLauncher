"""Normaliza enlaces de descarga: ClaroDrive, GitHub y Google Drive."""
from __future__ import annotations
import logging
import re
from urllib.parse import parse_qs, urlparse
from kaz_launcher.utils.download import request_with_retries
_CLARO_FILE_EXTENSIONS = ('.zip', '.jar', '.rar', '.7z', '.txt', '.json')
def resolve_download_url(url: str) -> str:
    """\n    Convierte enlaces de compartir a descarga directa cuando aplica.\n    URLs ya directas (Modrinth, raw GitHub, etc.) se devuelven sin cambios.\n    """
    url = (url or '').strip()
    if not url:
        return url
    else:
        lower_host = urlparse(url).netloc.lower()
        if 'clarodrive.com' in lower_host:
            return _resolve_clarodrive(url)
        else:
            if 'github.com' in lower_host:
                return _resolve_github(url)
            else:
                if 'drive.google.com' in lower_host or 'docs.google.com' in lower_host:
                    return _resolve_google_drive(url)
                else:
                    return url
def _resolve_clarodrive(url: str) -> str:
    path = url.lower().split('?')[0]
    if path.endswith(_CLARO_FILE_EXTENSIONS):
        return url
    else:
        if '/download' in url:
            return url.split('/download')[0].rstrip('/') + '/download'
        else:
            return url.rstrip('/') + '/download'
def _resolve_github(url: str) -> str:
    """blob/branch/path → raw.githubusercontent.com (descarga directa)."""
    match = re.match('https?://github\\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)', url, re.IGNORECASE)
    if match:
        user, repo, branch, path = match.groups()
        return f'https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}'
    else:
        return url
def _resolve_google_drive(url: str) -> str:
    """file/d/ID o open?id=ID → uc?export=download."""
    parsed = urlparse(url)
    file_id = ''
    match = re.search('/file/d/([a-zA-Z0-9_-]+)', parsed.path)
    if match:
        file_id = match.group(1)
    else:
        qs = parse_qs(parsed.query)
        file_id = (qs.get('id') or [''])[0]
    if file_id and 'uc?export=download' not in url:
        return f'https://drive.google.com/uc?export=download&id={file_id}'
    else:
        return url
def fetch_remote_text(url: str, *, timeout: int=20) -> str:
    """GET con URL resuelta; devuelve texto UTF-8."""
    resolved = resolve_download_url(url)
    response = request_with_retries('GET', resolved, timeout=timeout)
    content = response.content.decode('utf-8-sig').strip()
    if content.startswith('<'):
        raise ValueError('Se recibió HTML en lugar del archivo esperado. Usa un enlace de descarga directa.')
    else:
        return content
def fetch_remote_json(url: str, *, timeout: int=20):
    import json
    return json.loads(fetch_remote_text(url, timeout=timeout))