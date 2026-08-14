"""Instalación de Forge tolerante a fallos transitorios (Windows).

Maneja archivos temporales bloqueados por el instalador de Java y cortes de red,
reintentando con backoff exponencial y verificando el resultado final.
"""
from __future__ import annotations
import logging
import time
from typing import Any, Callable
import requests
from .download import _backoff_seconds, is_retryable_http_error, is_winerror_32, run_install_with_retries


def run_forge_install_tolerant(
    install_fn: Callable[[], Any],
    minecraft_dir: str,
    expected_version_id: str,
    *,
    attempts: int = 6,
    backoff: float = 2.0,
) -> None:
    """Ejecuta install_fn (instalación de Forge) tolerando WinError 32 y cortes de red.

    Reintenta bloqueos transitorios y, si la versión esperada quedó instalada
    pese a que la limpieza de temporales falló, se considera éxito.
    """
    from minecraft_launcher_lib import utils
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        before = {v['id'] for v in utils.get_installed_versions(minecraft_dir)}
        try:
            run_install_with_retries(install_fn, max_attempts=2, backoff=1.5)
            return
        except Exception as exc:
            win32 = is_winerror_32(exc)
            if not win32 and not is_retryable_http_error(exc):
                raise
            last_error = exc
            if win32:
                after = {v['id'] for v in utils.get_installed_versions(minecraft_dir)}
                if expected_version_id in after:
                    logging.warning('Forge instalado correctamente; solo falló la limpieza de temporales (WinError 32). Se ignora.')
                    return
                if after != before:
                    logging.warning('Forge: WinError 32 pero se detectaron versiones nuevas en la instancia; se asume instalado.')
                    return
            if attempt >= attempts:
                raise exc
            time.sleep(_backoff_seconds(attempt, backoff))
    if isinstance(last_error, requests.ConnectionError):
        raise last_error
    raise requests.ConnectionError(last_error) from last_error
