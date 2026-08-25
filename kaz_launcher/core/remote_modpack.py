"""\nDetección e instalación de modpacks desde una carpeta (ej. ClaroDrive en la nube).\nEl launcher escanea la carpeta configurada en busca de archivos modpack.json\ny puede instalar versión de Minecraft + Forge/Fabric y todos los mods listados.\n"""
import os
import re
import json
import logging
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional
import minecraft_launcher_lib
from minecraft_launcher_lib import mod_loader
import minecraft_launcher_lib.fabric
from . import mod_manager
from .instance_sync import collect_manifest_files, sync_instance_files, sync_remote_mods, iter_mods_folder_urls
from .remote_url import fetch_remote_text, resolve_download_url
from kaz_launcher.utils.download import download_file_with_retries, friendly_download_error, run_install_with_retries
from kaz_launcher.utils.forge_install import run_forge_install_tolerant
MANIFEST_FILENAME = 'modpack.json'
def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    else:
        text = str(value or '').strip().lower()
        return text in ['true', '1', 'yes', 'si', 'sí']
def _parse_txt_extras(content: str) -> dict:
    extras = {}
    for line in str(content).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(('{', '[', '#', '//', '\"', '\'')):
            continue
        else:
            if '=' not in stripped:
                continue
            else:
                key, _, val = stripped.partition('=')
                key = key.strip().lower().replace(' ', '_')
                val = val.strip().strip('\"').strip('\'')
                if key in ['actualizacion', 'actualización', 'update', 'updates']:
                    extras['actualizacion'] = _parse_bool(val)
                else:
                    if key == 'revision':
                        extras['revision'] = val
                    else:
                        if key in ('name', 'nombre') and val:
                            extras['name'] = val
                        else:
                            if key in ['pass', 'password', 'contraseña', 'contrasena', 'clave']:
                                extras['pass'] = val
    return extras
def _extract_json_block(text: str) -> str:
    """Extrae el bloque JSON principal ({...} o [...]) ignorando líneas TXT previas."""
    text = text.strip()
    for opener, closer in [('{', '}'), ('[', ']')]:
        start = text.find(opener)
        if start < 0:
            continue
        else:
            depth = 0
            in_string = False
            escape = False
            for index in range(start, len(text)):
                ch = text[index]
                if in_string:
                    if escape:
                        escape = False
                    else:
                        if ch == '\\':
                            escape = True
                        else:
                            if ch == '\"':
                                in_string = False
                    continue
                else:
                    if ch == '\"':
                        in_string = True
                        continue
                    else:
                        if ch == opener:
                            depth += 1
                        else:
                            if ch == closer:
                                depth -= 1
                                if depth == 0:
                                    return text[start:index + 1]
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        return text[start:end + 1]
    else:
        return text
def _loads_json_robust(json_text: str):
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        content_fixed = json_text.replace(", '\"').replace(", '"').replace('„', '"').replace('‟', '"')
        content_fixed = re.sub('"\\s*(https?://[^\\s"]+)\\s*"', '"\\1"', content_fixed)
        content_fixed = re.sub('([{,]\\s*)(\\w+)(\\s*):', '\\1"\\2"\\3:', content_fixed)
        content_fixed = re.sub(',\\s*([}\\]])', '\\1', content_fixed)
        try:
            return json.loads(content_fixed)
        except json.JSONDecodeError:
            return None
def parse_manifest_content(content: str):
    """\n    Parsea manifest JSON (objeto o lista) y líneas TXT extra.\n    Devuelve dict, list o None.\n    """
    if not content or not str(content).strip():
        return None
    else:
        extras = _parse_txt_extras(content)
        json_text = _extract_json_block(content)
        payload = _loads_json_robust(json_text)
        if payload is None:
            return
        else:
            if isinstance(payload, list):
                result = []
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    else:
                        merged = dict(item)
                        for key in ['actualizacion', 'revision']:
                            if key in extras and key not in merged:
                                    merged[key] = extras[key]
                        if 'pass' in extras and (not merged.get('pass')):
                                merged['pass'] = extras['pass']
                        result.append(merged)
                return result if result else None
            else:
                if not isinstance(payload, dict):
                    return
                else:
                    manifest = dict(payload)
                    for key in ['actualizacion', 'revision']:
                        if key in extras:
                            manifest[key] = extras[key]
                    if 'pass' in extras and 'modpacks' not in manifest and (not manifest.get('pass')):
                                manifest['pass'] = extras['pass']
                    return manifest
def _merge_global_fields(base: dict, global_meta: dict) -> dict:
    merged = dict(base)
    for key in ['actualizacion', 'revision']:
        if key not in merged or merged.get(key) in (None, ''):
            if key in global_meta:
                merged[key] = global_meta[key]
    return merged
def expand_manifests(parsed) -> list[dict]:
    """Convierte manifest único, lista o {modpacks: [...]} en lista de modpacks."""
    if not parsed:
        return []
    else:
        if isinstance(parsed, list):
            return [m for m in parsed if isinstance(m, dict)]
        else:
            if not isinstance(parsed, dict):
                return []
            else:
                global_meta = {k: parsed[k] if k in parsed else None for k in ['actualizacion', 'revision']}
                modpacks = parsed.get('modpacks')
                if isinstance(modpacks, list):
                    return [_merge_global_fields(mp, global_meta) for mp in modpacks if isinstance(mp, dict)]
                else:
                    if parsed.get('name') or parsed.get('game_version') or parsed.get('url') or parsed.get('mods'):
                        return [_merge_global_fields(parsed, global_meta)]
                    else:
                        return []
def format_modpack_label(manifest: dict) -> str:
    """Etiqueta para la lista: Nombre — versión (loader loader_version)."""
    name = manifest.get('name', 'Modpack')
    ver = manifest.get('game_version', '?')
    loader = manifest.get('loader', '?')
    loader_ver = str(manifest.get('loader_version') or '').strip()
    loader_part = f'{loader} {loader_ver}' if loader_ver else str(loader)
    return f'{name}  —  {ver}  ({loader_part})'
def is_actualizacion_enabled(manifest: dict) -> bool:
    return _parse_bool(manifest.get('actualizacion'))
def sanitize_instance_name(name: str) -> str:
    safe = re.sub('[^A-Za-z0-9._-]+', '_', str(name or 'Modpack')).strip('_')
    return re.sub('_+', '_', safe) or 'Modpack'
def resolve_instance_dir(minecraft_dir: str, manifest: dict) -> str:
    folder = sanitize_instance_name(manifest.get('name', 'Modpack'))
    return os.path.join(minecraft_dir, 'instancias', folder)
def instance_is_installed(instance_dir: str) -> bool:
    if not instance_dir or not os.path.isdir(instance_dir):
        return False
    else:
        try:
            installed = minecraft_launcher_lib.utils.get_installed_versions(instance_dir)
            return bool(installed)
        except Exception:
            return os.path.isfile(os.path.join(instance_dir, 'kaz_instance.json'))
def fetch_remote_manifest(url: str) -> Optional[dict]:
    """Descarga el primer manifest (compatibilidad)."""
    manifests = fetch_remote_manifests(url)
    return manifests[0] if manifests else None
def fetch_remote_manifests(url: str) -> list[dict]:
    """Descarga manifest(s) desde URL. Soporta uno o varios modpacks."""
    try:
        content = fetch_remote_text(url, timeout=15)
        parsed = parse_manifest_content(content)
        if parsed is None:
            logging.error('Error crítico de formato en manifest remoto.')
            return []
        else:
            manifests = expand_manifests(parsed)
            if not manifests:
                logging.error('Manifest parseado pero sin modpacks válidos.')
            return manifests
    except Exception as e:
        logging.error('Error al obtener manifest remoto: %s', e)
        return []
def _normalize_clarodrive_download_url(url: str) -> str:
    """Normaliza enlaces de descarga (ClaroDrive, GitHub, Google Drive)."""
    return resolve_download_url(url)
def download_and_extract_zip(url: str, target_dir: str, callback: Optional[dict]=None) -> bool:
    """Descarga un ZIP de modpack y lo extrae en el directorio indicado."""
    callback = callback or {}
    def set_status(text: str):
        callback.get('setStatus', lambda _: None)(text)
    def set_progress(current: int, total: int=0):
        callback.get('setProgress', lambda a, b: None)(current, total)
    url = _normalize_clarodrive_download_url(url)
    os.makedirs(target_dir, exist_ok=True)
    zip_path = os.path.join(target_dir, 'modpack_temp.zip')
    set_status('Descargando modpack ZIP...')
    try:
        def _report(current: int, total: int):
            set_progress(current, total)
        download_file_with_retries(url, zip_path, timeout=60, chunk_size=65536, on_progress=_report)
        set_status('Extrayendo modpack...')
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        mods_dir = os.path.join(target_dir, 'mods')
        jar_files = [name for name in os.listdir(target_dir) if name.lower().endswith('.jar')]
        has_mods_folder = os.path.isdir(mods_dir)
        if jar_files and (not has_mods_folder):
                os.makedirs(mods_dir, exist_ok=True)
                for jf in jar_files:
                    try:
                        os.replace(os.path.join(target_dir, jf), os.path.join(mods_dir, jf))
                    except Exception:
                        pass
                    else:
                        pass
        os.remove(zip_path)
    except Exception as e:
        logging.error('Error descargando/extrayendo modpack: %s', e)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False
    return True
def _extra_java_dirs():
    """Directorios habituales de Java en Windows para el instalador de Forge."""
    if os.name != 'nt':
        return
    else:
        extra = []
        pf = os.environ.get('ProgramFiles', 'C:\\Program Files')
        pfx = os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')
        la = os.environ.get('LOCALAPPDATA', '')
        for base in [pf, pfx]:
            if base:
                extra.extend([os.path.join(base, 'Java'), os.path.join(base, 'Microsoft'), os.path.join(base, 'Eclipse Adoptium'), os.path.join(base, 'AdoptOpenJDK')])
        if la:
            extra.append(os.path.join(la, 'Programs', 'Eclipse Adoptium'))
            extra.append(os.path.join(la, 'Microsoft', 'OpenJDK'))
        return extra
def _bundled_java_for_installer(mc_version: Optional[str]=None) -> Optional[str]:
    """Busca el Java portable que el launcher ya tiene en runtime/jdk-*."""
    from kaz_launcher.utils.java_installer import get_bundled_java_executable
    from kaz_launcher.utils.java_resolver import required_java_major
    majors = []
    if mc_version:
        majors.append(required_java_major(mc_version))
    for m in (17, 21, 8):
        if m not in majors:
            majors.append(m)
    for major in majors:
        exe = get_bundled_java_executable(major)
        if exe:
            return exe
    return None
def get_java_for_installer(java_path_from_settings: Optional[str]=None, mc_version: Optional[str]=None, on_status: Optional[Callable[[str], None]]=None) -> Optional[str]:
    """Obtiene una ruta válida a Java para el instalador de Forge.

    Orden de resolución: ruta configurada en ajustes -> Java del sistema
    (get_java_executable y carpetas estándar) -> Java portable del launcher
    (runtime/jdk-*) -> auto-instalación de Adoptium si no hay nada.
    """
    if (java_path_from_settings or '').strip() and os.path.isfile(java_path_from_settings.strip()):
        return java_path_from_settings.strip()
    try:
        c = minecraft_launcher_lib.utils.get_java_executable()
        if c and os.path.isabs(c) and os.path.isfile(c):
            return c
    except Exception:
        pass
    try:
        for java_dir in minecraft_launcher_lib.java_utils.find_system_java_versions(additional_directories=_extra_java_dirs() or None):
            if not java_dir or not os.path.isdir(java_dir):
                continue
            for exe in ['java.exe', 'javaw.exe']:
                full = os.path.join(java_dir, 'bin', exe)
                if os.path.isfile(full):
                    return full
    except Exception:
        pass
    bundled = _bundled_java_for_installer(mc_version)
    if bundled:
        return bundled
    try:
        from kaz_launcher.utils.java_installer import install_portable_jdk
        from kaz_launcher.utils.java_resolver import required_java_major
        required = required_java_major(mc_version) if mc_version else 17
        return install_portable_jdk(required, on_status=on_status)
    except Exception as exc:
        logging.error('No se pudo instalar Java portable para Forge: %s', exc)
        return None
def scan_folder(folder_path: str) -> list[dict]:
    """\n    Escanea una carpeta en busca de modpack.json (o subcarpetas que lo contengan).\n    Devuelve lista de { \"path\": ruta del manifest, \"name\": nombre, \"manifest\": dict }.\n    """
    if not folder_path or not os.path.isdir(folder_path):
        return []
    else:
        result = []
        for root, _dirs, files in os.walk(folder_path, topdown=True):
            if MANIFEST_FILENAME in files:
                manifest_path = os.path.join(root, MANIFEST_FILENAME)
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    logging.warning('Manifest inválido %s: %s', manifest_path, e)
                else:
                    if isinstance(data, dict):
                        name = data.get('name') or os.path.basename(root) or 'Modpack'
                        result.append({'path': manifest_path, 'name': name, 'manifest': data})
        return result
def validate_manifest(manifest: dict) -> tuple[bool, str]:
    """Valida campos mínimos del manifest. Devuelve (ok, mensaje)."""
    if not manifest.get('game_version'):
        return (False, 'Falta \'game_version\' en el manifest.')
    else:
        if manifest.get('loader') not in ['forge', 'fabric', 'neoforge']:
            return (False, 'El manifest debe tener \'loader\': \'forge\', \'fabric\' o \'neoforge\'.')
        else:
            mods = manifest.get('mods')
            if mods is not None and (not isinstance(mods, list)):
                return (False, 'El listado \'mods\' no es válido.')
            else:
                has_zip = bool(str(manifest.get('url') or manifest.get('modpack_url') or '').strip())
                has_files = bool(collect_manifest_files(manifest))
                has_mods = isinstance(mods, list) and len(mods) > 0
                has_mods_folder = bool(iter_mods_folder_urls(manifest))
                if not has_zip and (not has_files) and (not has_mods) and (not has_mods_folder):
                    return (False, 'El manifest debe incluir \'mods\' (carpeta o lista), \'mods_folder_url\', \'url\'/\'modpack_url\' o \'files\'/\'files_url\'.')
                else:
                    return (True, '')
def verify_remote_instance(manifest: dict, instance_dir: str, lang_dict: dict) -> tuple[bool, str]:
    """Solo comprueba mods/ sin aplicar cambios."""
    from .instance_sync import verify_remote_mods
    report = verify_remote_mods(manifest, instance_dir, lang_dict)
    if report.errors:
        return (False, report.errors[0])
    else:
        if report.up_to_date:
            return (True, lang_dict.get('modpack_up_to_date', 'Ya tienes la última versión.'))
        else:
            details = report.format_diff_details(lang_dict)
            if details:
                return (False, details)
            else:
                return (False, lang_dict.get('modpack_diff_found', 'Hay diferencias en mods.'))
def update_remote_instance_mods(manifest: dict, instance_dir: str, lang_dict: dict, callback: Optional[dict]=None) -> tuple[bool, str]:
    """Actualiza mods/ y archivos de configuración (FancyMenu, resourcepacks, etc.) según el manifest."""
    callback = callback or {}
    def set_status(text: str):
        callback.get('setStatus', lambda _: None)(text)
    file_entries = collect_manifest_files(manifest)
    non_mod_files = [e for e in file_entries if not e['path'].lower().startswith('mods/')]
    if non_mod_files:
        set_status('Sincronizando configs y resourcepacks...')
        ok, err = sync_instance_files(manifest, instance_dir, folders_filter=None, exclude_folders={'mods'}, on_status=set_status)
        if not ok:
            return (False, err)
    report, ok, summary = sync_remote_mods(manifest, instance_dir, lang_dict, on_status=set_status, apply_changes=True, prune_extra=True)
    if not ok:
        return (False, summary)
    else:
        if summary == 'up_to_date' and report.up_to_date and not non_mod_files:
            return (True, lang_dict.get('modpack_up_to_date', 'Ya tienes la última versión.'))
        else:
            return (True, lang_dict.get('modpack_updated_ok', 'Instancia actualizada correctamente.'))
def install_modpack(manifest: dict, minecraft_dir: str, lang_dict: dict, java_path: Optional[str]=None, callback: Optional[dict]=None, target_instance_dir: Optional[str]=None, mode: str='full') -> tuple[bool, str]:
    """\n    Instala el modpack: versión base + loader + archivos/mods.\n    mode: 'full' | 'mods_only'\n    """
    ok, err = validate_manifest(manifest)
    if not ok:
        return (False, err)
    callback = callback or {}
    def set_status(text: str):
        callback.get('setStatus', lambda _: None)(text)
    def set_progress(current: int, total: int=0):
        if total:
            callback.get('setProgress', lambda a, b: None)(current, total)
    game_version = str(manifest['game_version']).strip()
    loader = str(manifest['loader']).strip().lower()
    loader_version = str(manifest.get('loader_version') or '').strip()
    mods = manifest.get('mods') or []
    zip_url = str(manifest.get('url') or manifest.get('modpack_url') or '').strip()
    if not zip_url and isinstance(mods, list):
        for entry in list(mods):
            try:
                u = str(entry.get('url') or '').strip()
            except Exception:
                u = ''
            if u.lower().endswith('.zip'):
                zip_url = u
                try:
                    mods.remove(entry)
                except ValueError:
                    pass
                break
    working_dir = target_instance_dir or minecraft_dir
    os.makedirs(working_dir, exist_ok=True)
    if mode == 'mods_only':
        return update_remote_instance_mods(manifest, working_dir, lang_dict, callback)
    if zip_url:
        set_status('Descargando y extrayendo modpack ZIP...')
        if not download_and_extract_zip(zip_url, working_dir, callback):
            return (False, f'Error descargando o extrayendo el modpack desde {zip_url}')
    file_entries = collect_manifest_files(manifest)
    non_mod_files = [e for e in file_entries if not e['path'].lower().startswith('mods/')]
    if non_mod_files:
        set_status('Sincronizando archivos de configuración...')
        ok, err = sync_instance_files(manifest, working_dir, folders_filter=None, exclude_folders={'mods'}, on_status=set_status)
        if not ok:
            return (False, err)
    installed_ids = [v['id'] for v in minecraft_launcher_lib.utils.get_installed_versions(working_dir)]
    if game_version not in installed_ids:
        set_status(f'Instalando Minecraft {game_version}...')
        try:
            run_install_with_retries(lambda: minecraft_launcher_lib.install.install_minecraft_version(game_version, working_dir, callback=callback))
        except Exception as e:
            return (False, f'Error instalando Minecraft {game_version}: {friendly_download_error(e)}')
    if loader == 'forge':
        try:
            if loader_version:
                if game_version in loader_version or '-' in loader_version:
                    forge_version = loader_version if '-' in loader_version else f'{game_version}-{loader_version}'
                else:
                    forge_version = f'{game_version}-{loader_version}'
                if not run_install_with_retries(lambda: minecraft_launcher_lib.forge.is_forge_version_valid(forge_version)):
                    forge_version = run_install_with_retries(lambda: minecraft_launcher_lib.forge.find_forge_version(game_version)) or forge_version
            else:
                forge_version = run_install_with_retries(lambda: minecraft_launcher_lib.forge.find_forge_version(game_version))
            if not forge_version:
                return (False, f'No se encontró una versión de Forge para {game_version}.')
        except Exception as e:
            return (False, f'Error listando Forge: {friendly_download_error(e)}')
        installed = minecraft_launcher_lib.utils.get_installed_versions(working_dir)
        version_id_to_use = None
        for v in installed:
            vid = v['id']
            if 'forge' in vid and game_version in vid and (not loader_version or loader_version in vid):
                version_id_to_use = vid
                break
        if not version_id_to_use:
            set_status(f'Instalando Forge {forge_version}...')
            java_exe = get_java_for_installer(java_path, mc_version=game_version, on_status=set_status)
            try:
                run_forge_install_tolerant(
                    lambda: minecraft_launcher_lib.forge.install_forge_version(forge_version, working_dir, callback=callback, java=java_exe),
                    working_dir,
                    minecraft_launcher_lib.forge.forge_to_installed_version(forge_version),
                )
            except Exception as e:
                msg = friendly_download_error(e)
                if isinstance(e, OSError) and getattr(e, 'errno', None) == 2:
                    msg = f'{msg} No se encontró Java para ejecutar el instalador de Forge.'
                return (False, f'Error instalando Forge: {msg}')
    elif loader == 'fabric':
        installed = minecraft_launcher_lib.utils.get_installed_versions(working_dir)
        has_fabric = any(('fabric' in v['id'] for v in installed))
        if not has_fabric:
            set_status(f'Instalando Fabric para {game_version}...')
            try:
                run_install_with_retries(lambda: minecraft_launcher_lib.fabric.install_fabric(game_version, working_dir, callback=callback))
            except Exception as e:
                return (False, f'Error instalando Fabric: {friendly_download_error(e)}')
    elif loader == 'neoforge':
        try:
            ml = mod_loader.get_mod_loader('neoforge')
            if not loader_version:
                loader_version = run_install_with_retries(lambda: ml.get_latest_loader_version(game_version))
            installed = minecraft_launcher_lib.utils.get_installed_versions(working_dir)
            has_neoforge = any(('neoforge' in v['id'] for v in installed))
            if not has_neoforge:
                set_status(f'Instalando NeoForge {loader_version}...')
                java_exe = get_java_for_installer(java_path, mc_version=game_version, on_status=set_status)
                run_install_with_retries(lambda: ml.install(game_version, working_dir, loader_version=loader_version, callback=callback, java=java_exe))
        except Exception as e:
            return (False, f'Error instalando NeoForge: {friendly_download_error(e)}')
    if iter_mods_folder_urls(manifest) or mods:
        set_status('Sincronizando mods desde carpeta remota...')
        report, ok, err = sync_remote_mods(manifest, working_dir, lang_dict, on_status=set_status, apply_changes=True, prune_extra=True)
        if not ok:
            return (False, err)
    set_status('Modpack instalado correctamente.')
    return (True, '')
def install_mrpack(mrpack_path: str, minecraft_dir: str, lang_dict: dict, progress_callback=None, stop_flag=None) -> tuple[bool, str, dict]:
    """\n    Instala un modpack desde un archivo .mrpack (Modrinth Modpack).\n    Devuelve (success, message, result_dict).\n    """
    if progress_callback is None:
        progress_callback = lambda msg: None
    if stop_flag is None:
        stop_flag = lambda: False
    def status(msg):
        progress_callback(msg)

    try:
        with zipfile.ZipFile(mrpack_path, 'r') as zf:
            if 'modrinth.index.json' not in zf.namelist():
                return (False, 'Invalid mrpack: missing modrinth.index.json', {})
            index_data = json.loads(zf.read('modrinth.index.json'))
        name = index_data.get('name', 'Unknown Modpack')
        version_id_str = index_data.get('versionId', 'unknown')
        deps = index_data.get('dependencies', {})
        mc_version = deps.get('minecraft', '')
        files = index_data.get('files', [])

        loader = 'forge'
        loader_version = ''
        for dep_key, dep_val in deps.items():
            if dep_key == 'forge':
                loader = 'forge'
                loader_version = dep_val
                break
            elif dep_key == 'fabric-loader':
                loader = 'fabric'
                loader_version = dep_val
                break
            elif dep_key == 'neoforge':
                loader = 'neoforge'
                loader_version = dep_val
                break
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]+', '_', name).strip('_').lower() or 'modpack'
        instances_base = os.path.join(minecraft_dir, 'instancias')
        os.makedirs(instances_base, exist_ok=True)
        instance_dir = os.path.join(instances_base, f'{safe_name}_{version_id_str}')
        counter = 1
        while os.path.exists(instance_dir):
            instance_dir = os.path.join(instances_base, f'{safe_name}_{version_id_str}_{counter}')
            counter += 1
        os.makedirs(instance_dir, exist_ok=True)

        status(f'Installing Minecraft {mc_version}...')
        installed_ids = [v['id'] for v in minecraft_launcher_lib.utils.get_installed_versions(instance_dir)]
        if mc_version not in installed_ids:
            run_install_with_retries(lambda: minecraft_launcher_lib.install.install_minecraft_version(mc_version, instance_dir))
        if loader == 'forge':
            status(f'Installing Forge {loader_version}...')
            forge_version = f'{mc_version}-{loader_version}' if '-' not in loader_version else loader_version
            run_forge_install_tolerant(
                lambda: minecraft_launcher_lib.forge.install_forge_version(forge_version, instance_dir, java=get_java_for_installer(None, mc_version=mc_version, on_status=status)),
                instance_dir,
                minecraft_launcher_lib.forge.forge_to_installed_version(forge_version),
            )
        elif loader == 'fabric':
            status(f'Installing Fabric loader {loader_version} for MC {mc_version}...')
            if loader_version:
                run_install_with_retries(lambda: minecraft_launcher_lib.fabric.install_fabric(mc_version, instance_dir, loader_version=loader_version))
            else:
                run_install_with_retries(lambda: minecraft_launcher_lib.fabric.install_fabric(mc_version, instance_dir))
        elif loader == 'neoforge':
            status(f'Installing NeoForge {loader_version}...')
            ml = mod_loader.get_mod_loader('neoforge')
            java_path = None
            if not loader_version:
                loader_version = run_install_with_retries(lambda: ml.get_latest_loader_version(mc_version))
            run_install_with_retries(lambda: ml.install(mc_version, instance_dir, loader_version=loader_version, java=get_java_for_installer(java_path, mc_version=mc_version, on_status=status)))

        installed = minecraft_launcher_lib.utils.get_installed_versions(instance_dir)
        version_id = ''
        for v in installed:
            if loader == 'forge' and 'forge' in v['id'] and (mc_version in v['id']):
                version_id = v['id']
                break
            elif loader == 'fabric' and 'fabric' in v['id'] and (mc_version in v['id']):
                version_id = v['id']
                break
            elif loader == 'neoforge' and 'neoforge' in v['id']:
                version_id = v['id']
                break
        if not version_id and installed:
            version_id = installed[(-1)]['id']
        mods_dir = os.path.join(instance_dir, 'mods')
        os.makedirs(mods_dir, exist_ok=True)

        jar_files = []
        for file_entry in files:
            downloads = file_entry.get('downloads', [])
            if not downloads:
                continue
            rel_path = file_entry.get('path', '')
            file_name = os.path.basename(rel_path) if rel_path else 'mod.jar'
            if file_name.endswith('.jar'):
                jar_files.append((file_name, downloads))
        if jar_files:
            if stop_flag():
                return (False, 'Installation cancelled', {})
            status(f'Downloading {len(jar_files)} mods...')
            from .mod_manager import get_session
            from kaz_launcher.utils.download import download_file_with_retries
            def _download_one(args) -> tuple[str, bool]:
                file_name, downloads = args
                for dl_url in downloads:
                    resolved = resolve_download_url(dl_url)
                    if not resolved:
                        continue
                    try:
                        dest = os.path.join(mods_dir, file_name)
                        download_file_with_retries(resolved, dest, session=get_session(), timeout=60, chunk_size=65536)
                        return (file_name, True)
                    except Exception:
                        continue
                return (file_name, False)
            workers = min(8, len(jar_files))
            done_count = 0
            total_count = len(jar_files)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_download_one, args) for args in jar_files]
                for fut in as_completed(futures):
                    file_name, ok = fut.result()
                    done_count += 1
                    status(f'Downloading mods ({done_count}/{total_count})...')
                    if not ok:
                        status(f'Warning: Could not download {file_name}')

        override_dir_name = index_data.get('overrides', 'overrides')
        status('Extracting overrides...')
        with zipfile.ZipFile(mrpack_path, 'r') as zf:
            for member in zf.namelist():
                if member.startswith(override_dir_name + '/') and (not member.endswith('/')):
                    rel = os.path.relpath(member, override_dir_name)
                    dest = os.path.join(instance_dir, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with zf.open(member) as src:
                        with open(dest, 'wb') as dst:
                            dst.write(src.read())
        from ..utils.instance_registry import save_instance_meta
        save_instance_meta(instance_dir, name=name, version_id=version_id, loader=loader, game_version=mc_version, source='mrpack', loader_version=loader_version, actualizacion=False)
        status(f'Modpack \'{name}\' installed successfully.')
        return (True, f'Modpack \'{name}\' installed at {instance_dir}.', {'version_id': version_id, 'instance_dir': instance_dir, 'loader': loader, 'name': name, 'game_version': mc_version})
    except Exception as e:
        logging.exception('mrpack install error')
        return (False, f'mrpack installation error: {friendly_download_error(e, str(e))}', {})