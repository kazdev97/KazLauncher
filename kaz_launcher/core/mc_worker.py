import os
import sys
import uuid
import subprocess
import re
import traceback
import logging
import shutil
from datetime import datetime
from PySide6.QtCore import QThread, Signal
import minecraft_launcher_lib
from requests.exceptions import RequestException
from .profile_manager import create_launcher_profiles_if_needed, add_profile
from ..config import resources
from ..utils.java_resolver import is_jni_java_error, parse_found_major_from_class_error, parse_required_major_from_class_error, required_java_major, resolve_java_for_minecraft
from ..utils.download import run_install_with_retries
from ..utils.forge_install import run_forge_install_tolerant
class GameProcessError(Exception):
    def __init__(self, message, exit_code, output=''):
        super().__init__(message)
        self.exit_code = exit_code
        self.output = output
class InterruptedError(Exception):
    pass
class MinecraftWorker(QThread):
    progress_update = Signal(int, int, str)
    finished = Signal(str, object)
    log_message = Signal(str)
    def __init__(self, mc_version, username, minecraft_dir, client_token, memory_gb=2, fullscreen=False, options=None, lang='es', mod_loader=None, auth_uuid=None, auth_token=None):
        super().__init__()
        self.mc_version = mc_version
        self.username = username
        self.minecraft_dir = minecraft_dir
        self.client_token = client_token
        self.memory_gb = memory_gb
        self.fullscreen = fullscreen
        self.options = options if options else {}
        self.lang = lang
        self.mod_loader = mod_loader
        self.auth_uuid = auth_uuid
        self.auth_token = auth_token
        self._is_running = True
        self._versions_before_install = set()
        self._is_installing = False
    def stop(self):
        self.log_message.emit('Cancellation requested...')
        self._is_running = False
    @staticmethod
    def _looks_like_invalid_jvm_args(output: str) -> bool:
        if not output:
            return False
        else:
            needles = ['Unrecognized option', 'Could not create the Java Virtual Machine', 'A fatal exception has occurred', 'Invalid maximum heap size', 'Error: Could not create JVM', 'Error: A JNI error has occurred']
            return any((n.lower() in output.lower() for n in needles))
    def _get_stoppable_callback(self):
        lang_dict = resources.LANGUAGES[self.lang]
        def set_status(text):
            if not self._is_running:
                raise InterruptedError()
            else:
                self.log_and_update_status(text)
        def set_progress(value, max_value=0):
            if not self._is_running:
                raise InterruptedError()
            else:
                if max_value > 0:
                    status_text = lang_dict.get('downloading_files', 'Downloading files')
                    self.progress_update.emit(value, max_value, status_text)
        return {'setStatus': set_status, 'setProgress': set_progress}
    def _forge_client_jar_path(self, forge_version_id: str) -> str:
        """\n        forge_version_id esperado: \"1.20.1-forge-47.4.5\"\n        jar esperado: libraries/net/minecraftforge/forge/1.20.1-47.4.5/forge-1.20.1-47.4.5-client.jar\n        """
        try:
            base_mc, _forge_word, forge_ver = forge_version_id.split('-', 2)
        except ValueError:
            return ''
        forge_lib_version = f'{base_mc}-{forge_ver}'
        return os.path.join(self.minecraft_dir, 'libraries', 'net', 'minecraftforge', 'forge', forge_lib_version, f'forge-{forge_lib_version}-client.jar')
    def _ensure_forge_install_complete(self, forge_version_id: str, callback) -> None:
        """\n        Si faltan jars clave de Forge, re-ejecuta la instalación para reparar.\n        """
        forge_client_jar = self._forge_client_jar_path(forge_version_id)
        if not forge_client_jar:
            return
        else:
            if os.path.exists(forge_client_jar):
                return
            else:
                self.log_message.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Instalación de Forge incompleta (falta {forge_client_jar}). Reinstalando...")
                version_path = os.path.join(self.minecraft_dir, 'versions', forge_version_id)
                try:
                    if os.path.isdir(version_path):
                        shutil.rmtree(version_path)
                except Exception as e:
                    self.log_message.emit(f'No se pudo limpiar la versión Forge dañada: {e}')
                java_path = self._get_java_for_installer()
                run_forge_install_tolerant(lambda: minecraft_launcher_lib.forge.install_forge_version(self.mc_version, self.minecraft_dir, callback=callback, java=java_path), self.minecraft_dir, forge_version_id)
    def _get_java_for_installer(self):
        """\n        Ruta absoluta al ejecutable de Java para el instalador de Forge.\n        El instalador corre en subprocess y necesita un path que exista (no solo \"java\" en PATH).\n        En Windows se prefiere java.exe (el proceso del instalador es por consola).\n        """
        path = (self.options.get('executablePath') or '').strip()
        if path and os.path.isfile(path):
            if path.lower().endswith('javaw.exe'):
                dir_bin = os.path.dirname(path)
                java_exe = os.path.join(dir_bin, 'java.exe')
                if os.path.isfile(java_exe):
                    return java_exe
            return path
        else:
            resolved, _, _ = resolve_java_for_minecraft(self.mc_version, preferred_exe=path or None)
            if resolved:
                if resolved.lower().endswith('javaw.exe'):
                    dir_bin = os.path.dirname(resolved)
                    java_exe = os.path.join(dir_bin, 'java.exe')
                    if os.path.isfile(java_exe):
                        return java_exe
                return resolved
            else:
                self.log_message.emit('[AVISO] No se encontró Java compatible para esta versión de Minecraft. Instala Java 17 o 21 (64 bits) o configura la ruta en Configuración avanzada.')
    def _detect_forge_id(self, versions, base_mc_version):
        build = self.mc_version.split('-')[(-1)]
        for v in versions:
            vid = v['id'] if isinstance(v, dict) else v
            if 'forge' in vid and base_mc_version in vid and (build in vid):
                        return vid
        return
    def _cleanup_interrupted_install(self):
        """Deletes partially installed version directory."""
        self.log_message.emit('Cleaning up partially installed files...')
        try:
            versions_after = {v['id'] for v in minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_dir)}
            newly_created_versions = versions_after - self._versions_before_install
            if not newly_created_versions:
                self.log_message.emit('No new version folders found to clean up.')
                return
            else:
                for version_id in newly_created_versions:
                    version_path = os.path.join(self.minecraft_dir, 'versions', version_id)
                    if os.path.isdir(version_path):
                        shutil.rmtree(version_path)
                        self.log_message.emit(f'Removed broken version directory: {version_id}')
                self.log_message.emit('Cleanup complete.')
        except Exception as e:
            self.log_message.emit(f'Cleanup failed: {e}')
            self.log_message.emit(traceback.format_exc())
    def run(self):
        version_id_to_launch = ''
        game_output = ''
        try:
            callback = self._get_stoppable_callback()
            create_launcher_profiles_if_needed(self.minecraft_dir, self.client_token)
            base_mc_version = self.mc_version.split('-')[0] if self.mod_loader == 'forge' else self.mc_version
            if not self._is_running:
                raise InterruptedError()
            else:
                installed_version_ids = [v['id'] for v in minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_dir)]
                if self.mc_version in installed_version_ids:
                    version_id_to_launch = self.mc_version
                    profile_name = self.mc_version
                    self._is_installing = False
                    self.log_and_update_status(f'Usando versión instalada: {version_id_to_launch}')
                else:
                    self._is_installing = True
                    self._versions_before_install = set(installed_version_ids)
                    if base_mc_version not in installed_version_ids:
                        self.log_and_update_status(f'Base version {base_mc_version} not found. Installing...')
                        run_install_with_retries(lambda: minecraft_launcher_lib.install.install_minecraft_version(base_mc_version, self.minecraft_dir, callback=callback))
                    else:
                        self.log_and_update_status(f'Base version {base_mc_version} already installed.')
                    version_id_to_launch = base_mc_version
                    profile_name = base_mc_version
                    if self.mod_loader in ['fabric', 'forge', 'neoforge']:
                        mods_path = os.path.join(self.minecraft_dir, 'mods')
                        os.makedirs(mods_path, exist_ok=True)
                        if not self._is_running:
                            raise InterruptedError()
                        else:
                            if self.mod_loader == 'fabric':
                                version_id_to_launch = run_install_with_retries(lambda: minecraft_launcher_lib.fabric.install_fabric(base_mc_version, self.minecraft_dir, callback=callback))
                                profile_name = f'{base_mc_version} Fabric'
                            else:
                                if self.mod_loader == 'forge':
                                    all_installed = minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_dir)
                                    version_id_to_launch = self._detect_forge_id(all_installed, base_mc_version)
                                    if not version_id_to_launch:
                                        self.log_and_update_status(f'Installing Forge {self.mc_version}')
                                        java_path = self._get_java_for_installer()
                                        expected_forge = self.mc_version
                                        if 'forge' not in expected_forge:
                                            try:
                                                expected_forge = minecraft_launcher_lib.forge.forge_to_installed_version(expected_forge)
                                            except Exception:
                                                pass
                                        run_forge_install_tolerant(lambda: minecraft_launcher_lib.forge.install_forge_version(self.mc_version, self.minecraft_dir, callback=callback, java=java_path), self.minecraft_dir, expected_forge)
                                        all_installed_after = minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_dir)
                                        version_id_to_launch = self._detect_forge_id(all_installed_after, base_mc_version)
                                        if not version_id_to_launch:
                                            raise Exception(f'Could not find Forge version for {self.mc_version} after installation.')
                                        else:
                                            self.log_and_update_status(f'New Forge version installed: {version_id_to_launch}')
                                    else:
                                        self.log_and_update_status(f'Found existing Forge version: {version_id_to_launch}')
                                        self._ensure_forge_install_complete(version_id_to_launch, callback)
                                    profile_name = f'{base_mc_version} Forge'
                                else:
                                    if self.mod_loader == 'neoforge':
                                        from minecraft_launcher_lib import mod_loader as mll_mod_loader
                                        ml = mll_mod_loader.get_mod_loader('neoforge')
                                        loader_version = self.mc_version if self.mc_version != base_mc_version else None
                                        if not loader_version:
                                            loader_version = run_install_with_retries(lambda: ml.get_latest_loader_version(base_mc_version))
                                        self.log_and_update_status(f'Installing NeoForge {loader_version}...')
                                        java_path = self._get_java_for_installer()
                                        version_id_to_launch = run_install_with_retries(lambda: ml.install(base_mc_version, self.minecraft_dir, loader_version=loader_version, callback=callback, java=java_path))
                                        profile_name = f'{base_mc_version} NeoForge'
                    self._is_installing = False
                    add_profile(self.minecraft_dir, version_id_to_launch, profile_name)
                custom_jvm_args = self.options.get('jvmArguments', [])
                all_jvm_args = [f'-Xmx{self.memory_gb}G', f'-Xms{self.memory_gb}G'] + custom_jvm_args
                token = self.auth_token or '0'
                mc_uuid = self.auth_uuid or str(uuid.uuid3(uuid.NAMESPACE_DNS, self.username))
                launch_options = {'username': self.username, 'uuid': mc_uuid, 'token': token, 'jvmArguments': all_jvm_args, 'fullscreen': self.fullscreen, 'gameDirectory': self.minecraft_dir, 'executablePath': self.options.get('executablePath'), 'resolutionWidth': self.options.get('resolutionWidth'), 'resolutionHeight': self.options.get('resolutionHeight'), 'launchTarget': 'minecraft'}
                launch_options = {k: v for k, v in launch_options.items() if v}
                if not self._is_running:
                    raise InterruptedError()
                else:
                    self.log_and_update_status(resources.LANGUAGES[self.lang]['starting'])
                    command = minecraft_launcher_lib.command.get_minecraft_command(version_id_to_launch, self.minecraft_dir, launch_options)
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0, cwd=self.minecraft_dir)
                    output_lines = []
                    while self._is_running:
                        if process.poll() is not None:
                            break
                        for line in iter(process.stdout.readline, ''):
                            if not line:
                                break
                            else:
                                clean_line = line.strip()
                                self.log_message.emit(clean_line)
                                output_lines.append(clean_line)
                        self.msleep(50)
                    game_output = '\n'.join(output_lines)
                    if not self._is_running:
                        self.log_message.emit('Terminating game process...')
                        process.terminate()
                        process.wait(timeout=5)
                        raise InterruptedError()
                    else:
                        exit_code = process.returncode
                        if exit_code != 0:
                            raise GameProcessError(f'Game process exited with code {exit_code}', exit_code, game_output)
                        else:
                            self.finished.emit('success', None)
        except InterruptedError:
            self.log_message.emit('Launch was successfully cancelled.')
            if self._is_installing:
                self._cleanup_interrupted_install()
            self.finished.emit('cancelled', None)
        except RequestException as e:
            error_msg = resources.LANGUAGES[self.lang].get('error_network_desc', 'Could not connect to Mojang servers.')
            self.log_message.emit(f'ERROR: {error_msg} Details: {e}')
            self.finished.emit('error', {'type': 'network_error', 'message': error_msg})
            return None
        except Exception as e:
            error_details = {'message': str(e), 'version_id': version_id_to_launch}
            if 'Could not find net/minecraft/client/Minecraft.class' in game_output:
                error_details['type'] = 'file_corruption'
            else:
                if isinstance(e, GameProcessError):
                    if is_jni_java_error(e.output or '') or 'UnsupportedClassVersionError' in (e.output or ''):
                        out = e.output or ''
                        needed = parse_required_major_from_class_error(out) or required_java_major(self.mc_version)
                        found = parse_found_major_from_class_error(out)
                        error_details['type'] = 'java_version_mismatch'
                        error_details['mc_version'] = self.mc_version
                        error_details['required'] = needed
                        error_details['found'] = found
                    else:
                        if 'IncompatibleEnvironmentException' in e.output or 'InvalidLauncherSetupException' in e.output:
                            error_details['type'] = 'mod_incompatibility'
                            error_details['message'] = 'A mod is incompatible with this version of Minecraft or Forge.'
                        else:
                            if 'contained no existing paths' in (e.output or ''):
                                error_details['type'] = 'file_corruption'
                            else:
                                if self._looks_like_invalid_jvm_args(e.output):
                                    error_details['type'] = 'invalid_jvm_argument'
                                else:
                                    if '--sun-misc-unsafe-memory-access' in (e.output or '') or 'Unrecognized option' in (e.output or ''):
                                        error_details['type'] = 'java_version_mismatch'
                                        error_details['mc_version'] = self.mc_version
                                        error_details['required'] = 22
                                        error_details['message'] = 'Esta versión requiere Java 22 o superior.'
                                    else:
                                        error_details['type'] = 'generic'
                else:
                    if isinstance(e, FileNotFoundError):
                        error_details['type'] = 'invalid_java_path'
                    else:
                        error_details['type'] = 'generic'
            self.log_message.emit(f'ERROR: An error occurred: {e}')
            self.log_message.emit(traceback.format_exc())
            self.finished.emit('error', error_details)
    def log_and_update_status(self, text):
        self.progress_update.emit(0, 0, text)
        self.log_message.emit(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")