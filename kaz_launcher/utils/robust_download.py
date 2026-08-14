"""Descargas robustas para minecraft_launcher_lib.

Sustituye download_file (en _helper y en cada módulo que lo importó por nombre)
por una versión con timeout, escritura atómica a .part, reanudación por Range y
reintentos con backoff. El parche se aplica una sola vez al iniciar la aplicación,
antes de cualquier instalación.
"""
from __future__ import annotations
import importlib
import logging
import lzma
import os
import requests
from .download import download_file_with_retries

_DOWNLOAD_FILE_IMPORTERS = (
    'minecraft_launcher_lib.install',
    'minecraft_launcher_lib.forge',
    'minecraft_launcher_lib.fabric',
    'minecraft_launcher_lib.quilt',
    'minecraft_launcher_lib.mrpack',
    'minecraft_launcher_lib.runtime',
    'minecraft_launcher_lib.mod_loader._forge',
    'minecraft_launcher_lib.mod_loader._fabric',
    'minecraft_launcher_lib.mod_loader._quilt',
)

_patched = False


def _is_http_404(exc: BaseException) -> bool:
    if isinstance(exc, requests.HTTPError):
        return getattr(getattr(exc, 'response', None), 'status_code', 0) in (404, 410)
    return False


def _make_robust_download_file():
    from minecraft_launcher_lib._helper import InvalidChecksum, check_path_inside_minecraft_directory, empty, get_sha1_hash, get_user_agent

    def robust_download_file(url, path, callback=None, sha1=None, lzma_compressed=False, session=None, minecraft_directory=None, overwrite=False):
        if minecraft_directory is not None:
            check_path_inside_minecraft_directory(minecraft_directory, path)
        if os.path.isfile(path) and not overwrite:
            if sha1 is None:
                return False
            if get_sha1_hash(path) == sha1:
                return False
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        (callback or {}).get('setStatus', empty)('Download ' + os.path.basename(path))
        headers = {'user-agent': get_user_agent()}
        try:
            download_file_with_retries(
                url,
                path,
                headers=headers,
                session=session,
                timeout=60,
                chunk_size=65536,
                max_attempts=6,
                backoff=2.0,
                resume=True,
            )
        except requests.HTTPError as exc:
            if _is_http_404(exc):
                return False
            raise
        if lzma_compressed:
            with open(path, 'rb') as f:
                raw = f.read()
            os.remove(path)
            with open(path, 'wb') as f:
                f.write(lzma.decompress(raw))
        if sha1 is not None:
            checksum = get_sha1_hash(path)
            if checksum != sha1:
                raise InvalidChecksum(url, path, sha1, checksum)
        return True

    return robust_download_file


def apply_download_patches() -> None:
    """Sustituye download_file en minecraft_launcher_lib por la versión robusta.

    Idempotente: solo parchea la primera vez.
    """
    global _patched
    if _patched:
        return
    try:
        import minecraft_launcher_lib._helper as helper
    except Exception as exc:
        logging.warning('No se pudo parchear las descargas de minecraft_launcher_lib: %s', exc)
        return
    robust = _make_robust_download_file()
    helper.download_file = robust
    for modname in _DOWNLOAD_FILE_IMPORTERS:
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        if hasattr(mod, 'download_file'):
            mod.download_file = robust
    _patched = True
    logging.info('Descargas robustas aplicadas a minecraft_launcher_lib.')
