"""Utilidades de descarga con reintentos, backoff y reanudación por Range.

Los cortes de conexión (red inestable, cortafuegos o límites del CDN) se
reintentan con backoff y, cuando el servidor soporta Range, la descarga se
reanuda desde donde quedó.
"""
from __future__ import annotations
import os
import random
import time
from typing import Any, Callable, Optional
import requests
from urllib3.exceptions import DecodeError, IncompleteRead, ProtocolError, ReadTimeoutError

ProgressCallback = Optional[Callable[[int, int], None]]
RetryCallback = Optional[Callable[[int, int], None]]

_HTTP_RETRYABLE = (
    requests.ConnectionError,
    requests.Timeout,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ContentDecodingError,
)
_TRANSIENT_STATUS = (408, 429, 500, 502, 503, 504)


def is_retryable_http_error(exc: BaseException) -> bool:
    """True si el error es un corte de conexión/red y merece reintento."""
    if isinstance(exc, _HTTP_RETRYABLE):
        return True
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError, ProtocolError, ReadTimeoutError, DecodeError, IncompleteRead)):
        return True
    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if getattr(exc, 'response', None) is not None else 0
        if status in _TRANSIENT_STATUS:
            return True
    text = str(exc or '').lower()
    return ('10054' in text or 'connection aborted' in text or 'forcibly closed' in text or 'chunked' in text or 'connection reset' in text)


def _backoff_seconds(attempt: int, base: float) -> float:
    delay = base * (2 ** (attempt - 1))
    return delay + random.uniform(0, delay * 0.3)


def is_winerror_32(exc: BaseException) -> bool:
    """True si el error es un archivo bloqueado por otro proceso (WinError 32)."""
    if isinstance(exc, OSError):
        return getattr(exc, 'winerror', None) == 32 or getattr(exc, 'errno', None) == 32
    return False


def friendly_download_error(exc: BaseException, fallback: str = '') -> str:
    """Convierte un error de red o de archivo en un mensaje claro para el usuario final."""
    text = str(exc or '').strip()
    lower = text.lower()
    if is_winerror_32(exc):
        return ('Un archivo necesario está bloqueado por otro proceso (WinError 32). '
                'Cierra Minecraft/Java si están abiertos y desactiva temporalmente el antivirus, '
                'luego vuelve a intentarlo.')
    if '10054' in lower or 'forcibly closed' in lower or 'connection aborted' in lower or 'connection reset' in lower:
        return ('Se cortó la conexión mientras se descargaba (error 10054). '
                'Revisa tu conexión a internet y, si falla otra vez, desactiva temporalmente '
                'el antivirus/cortafuegos y vuelve a intentarlo.')
    if not text:
        return fallback or 'Error de conexión al descargar.'
    return text


def request_with_retries(
    method: str,
    url: str,
    *,
    auth=None,
    headers: Optional[dict] = None,
    timeout: float = 20,
    max_attempts: int = 4,
    backoff: float = 1.0,
    session: Optional[requests.Session] = None,
    **kwargs,
) -> requests.Response:
    """GET/PROPFIND/etc. con reintentos. Lee el cuerpo dentro del try para
    detectar cortes a mitad de la respuesta. Devuelve la Response con
    .content ya cacheado (llamadas a .json()/text no re-leen de la red)."""
    requestor = session if session is not None else requests
    last_error: Optional[BaseException] = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requestor.request(method, url, auth=auth, headers=headers, timeout=timeout, **kwargs)
            if response.status_code in (408, 429) or response.status_code >= 500:
                response.raise_for_status()
            if method.upper() != 'HEAD':
                response.content
            response.raise_for_status()
            return response
        except Exception as exc:
            if not is_retryable_http_error(exc):
                raise
            last_error = exc
            if attempt < max_attempts:
                time.sleep(_backoff_seconds(attempt, backoff))
    raise requests.ConnectionError(last_error) from last_error


def download_file_with_retries(
    url: str,
    dest_path: str,
    *,
    auth=None,
    headers: Optional[dict] = None,
    session: Optional[requests.Session] = None,
    timeout: float = 60,
    chunk_size: int = 65536,
    max_attempts: int = 4,
    backoff: float = 1.5,
    resume: bool = True,
    on_progress: ProgressCallback = None,
    on_retry: RetryCallback = None,
) -> None:
    """Descarga streamed con reintentos y reanudación (Range cuando aplica).

    Escribe en dest_path + '.part' y lo renombra de forma atómica al final.
    Si fallan todos los intentos, lanza la última excepción y elimina el .part.
    """
    requestor = session if session is not None else requests
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    part_path = dest_path + '.part'
    last_error: Optional[BaseException] = None
    for attempt in range(1, max_attempts + 1):
        stream_headers = dict(headers or {})
        start = 0
        if resume and os.path.isfile(part_path):
            start = os.path.getsize(part_path)
        if start > 0:
            stream_headers['Range'] = f'bytes={start}-'
        open_mode = 'ab' if start > 0 else 'wb'
        try:
            with requestor.get(url, auth=auth, headers=stream_headers, stream=True, timeout=timeout) as response:
                if response.status_code == 416:
                    os.replace(part_path, dest_path)
                    return
                if start > 0 and response.status_code == 200:
                    start = 0
                    open_mode = 'wb'
                elif response.status_code not in (200, 206):
                    response.raise_for_status()
                total = int(response.headers.get('content-length') or 0)
                if response.status_code == 206:
                    total = start + total
                downloaded = start
                with open(part_path, open_mode) as handle:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if on_progress and total:
                            on_progress(min(downloaded, total), total)
                if total > 0 and downloaded < total:
                    raise requests.exceptions.ChunkedEncodingError(f'Descarga incompleta: {downloaded}/{total} bytes')
            _replace_with_retry(part_path, dest_path)
            return
        except Exception as exc:
            if not is_retryable_http_error(exc):
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except OSError:
                        pass
                raise
            last_error = exc
            if on_retry:
                on_retry(attempt, max_attempts)
            if attempt < max_attempts:
                time.sleep(_backoff_seconds(attempt, backoff))
    if os.path.exists(part_path):
        try:
            os.remove(part_path)
        except OSError:
            pass
    raise requests.ConnectionError(last_error) from last_error


def _replace_with_retry(part_path: str, dest_path: str) -> None:
    """Renombra de forma atómica tolerando bloqueos transitorios (WinError 32).

    El antivirus o un proceso que escanea el destino pueden bloquear el renombrado
    unos instantes; se reintenta con una pequeña espera antes de rendirse.
    """
    for attempt in range(1, 4):
        try:
            os.replace(part_path, dest_path)
            return
        except OSError as exc:
            if not is_winerror_32(exc) or attempt >= 3:
                raise
            time.sleep(1.0 + attempt)


def run_install_with_retries(fn: Callable[[], Any], *, on_retry: RetryCallback = None, max_attempts: int = 6, backoff: float = 2.5) -> Any:
    """Ejecuta una instalación de minecraft_launcher_lib reintentándola si hay
    cortes de red o archivos bloqueados transitoriamente (WinError 32).
    La instalación es idempotente: archivos ya completos se omiten
    y archivos parciales se vuelven a descargar."""
    last_error: Optional[BaseException] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if not is_retryable_http_error(exc) and not is_winerror_32(exc):
                raise
            last_error = exc
            if on_retry:
                on_retry(attempt, max_attempts)
            if attempt < max_attempts:
                time.sleep(_backoff_seconds(attempt, backoff))
    raise requests.ConnectionError(last_error) from last_error
