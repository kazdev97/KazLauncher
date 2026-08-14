"""Actualización automática del launcher (ejecutable onefile).

En Windows un exe no puede reemplazarse a sí mismo mientras corre. El flujo es:
consultar el manifest remoto, descargar el exe nuevo, verificar su SHA-256 y
lanzar un finalizador oculto que reemplaza y relanza el launcher.

Manifest (JSON):
    {"version": "v1.2.5", "url": "https://.../KazLauncher.exe", "sha256": "<hex>"}
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import subprocess
import sys
from typing import Callable, Optional

from kaz_launcher.utils.download import download_file_with_retries, request_with_retries

# Manifest de actualizaciones (latest.json publicado junto al exe en GitHub Releases).
UPDATE_MANIFEST_URL = 'https://github.com/kazdev97/KazLauncher/releases/latest/download/latest.json'

ProgressCallback = Optional[Callable[[int, int], None]]
StatusCallback = Optional[Callable[[str], None]]


def parse_version(version: str) -> tuple:
    """'v1.2.2-beta' -> ((1, 2, 2), 'beta'). Devuelve tupla comparable."""
    v = (version or '').strip()
    if v[:1].lower() == 'v':
        v = v[1:]
    parts = v.split('-', 1)
    nums = []
    for token in parts[0].split('.'):
        try:
            nums.append(int(token))
        except ValueError:
            nums.append(0)
    pre = parts[1].strip().lower() if len(parts) > 1 else ''
    return (tuple(nums), pre)


def is_newer_version(current: str, remote: str) -> bool:
    """True si remote es más nueva que current (semver simple)."""
    c_num, c_pre = parse_version(current)
    r_num, r_pre = parse_version(remote)
    if r_num != c_num:
        return r_num > c_num
    if c_pre == r_pre:
        return False
    # 'v1.2.2' (release) es mayor que 'v1.2.2-beta'; 'beta' > 'alpha'.
    if not c_pre:
        return False
    if not r_pre:
        return True
    return r_pre > c_pre


def get_launcher_exe_path() -> Optional[str]:
    """Ruta del exe actual. None cuando se ejecuta desde código fuente."""
    if getattr(sys, 'frozen', False):
        exe = os.path.abspath(sys.executable)
        if exe.lower().endswith('.exe'):
            return exe
    return None


def fetch_update_manifest(url: str = '', timeout: float = 20) -> dict:
    """Descarga y valida el manifest de actualizaciones."""
    url = (url or UPDATE_MANIFEST_URL or '').strip()
    if not url:
        raise RuntimeError('update_manifest_missing')
    response = request_with_retries('GET', url, timeout=timeout, max_attempts=3)
    try:
        data = json.loads(response.content.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'El manifest de actualización no es JSON válido: {exc}')
    if not data.get('version') or not data.get('url'):
        raise RuntimeError('El manifest de actualización no contiene version/url.')
    return data


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: str, expected: str) -> bool:
    if not expected:
        return True
    expected = (expected or '').strip().lower()
    if expected.startswith('sha256:'):
        expected = expected[len('sha256:'):]
    try:
        return sha256_of(path).lower() == expected
    except OSError:
        return False


def download_update(url: str, dest_path: str, on_progress: ProgressCallback = None, on_status: StatusCallback = None) -> str:
    """Descarga el exe nuevo con reintentos y reanudación. Devuelve dest_path."""
    if on_status:
        on_status('Descargando actualización...')
    download_file_with_retries(url, dest_path, timeout=300, chunk_size=262144, on_progress=on_progress)
    return dest_path


def spawn_apply_update(new_exe: str, old_exe: str) -> bool:
    """Lanza un finalizador oculto que reemplaza old_exe por new_exe y lo abre.

    El finalizador:
      1) espera hasta 120 s a que el launcher actual salga (libera el lock del exe);
      2) si sigue bloqueado, fuerza el cierre de los procesos cuyo ejecutable sea
         old_exe (el bootloader de onefile retiene el archivo);
      3) borra el viejo, mueve el nuevo y lo vuelve a lanzar;
      4) escribe KazLauncher_updater.log junto al exe para poder depurar fallos.
    """
    if sys.platform != 'win32':
        return False
    if not new_exe or not old_exe or not os.path.isfile(new_exe):
        return False
    log_path = os.path.join(os.path.dirname(os.path.abspath(old_exe)), 'KazLauncher_updater.log')
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "$old='" + str(old_exe).replace("'", "''") + "';"
        "$new='" + str(new_exe).replace("'", "''") + "';"
        "$log='" + str(log_path).replace("'", "''") + "';"
        "function Log($m){ try{ Add-Content -LiteralPath $log -Value ((Get-Date -Format 'HH:mm:ss') + ' ' + $m) }catch{} };"
        "Log 'Finalizador iniciado';"
        "$deadline=(Get-Date).AddSeconds(120);"
        "while((Get-Date) -lt $deadline){"
        "  try{ Remove-Item -LiteralPath $old -Force -ErrorAction Stop; Log 'Exe anterior eliminado'; break }catch{}"
        "  Start-Sleep -Milliseconds 500 };"
        "if(Test-Path -LiteralPath $old){"
        "  Log 'Exe anterior aun bloqueado; cerrando procesos que lo usan';"
        "  Get-CimInstance Win32_Process -Filter \"Name='" + os.path.basename(old_exe).replace("'", "''") + "'\" -ErrorAction SilentlyContinue | "
        "    Where-Object { $_.ExecutablePath -eq $old } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue };"
        "  Start-Sleep -Seconds 2;"
        "  Remove-Item -LiteralPath $old -Force -ErrorAction SilentlyContinue };"
        "if(Test-Path -LiteralPath $new){ Move-Item -LiteralPath $new -Destination $old -Force; Log 'Nuevo exe colocado' };"
        "if(Test-Path -LiteralPath $old){ Start-Process -FilePath $old; Log 'Nuevo exe lanzado' }"
        "else{ Log 'ERROR: no se pudo reemplazar el ejecutable' };"
    )
    try:
        encoded = base64.b64encode(ps.encode('utf-16-le')).decode('ascii')
        subprocess.Popen(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-EncodedCommand', encoded],
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        return True
    except Exception as exc:
        logging.warning('No se pudo lanzar el finalizador de actualización: %s', exc)
        return False


# ── Workers (QThread) ───────────────────────────────────────────────────────
from PySide6.QtCore import QThread, Signal  # noqa: E402


class UpdateCheckWorker(QThread):
    """Consulta el manifest en segundo plano y compara la versión."""

    finished_check = Signal(bool, object)

    def __init__(self, current_version: str, manifest_url: str = '', parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.manifest_url = (manifest_url or UPDATE_MANIFEST_URL or '').strip()

    def run(self):
        try:
            info = fetch_update_manifest(self.manifest_url)
            info['update_available'] = bool(info.get('version') and is_newer_version(self.current_version, info['version']))
            self.finished_check.emit(True, info)
        except Exception as exc:
            self.finished_check.emit(False, {'error': str(exc)})


class UpdateDownloadWorker(QThread):
    """Descarga el exe nuevo con progreso y verificación SHA-256."""

    progress = Signal(int)
    status = Signal(str)
    finished_download = Signal(bool, str, str)

    def __init__(self, url: str, dest_path: str, expected_sha256: str = '', parent=None):
        super().__init__(parent)
        self.url = url
        self.dest_path = dest_path
        self.expected_sha256 = expected_sha256

    def run(self):
        try:
            def on_progress(current: int, total: int):
                if total > 0:
                    self.progress.emit(min(99, int(current * 100 / total)))

            def on_status(message: str):
                self.status.emit(message)

            download_update(self.url, self.dest_path, on_progress=on_progress, on_status=on_status)
            if self.expected_sha256:
                self.status.emit('Verificando integridad...')
                if not verify_sha256(self.dest_path, self.expected_sha256):
                    raise RuntimeError('El archivo descargado no coincide con el SHA-256 esperado.')
            self.progress.emit(100)
            self.finished_download.emit(True, self.dest_path, '')
        except Exception as exc:
            self.finished_download.emit(False, '', str(exc))
