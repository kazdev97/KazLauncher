"""Rich Presence de Discord (opcional; requiere pypresence y Discord abierto)."""
from __future__ import annotations

import atexit
import logging
import threading
from typing import Any, Optional

DISCORD_APPLICATION_ID = '1257798947699691621'

_rpc_lock = threading.Lock()
_rpc_client: Any = None
_shutdown_requested = False
_atexit_registered = False


def _disconnect_client(client: Any) -> None:
    try:
        client.clear()
    except Exception as exc:
        logging.debug('Discord clear: %s', exc)
    try:
        client.close()
    except Exception as exc:
        logging.debug('Discord close: %s', exc)


def _presence_worker(version: str) -> None:
    global _rpc_client
    try:
        from pypresence import Presence
    except ImportError:
        logging.info('pypresence no instalado; se omite Discord Rich Presence.')
        return None
    client = Presence(DISCORD_APPLICATION_ID)
    client.connect()
    try:
        with _rpc_lock:
            if _shutdown_requested:
                _disconnect_client(client)
                return
            client.update(details='KazLauncher', state=f'Versión {version}')
            _rpc_client = client
    except Exception as exc:
        logging.info('Discord Rich Presence no disponible: %s', exc)


def start_discord_presence(version: str) -> None:
    global _atexit_registered
    global _shutdown_requested
    _shutdown_requested = False
    if not _atexit_registered:
        atexit.register(stop_discord_presence)
        _atexit_registered = True
    threading.Thread(target=_presence_worker, args=(version,), daemon=True).start()


def update_discord_playing(modpack_name: str, mc_version: str, loader: str) -> None:
    """Actualiza Discord mientras se juega un modpack/instancia."""

    def _worker():
        global _rpc_client
        try:
            from pypresence import Presence
        except ImportError:
            return None
        with _rpc_lock:
            client = _rpc_client
        if client is None:
            client = Presence(DISCORD_APPLICATION_ID)
            client.connect()
            try:
                with _rpc_lock:
                    if _shutdown_requested:
                        _disconnect_client(client)
                        return
                    _rpc_client = client
            except Exception as exc:
                logging.debug('Discord update connect: %s', exc)
                return
        details = modpack_name or 'Minecraft'
        state_parts = [p for p in [mc_version, loader] if p]
        state = ' · '.join(state_parts) if state_parts else 'Jugando'
        try:
            with _rpc_lock:
                if _rpc_client is not None:
                    _rpc_client.update(details=details, state=state)
        except Exception as exc:
            logging.debug('Discord update playing: %s', exc)

    threading.Thread(target=_worker, daemon=True).start()


def reset_discord_launcher(version: str) -> None:
    """Vuelve al estado del launcher tras cerrar Minecraft."""

    def _worker():
        with _rpc_lock:
            client = _rpc_client
        if client is None:
            return
        try:
            with _rpc_lock:
                if _rpc_client is not None:
                    _rpc_client.update(details='KazLauncher', state=f'Versión {version}')
        except Exception as exc:
            logging.debug('Discord reset launcher: %s', exc)

    threading.Thread(target=_worker, daemon=True).start()


def stop_discord_presence() -> None:
    global _shutdown_requested
    global _rpc_client
    _shutdown_requested = True
    with _rpc_lock:
        client = _rpc_client
        _rpc_client = None
    if client is not None:
        _disconnect_client(client)
        logging.info('Discord Rich Presence cerrada.')
