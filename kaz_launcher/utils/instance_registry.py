"""Instancias de modpack remoto instaladas en .kazlauncher/instancias/."""
from __future__ import annotations
import json
import os
from typing import Any, Optional
import minecraft_launcher_lib
from .helpers import get_base_version
INSTANCE_META_FILE = 'kaz_instance.json'


def resolve_version_id(instance_dir: str, loader: str, game_version: str, loader_version: str) -> Optional[str]:
    """Obtiene el id de versión instalado en una instancia."""
    try:
        installed = minecraft_launcher_lib.utils.get_installed_versions(instance_dir)
    except Exception:
        return None
    loader = (loader or 'forge').lower()
    game_version = str(game_version).strip()
    if loader == 'forge':
        best = None
        for entry in installed:
            vid = entry['id']
            if 'forge' not in vid or game_version not in vid:
                continue
            else:
                if loader_version and loader_version not in vid:
                        continue
                best = vid
        return best
    else:
        if loader == 'fabric':
            for entry in installed:
                vid = entry['id']
                if 'fabric' in vid and game_version in vid:
                        return vid
        else:
            if loader == 'neoforge':
                for entry in installed:
                    vid = entry['id']
                    if 'neoforge' not in vid:
                        continue
                    else:
                        if loader_version and loader_version not in vid:
                                continue
                        return vid
            else:
                ids = [entry['id'] for entry in installed]
                return game_version if game_version in ids else None
def load_instance_meta(instance_dir: str) -> dict[str, Any]:
    path = os.path.join(instance_dir, INSTANCE_META_FILE)
    if not os.path.isfile(path):
        return {}
    else:
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
# return {'source': 'remote', 'loader_version': '', 'manifest_url': '', 'manifest_revision': '', 'actualizacion': False}
def save_instance_meta(instance_dir: str, *, name: str, version_id: str, loader: str, game_version: str, source: str = 'remote', loader_version: str = '', manifest_url: str = '', manifest_revision: str = '', actualizacion: bool = False) -> None:
    os.makedirs(instance_dir, exist_ok=True)
    meta = {'name': name, 'version_id': version_id, 'loader': loader, 'game_version': game_version, 'source': source, 'loader_version': loader_version, 'manifest_url': manifest_url, 'manifest_revision': manifest_revision, 'actualizacion': actualizacion}
    path = os.path.join(instance_dir, INSTANCE_META_FILE)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
def scan_remote_instances(minecraft_directory: str) -> list[dict[str, Any]]:
    """Lista instancias en instancias/ con versión instalada."""
    base = os.path.join(minecraft_directory, 'instancias')
    if not os.path.isdir(base):
        return []
    else:
        results = []
        for folder_name in sorted(os.listdir(base)):
            instance_dir = os.path.join(base, folder_name)
            if not os.path.isdir(instance_dir):
                continue
            else:
                meta_path = os.path.join(instance_dir, INSTANCE_META_FILE)
                meta = {}
                if os.path.isfile(meta_path):
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                    except (json.JSONDecodeError, OSError):
                        meta = {}
                version_id = meta.get('version_id')
                loader = (meta.get('loader') or 'forge').lower()
                game_version = str(meta.get('game_version') or '').strip()
                display_name = meta.get('name') or folder_name
                if not version_id and game_version:
                        version_id = resolve_version_id(instance_dir, loader, game_version, meta.get('loader_version', ''))
                if not version_id:
                    try:
                        installed = minecraft_launcher_lib.utils.get_installed_versions(instance_dir)
                    except Exception:
                        installed = []
                    for entry in installed:
                        vid = entry['id']
                        if 'neoforge' in vid:
                            version_id = vid
                            loader = 'neoforge'
                            break
                        else:
                            if 'fabric' in vid:
                                version_id = vid
                                loader = 'fabric'
                                break
                            else:
                                if 'forge' in vid:
                                    version_id = vid
                                    loader = 'forge'
                                    break
                    if not version_id and installed:
                            version_id = installed[(-1)]['id']
                            loader = 'vanilla'
                if version_id:
                    results.append({'name': display_name, 'version_id': version_id, 'instance_dir': instance_dir, 'loader': loader, 'game_version': game_version or get_base_version(version_id), 'source': meta.get('source', 'remote'), 'manifest_url': meta.get('manifest_url', ''), 'manifest_revision': meta.get('manifest_revision', ''), 'actualizacion': bool(meta.get('actualizacion'))})
        return results