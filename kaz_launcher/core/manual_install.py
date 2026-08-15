"""Instalación manual de Vanilla / Forge / NeoForge / Fabric en una instancia."""
from __future__ import annotations
import os
import re
from typing import Callable, Optional
import minecraft_launcher_lib
from minecraft_launcher_lib import mod_loader
from minecraft_launcher_lib.exceptions import UnsupportedVersion
from kaz_launcher.core.remote_modpack import get_java_for_installer
from kaz_launcher.utils.download import friendly_download_error, run_install_with_retries
from kaz_launcher.utils.forge_install import run_forge_install_tolerant
from kaz_launcher.utils.instance_registry import resolve_version_id, save_instance_meta
StatusCallback = Optional[Callable[[str], None]]
def get_minecraft_versions_for_loader(loader: str) -> list[str]:
    loader = (loader or 'vanilla').lower()
    if loader == 'vanilla':
        return [v['id'] for v in minecraft_launcher_lib.utils.get_version_list() if v['type'] == 'release']
    else:
        try:
            ml = mod_loader.get_mod_loader(loader)
            versions = ml.get_minecraft_versions(True)
            if not versions:
                versions = ml.get_minecraft_versions(False)
            return versions
        except Exception:
            return []
def get_loader_versions_for(loader: str, minecraft_version: str) -> list[str]:
    loader = (loader or '').lower()
    if loader in ['vanilla', '']:
        return []
    else:
        try:
            ml = mod_loader.get_mod_loader(loader)
            versions = ml.get_loader_versions(minecraft_version, True)
            if not versions:
                versions = ml.get_loader_versions(minecraft_version, False)
            return versions
        except (UnsupportedVersion, Exception):
            return []
def _sanitize_folder_name(text: str) -> str:
    safe = re.sub('[^A-Za-z0-9._-]+', '_', str(text)).strip('_')
    return re.sub('_+', '_', safe) or 'Instalacion'
def _unique_instance_dir(base_dir: str, folder_name: str) -> str:
    os.makedirs(base_dir, exist_ok=True)
    candidate = os.path.join(base_dir, folder_name)
    if not os.path.exists(candidate):
        return candidate
    else:
        index = 2
        while os.path.exists(f'{candidate}_{index}'):
            index += 1
        return f'{candidate}_{index}'
def build_instance_display_name(loader: str, mc_version: str, loader_version: str='') -> str:
    labels = {'vanilla': 'Vanilla', 'forge': 'Forge', 'neoforge': 'NeoForge', 'fabric': 'Fabric'}
    prefix = labels.get(loader, loader.capitalize())
    if loader == 'vanilla' or not loader_version:
        return f'{prefix} {mc_version}'
    else:
        return f'{prefix} {mc_version} ({loader_version})'
# return {'java_path': None, 'on_status': None}
def install_manual_instance(*, loader: str, minecraft_version: str, loader_version: str, minecraft_directory: str, java_path: Optional[str], on_status: StatusCallback) -> tuple[bool, str, Optional[str], Optional[str]]:
    """\n    Instala en instancias/{nombre}. Devuelve (ok, mensaje, version_id, instance_dir).\n    """
    loader = (loader or 'vanilla').lower()
    mc_version = str(minecraft_version).strip()
    loader_version = str(loader_version or '').strip()
    def status(msg: str):
        if on_status:
            on_status(msg)
    if not mc_version:
        return (False, 'Selecciona una versión de Minecraft.', None, None)
    instancias_root = os.path.join(minecraft_directory, 'instancias')
    folder_bits = [loader, mc_version.replace('.', '_')]
    if loader != 'vanilla' and loader_version:
        folder_bits.append(loader_version.replace('.', '_'))
    instance_dir = _unique_instance_dir(instancias_root, _sanitize_folder_name('_'.join(folder_bits)))
    os.makedirs(instance_dir, exist_ok=True)
    callback = {'setStatus': lambda t: status(t)}
    java_exe = get_java_for_installer(java_path, mc_version=mc_version, on_status=status)
    try:
        if loader == 'vanilla':
            status(f'Instalando Minecraft {mc_version}...')
            run_install_with_retries(lambda: minecraft_launcher_lib.install.install_minecraft_version(mc_version, instance_dir, callback=callback))
            version_id = mc_version
        else:
            ml = mod_loader.get_mod_loader(loader)
            if not loader_version:
                try:
                    loader_version = run_install_with_retries(lambda: ml.get_latest_loader_version(mc_version))
                except UnsupportedVersion as exc:
                    return (False, str(exc), None, None)
            status(f'Instalando {ml.get_name()} {loader_version} para Minecraft {mc_version}...')
            if loader == 'forge':
                expected_id = ml.get_installed_version(mc_version, loader_version)
                run_forge_install_tolerant(lambda: ml.install(mc_version, instance_dir, loader_version=loader_version, callback=callback, java=java_exe), instance_dir, expected_id)
                version_id = expected_id
            else:
                version_id = run_install_with_retries(lambda: ml.install(mc_version, instance_dir, loader_version=loader_version, callback=callback, java=java_exe))
    except Exception as exc:
        return (False, friendly_download_error(exc, str(exc)), None, None)
    if not version_id:
        version_id = resolve_version_id(instance_dir, loader, mc_version, loader_version)
    if not version_id:
        return (False, 'La instalación terminó pero no se detectó la versión instalada.', None, None)
    display_name = build_instance_display_name(loader, mc_version, loader_version)
    save_instance_meta(instance_dir, name=display_name, version_id=version_id, loader=loader, game_version=mc_version, source='manual', loader_version=loader_version)
    status('Instalación completada.')
    return (True, '', version_id, instance_dir)