import sys
import os
import json
import subprocess
import re
import traceback
import logging
import shutil
import shlex
import socket
import hashlib
import base64
import secrets
import time
import urllib.parse
import webbrowser
from pathlib import Path
import psutil
from functools import partial
from typing import Optional
import requests
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPropertyAnimation, QEasingCurve, QSize, QPoint, QUrl, QByteArray
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPixmap, QColor, QStandardItemModel, QStandardItem, QDesktopServices
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QProgressBar, QFrame, QCheckBox, QSlider, QTabWidget, QTextEdit, QButtonGroup, QRadioButton, QGraphicsDropShadowEffect, QColorDialog, QListWidget, QListWidgetItem, QMessageBox, QSizeGrip, QFileDialog, QDialog, QStackedWidget, QAbstractItemView, QInputDialog, QScrollArea
import minecraft_launcher_lib
from minecraft_launcher_lib import microsoft_account
from minecraft_launcher_lib.exceptions import InvalidRefreshToken, AzureAppNotPermitted, AccountNotOwnMinecraft
from .widgets import AnimatedButton
from .widgets.mod_list_item import ModListItemWidget
from .widgets.installed_mod_list_item import InstalledModListItemWidget
from .widgets.version_selection_dialog import VersionSelectionDialog
from .widgets.version_list_item import VersionListItemWidget
from .widgets.modpack_list_item import ModpackListItemWidget
from . import themes
from kaz_launcher.core.premium_auth import PremiumTokenWorker, is_minecraft_profile_error, refresh_minecraft_profile, start_oauth_callback_server
from kaz_launcher.ui.premium_login_dialog import PremiumLoginDialog, webengine_available
from kaz_launcher.core.java_ensure_worker import JavaEnsureWorker
from kaz_launcher.core.mc_worker import MinecraftWorker
from kaz_launcher.core import mod_manager
from kaz_launcher.core import remote_modpack
from kaz_launcher.core.remote_news import fetch_remote_news
from kaz_launcher.utils.paths import get_assets_dir
from kaz_launcher.config import settings
from kaz_launcher.config import resources
from kaz_launcher.utils import helpers
from kaz_launcher.utils.java_resolver import resolve_java_for_minecraft
from kaz_launcher.utils.instance_registry import resolve_version_id, save_instance_meta, scan_remote_instances, load_instance_meta
from kaz_launcher.utils.account_store import find_account, remove_account, set_account_mode, upsert_account
from .dialogs import FixErrorDialog, AdvancedSettingsDialog, PasswordDialog, NewInstallationDialog, UpdateDialog
from kaz_launcher.core import updater
APP_VERSION = 'v1.2.5'
MODPACK_MANIFEST_URL = 'https://i0002.clarodrive.com/s/if5ar9aE7QCrWFk'
NEWS_REMOTE_URL = 'https://drive.google.com/file/d/1i7dOiFDCNA58M9t1xNh6bSoCPYS8xFzV/view?usp=sharing'
MODS_PER_PAGE = 20
PREMIUM_CLIENT_ID = '3a34c81c-7834-4c03-90ca-b83810923368'
class NewsWorker(QThread):
    """Noticias remotas (JSON) o feed RSS de Minecraft como respaldo."""
    news_loaded = Signal(list)
    error_occurred = Signal(str)
    def __init__(self, remote_url: str='', parent=None):
        super().__init__(parent)
        self.remote_url = (remote_url or '').strip()
    def _load_minecraft_rss(self) -> list:
        import xml.etree.ElementTree as ET
        response = requests.get('https://www.minecraft.net/en-us/updates/feed', timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        news_items = []
        for item in root.findall('.//item')[:10]:
            title = item.find('title')
            link = item.find('link')
            description = item.find('description')
            pub_date = item.find('pubDate')
            if title is None:
                continue
            else:
                news_items.append({'title': title.text if title.text else '', 'link': link.text if link is not None and link.text else '', 'description': description.text if description is not None and description.text else '', 'date': pub_date.text if pub_date is not None and pub_date.text else ''})
        return news_items
    def run(self):
        try:
            if self.remote_url:
                try:
                    items = fetch_remote_news(self.remote_url)
                    if items:
                        self.news_loaded.emit(items)
                        return
                except Exception:
                    pass
            self.news_loaded.emit(self._load_minecraft_rss())
        except requests.exceptions.RequestException:
            self.news_loaded.emit([{'title': 'Bienvenido a KazLauncher', 'description': 'Recuerda seguir a Kaz en sus redes, haciendo clic aqui', 'date': '', 'link': 'https://linktr.ee/kazeschido'}])
        except Exception as e:
            self.error_occurred.emit(f'Error al cargar noticias: {e}')
class ModSearchWorker(QThread):
    finished = Signal(list, int)
    def __init__(self, query, game_version, loader, sort_option, lang_dict, offset, parent=None):
        super().__init__(parent)
        self.query = query
        self.game_version = game_version
        self.loader = loader
        self.sort_option = sort_option
        self.lang_dict = lang_dict
        self.offset = offset
    def run(self):
        logging.info(f'Starting mod search: query=\'{self.query}\', game_version=\'{self.game_version}\', loader=\'{self.loader}\', sort=\'{self.sort_option}\', offset=\'{self.offset}\'')
        hits, total_hits = mod_manager.search_mods(self.query, self.game_version, self.loader, self.lang_dict, self.sort_option, self.offset)
        logging.info(f'Mod search finished, found {len(hits)} results out of {total_hits}.')
        self.finished.emit(hits, total_hits)
class ModDownloadWorker(QThread):
    finished = Signal(str, bool, str)
    mod_info_signal = Signal(str, dict)
    progress = Signal(str, int)
    def __init__(self, project_id, game_version, loader, minecraft_dir, lang_dict, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.game_version = game_version
        self.loader = loader
        self.minecraft_dir = minecraft_dir
        self.is_running = True
        self.lang_dict = lang_dict
    def run(self):
        try:
            self.progress.emit(self.project_id, 0)
            version_info = mod_manager.get_latest_mod_version(self.project_id, self.game_version, self.loader, self.lang_dict)
            if not version_info or (not version_info.get('files')):
                self.finished.emit(self.project_id, False, f'Error for {self.project_id}: could not find a compatible file.')
                return
            files = version_info.get('files', [])
            primary_file = next((f for f in files if f.get('primary')), files[0] if files else None)
            if not primary_file:
                self.finished.emit(self.project_id, False, f'Error for {self.project_id}: no files found for download.')
                return
            file_url = primary_file['url']
            file_name = primary_file['filename']
            mods_folder = os.path.join(self.minecraft_dir, 'mods')
            def progress_handler(p):
                if self.is_running:
                    self.progress.emit(self.project_id, p)
            success = mod_manager.download_file(file_url, mods_folder, file_name, progress_handler, self.lang_dict)
            if success and self.is_running:
                file_info = {'filename': file_name, 'url': file_url, 'project_id': self.project_id, 'game_version': self.game_version}
                self.mod_info_signal.emit(self.project_id, file_info)
                self.finished.emit(self.project_id, True, f'Successfully downloaded {file_name}')
            elif not self.is_running:
                self.finished.emit(self.project_id, False, f'Download of {file_name} was cancelled.')
            else:
                self.finished.emit(self.project_id, False, f'Failed to download {file_name}.')
        except Exception as e:
            self.finished.emit(self.project_id, False, f'Critical error in thread: {e}')
        finally:
            if self.is_running:
                self.progress.emit(self.project_id, 101)
    def stop(self):
        self.is_running = False
class LocalModsScannerWorker(QThread):
    finished = Signal(list)
    def __init__(self, mods_folder, lang_dict, installed_mods_data, parent=None):
        super().__init__(parent)
        self.mods_folder = mods_folder
        self.lang_dict = lang_dict
        self.installed_mods_data = installed_mods_data
    def run(self):
        mods = mod_manager.scan_local_mods(self.mods_folder, self.lang_dict, self.installed_mods_data)
        self.finished.emit(mods)
class ModpackInstallWorker(QThread):
    finished = Signal(bool, str)
    progress_status = Signal(str)
    def __init__(self, manifest, minecraft_dir, lang_dict, java_path, target_instance_dir=None, mode='full', parent=None):
        super().__init__(parent)
        self.manifest = manifest
        self.minecraft_dir = minecraft_dir
        self.lang_dict = lang_dict
        self.java_path = java_path
        self.target_instance_dir = target_instance_dir
        self.mode = mode
    def run(self):
        def set_status(text):
            self.progress_status.emit(text)
        callback = {'setStatus': set_status}
        success, msg = remote_modpack.install_modpack(self.manifest, self.minecraft_dir, self.lang_dict, java_path=self.java_path, callback=callback, target_instance_dir=self.target_instance_dir, mode=self.mode)
        self.finished.emit(success, msg)
class MrpackInstallWorker(QThread):
    finished = Signal(bool, str, object)
    progress_status = Signal(str)
    def __init__(self, mrpack_path, minecraft_dir, lang_dict, parent=None):
        super().__init__(parent)
        self.mrpack_path = mrpack_path
        self.minecraft_dir = minecraft_dir
        self.lang_dict = lang_dict
        self._stop = False
    def run(self):
        from kaz_launcher.core.remote_modpack import install_mrpack
        success, msg, result = install_mrpack(self.mrpack_path, self.minecraft_dir, self.lang_dict, progress_callback=self.progress_status.emit, stop_flag=lambda: self._stop)
        self.finished.emit(success, msg, result)
    def stop(self):
        self._stop = True
class ModpackVerifyWorker(QThread):
    finished = Signal(bool, str)
    progress_status = Signal(str)
    def __init__(self, manifest, instance_dir, lang_dict, apply_updates=True, parent=None):
        super().__init__(parent)
        self.manifest = manifest
        self.instance_dir = instance_dir
        self.lang_dict = lang_dict
        self.apply_updates = apply_updates
    def run(self):
        def set_status(text):
            self.progress_status.emit(text)
        callback = {'setStatus': set_status}
        if self.apply_updates:
            success, msg = remote_modpack.update_remote_instance_mods(self.manifest, self.instance_dir, self.lang_dict, callback=callback)
        else:
            success, msg = remote_modpack.verify_remote_instance(self.manifest, self.instance_dir, self.lang_dict)
        self.finished.emit(success, msg)
class PreLaunchModsCheckWorker(QThread):
    """Verifica mods de una instancia remota contra su manifest antes de jugar."""
    finished = Signal(object, object, str)
    def __init__(self, minecraft_dir, instance_dir, manifest_url, cached_manifests, lang_dict, parent=None):
        super().__init__(parent)
        self.minecraft_dir = minecraft_dir
        self.instance_dir = instance_dir
        self.manifest_url = manifest_url
        self.cached_manifests = list(cached_manifests or [])
        self.lang_dict = lang_dict
    @staticmethod
    def find_manifest(minecraft_dir, instance_dir, manifest_url, cached_manifests):
        target = os.path.normcase(os.path.abspath(instance_dir))
        folder_name = os.path.basename(instance_dir.rstrip('\\/'))
        meta = load_instance_meta(instance_dir)
        def matches(manifest):
            try:
                resolved = remote_modpack.resolve_instance_dir(minecraft_dir, manifest)
            except Exception:
                resolved = ''
            if resolved and os.path.normcase(os.path.abspath(resolved)) == target:
                return True
            manifest_name = remote_modpack.sanitize_instance_name(manifest.get('name', ''))
            meta_name = remote_modpack.sanitize_instance_name(meta.get('name', ''))
            return manifest_name == folder_name or manifest_name == meta_name
        for entry in cached_manifests:
            manifest = entry.get('manifest') or {}
            if manifest and matches(manifest):
                return manifest
        for manifest in remote_modpack.fetch_remote_manifests(manifest_url):
            if matches(manifest):
                return manifest
        return None
    def run(self):
        from kaz_launcher.core.instance_sync import verify_remote_mods
        try:
            manifest = self.find_manifest(self.minecraft_dir, self.instance_dir, self.manifest_url, self.cached_manifests)
            if not manifest:
                self.finished.emit(None, None, '')
                return
            report = verify_remote_mods(manifest, self.instance_dir, self.lang_dict)
            self.finished.emit(manifest, report, '')
        except Exception as exc:
            self.finished.emit(None, None, str(exc))
class ManualInstallWorker(QThread):
    finished = Signal(bool, str, object)
    progress_status = Signal(str)
    def __init__(self, loader, minecraft_version, loader_version, minecraft_dir, java_path, parent=None):
        super().__init__(parent)
        self.loader = loader
        self.minecraft_version = minecraft_version
        self.loader_version = loader_version
        self.minecraft_dir = minecraft_dir
        self.java_path = java_path
    def run(self):
        from kaz_launcher.core.manual_install import install_manual_instance
        ok, msg, version_id, instance_dir = install_manual_instance(loader=self.loader, minecraft_version=self.minecraft_version, loader_version=self.loader_version, minecraft_directory=self.minecraft_dir, java_path=self.java_path, on_status=self.progress_status.emit)
        self.finished.emit(ok, msg, {'version_id': version_id, 'instance_dir': instance_dir, 'loader': self.loader})
class VersionSizeScannerWorker(QThread):
    finished = Signal(dict, int)
    def __init__(self, instance_dirs, parent=None):
        super().__init__(parent)
        self.instance_dirs = list(instance_dirs or [])
    @staticmethod
    def get_dir_size(path):
        total = 0
        try:
            for root, dirs, files in os.walk(path, followlinks=False):
                for name in files:
                    try:
                        total += os.path.getsize(os.path.join(root, name))
                    except OSError:
                        pass
        except OSError:
            return 0
        return total
    def run(self):
        sizes = {}
        total_size = 0
        for instance_dir in self.instance_dirs:
            if self.isInterruptionRequested():
                return
            if os.path.isdir(instance_dir):
                size = self.get_dir_size(instance_dir)
                sizes[instance_dir] = size
                total_size += size
        if not self.isInterruptionRequested():
            self.finished.emit(sizes, total_size)
class MinecraftLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.total_system_memory = 16
        self.worker = None
        self.version_loader = None
        self.mod_search_worker = None
        self.local_mods_scanner = None
        self.version_size_scanner = None
        self.news_worker = None
        self.modpack_install_worker = None
        self.detected_remote_modpacks = []
        self._installing = False
        self._install_anim_frame = 0
        self._install_anim_timer = QTimer(self)
        self._install_anim_timer.setInterval(400)
        self._install_anim_timer.timeout.connect(self._tick_install_anim)
        self.mod_download_workers = {}
        self.mod_list_item_map = {}
        self._installed_mods_cache = []
        self.version_widget_map = {}
        self.mod_current_page = 1
        self.mod_total_hits = 0
        self.grouped_versions = {}
        self.selected_versions_for_deletion = set()
        self.settings = settings.load_settings()
        self.premium_accounts = list(self.settings.get('premium_accounts') or [])
        self.selected_account_id = self.settings.get('selected_account_id', '')
        self.account_mode = self.settings.get('account_mode', 'offline')
        self.premium_session = self.settings.get('premium_session') or {}
        self.offline_mode = self.account_mode == 'offline'
        self._refreshing_account_combo = False
        self._refreshing_version_combo = False
        self._select_instance_on_refresh = None
        self._versions_selected_instance_dir = ''
        self._versions_selected_source = ''
        self._prelaunch_update_pending = None
        self.current_language = 'es'
        self.lang_dict = resources.LANGUAGES[self.current_language]
        self.current_accent_color = self.settings.get('accent_color', '#1DB954')
        self.current_accent_color_secondary = self.settings.get('accent_color_secondary', '#8B5CF6')
        self.current_theme = self.settings.get('theme', 'default')
        self.current_version_type = self.settings.get('version_type', 'vanilla')
        default_mc_dir = minecraft_launcher_lib.utils.get_minecraft_directory()
        base_dir = os.path.dirname(default_mc_dir) if default_mc_dir else os.path.expanduser('~')
        self.minecraft_directory = os.path.join(base_dir, '.kazlauncher')
        os.makedirs(self.minecraft_directory, exist_ok=True)
        self.selected_instance_dir = self.settings.get('selected_instance_dir', '')
        base_installed_path = os.path.join(self.minecraft_directory, 'installed_mods.json')
        self.installed_mods_path = os.path.join(self.selected_instance_dir, 'installed_mods.json') if self.selected_instance_dir else base_installed_path
        self.init_fonts()
        self.init_icons()
        self.init_ui()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.update_version_display()
        self.old_pos = None
        self.setWindowOpacity(0)
        self.setAcceptDrops(True)
        self.fade_in_animation = QPropertyAnimation(self, b'windowOpacity')
        self.fade_in_animation.setDuration(500)
        self.fade_in_animation.setStartValue(0)
        self.fade_in_animation.setEndValue(1)
        self.fade_in_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.update_pagination_controls()
        self.update_mod_list()
        self.refresh_installed_mods()
        self._refresh_account_selector()
        if self.account_mode == 'online' and self.selected_account_id:
                active = self._find_premium_account(self.selected_account_id)
                if active:
                    self._apply_premium_session(active)
        self._update_login_status_label()
        # Comprobación silenciosa de actualizaciones al arrancar (solo exe compilado).
        if updater.get_launcher_exe_path():
            QTimer.singleShot(6000, lambda: self.check_for_updates(silent=True))
    def init_fonts(self):
        assets_dir = get_assets_dir()
        font_path = os.path.join(assets_dir, 'Minecraftia.ttf')
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != (-1):
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            self.minecraft_font = QFont(font_families[0], 9)
            self.title_font = QFont(font_families[0], 22, QFont.Bold)
            self.subtitle_font = QFont(font_families[0], 14)
        else:
            logging.warning('Font not found. Using default font.')
            self.minecraft_font = QFont('Arial', 10)
            self.title_font = QFont('Arial', 24, QFont.Bold)
            self.subtitle_font = QFont('Arial', 12)
    def init_icons(self):
        def create_icon(svg_data):
            pixmap = QPixmap()
            pixmap.loadFromData(svg_data)
            return QIcon(pixmap)
        self.play_icon = create_icon(resources.PLAY_ICON_SVG)
        self.cancel_icon = create_icon(resources.CANCEL_ICON_SVG)
        self.settings_icon = create_icon(resources.SETTINGS_ICON_SVG)
        self.news_icon = create_icon(resources.NEWS_ICON_SVG)
        self.console_icon = create_icon(resources.CONSOLE_ICON_SVG)
        self.version_icon = create_icon(resources.VERSION_ICON_SVG)
        self.username_icon = create_icon(resources.USERNAME_ICON_SVG)
        self.mods_icon = create_icon(resources.MODS_ICON_SVG)
        self.modpacks_icon = create_icon(resources.MODPACKS_ICON_SVG)
        self.installed_icon = create_icon(resources.INSTALLED_ICON_SVG)
        self.folder_icon = create_icon(resources.FOLDER_ICON_SVG)
        self.manage_versions_icon = create_icon(resources.MANAGE_ICON_SVG)
        self.version_management_icons = {'vanilla': self.version_icon, 'forge': create_icon(resources.FORGE_ICON_SVG), 'fabric': create_icon(resources.FABRIC_ICON_SVG), 'folder': self.folder_icon, 'repair': create_icon(resources.REPAIR_ICON_SVG), 'delete': create_icon(resources.DELETE_ICON_SVG), 'edit': create_icon(resources.EDIT_ICON_SVG)}
        assets_dir = get_assets_dir()
        icon_path = os.path.join(assets_dir, 'launcher-icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
    def init_ui(self):
        self.setWindowTitle('KazLauncher')
        self.resize(1280, 800)
        self.setMinimumSize(1080, 700)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        if 'window_geometry' in self.settings:
            try:
                geom_data = self.settings['window_geometry'].encode('utf-8')
                self.restoreGeometry(QByteArray.fromBase64(QByteArray(geom_data)))
            except Exception as e:
                logging.error(f'Failed to restore window geometry: {e}')
        self.container = QWidget(self)
        self.container.setObjectName('container')
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.create_title_bar(main_layout)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(20, 10, 20, 10)
        self.create_main_panel(content_layout)
        self.create_tabs_panel(content_layout)
        main_layout.addLayout(content_layout)
        bottom_bar_layout = QHBoxLayout()
        bottom_bar_layout.setContentsMargins(0, 0, 5, 5)
        bottom_bar_layout.addStretch()
        self.version_status_label = QLabel(f'{APP_VERSION}')
        self.version_status_label.setObjectName('versionStatusLabel')
        self.version_status_label.setFont(self.minecraft_font)
        self.update_version_display()
        bottom_bar_layout.addWidget(self.version_status_label)
        self.check_updates_button = QPushButton()
        self.check_updates_button.setObjectName('updateLinkButton')
        self.check_updates_button.setFont(self.minecraft_font)
        self.check_updates_button.setCursor(Qt.PointingHandCursor)
        self.check_updates_button.setFocusPolicy(Qt.NoFocus)
        self.check_updates_button.clicked.connect(self.check_for_updates)
        bottom_bar_layout.addWidget(self.check_updates_button)
        size_grip = QSizeGrip(self)
        bottom_bar_layout.addWidget(size_grip, 0, Qt.AlignBottom | Qt.AlignRight)
        main_layout.addLayout(bottom_bar_layout)
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(self.container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_theme()
        self.update_ui_text()
        self.populate_versions(self.current_version_type)
        self.tab_widget.setCurrentIndex(self.settings.get('last_tab', 0))
    def start_minecraft(self):
        if self.worker and self.worker.isRunning():
            return
        if getattr(self, '_installing', False) or (self.modpack_install_worker and self.modpack_install_worker.isRunning()) or (hasattr(self, 'manual_install_worker') and self.manual_install_worker and self.manual_install_worker.isRunning()) or (hasattr(self, '_mrpack_worker') and self._mrpack_worker and self._mrpack_worker.isRunning()) or (getattr(self, '_prelaunch_mods_worker', None) and self._prelaunch_mods_worker.isRunning()) or (getattr(self, 'modpack_verify_worker', None) and self.modpack_verify_worker.isRunning()):
            return
        else:
            auth = None
            if not getattr(self, 'offline_mode', False):
                auth = self._get_premium_auth()
            if auth:
                username = auth.get('name', '')
            else:
                username = self.user_input.text()
                if not username:
                    self.error_label.setText(self.lang_dict['enter_username_error'])
                    self.error_label.setVisible(True)
                    return
            self.launch_control_stack.setCurrentIndex(1)
            self.error_label.setVisible(False)
            self.progress_bar.setValue(0)
            console_widget = self.console_output.parentWidget()
            console_index = self.tab_widget.indexOf(console_widget)
            if console_index != (-1):
                self.tab_widget.setCurrentIndex(console_index)
            raw_jvm_args = (self.settings.get('jvm_args', '') or '').strip()
            try:
                jvm_args_list = shlex.split(raw_jvm_args, posix=False) if raw_jvm_args else []
            except ValueError as e:
                self.on_launch_finished('error', {'type': 'invalid_jvm_argument', 'message': f'Argumentos JVM inválidos: {e}'})
                return
            selected_version, launch_instance_dir = self._get_version_combo_selection()
            if not selected_version:
                self.on_launch_finished('error', {'type': 'generic', 'message': 'Game version not selected.'})
                return
            else:
                self.selected_instance_dir = launch_instance_dir
                self.settings['selected_instance_dir'] = launch_instance_dir
                effective_dir = launch_instance_dir if launch_instance_dir and os.path.isdir(launch_instance_dir) else self.minecraft_directory
                needs_22 = self._detect_version_needs_java22(selected_version, effective_dir)
                min_java = 22 if needs_22 else None
                self._pending_launch = {'username': username, 'auth': auth, 'selected_version': selected_version, 'jvm_args_list': jvm_args_list, 'required_java': min_java}
                self._maybe_verify_mods_before_launch(launch_instance_dir)
    def _maybe_verify_mods_before_launch(self, instance_dir):
        if not instance_dir or not self._is_remote_instance_dir(instance_dir):
            self._start_java_ensure()
            return
        cached = list(getattr(self, 'detected_remote_modpacks', []) or [])
        self._prelaunch_instance_dir = instance_dir
        self._prelaunch_mods_worker = PreLaunchModsCheckWorker(self.minecraft_directory, instance_dir, MODPACK_MANIFEST_URL, cached, self.lang_dict, self)
        self._prelaunch_mods_worker.finished.connect(self._on_prelaunch_mods_check_finished)
        self._prelaunch_mods_worker.start()
        msg = self.lang_dict.get('verifying_mods_before_launch', 'Verificando mods...')
        self.progress_bar.setFormat(msg)
        self.log_to_console(msg)
    def _on_prelaunch_mods_check_finished(self, manifest, report, error):
        pending = getattr(self, '_pending_launch', None)
        if not pending:
            return
        if error or not manifest:
            if error:
                self.log_to_console(self.lang_dict.get('prelaunch_mods_check_failed', 'No se pudo verificar los mods remotos: {msg}').format(msg=error))
            self._start_java_ensure()
            return
        if report and report.errors:
            self.log_to_console(self.lang_dict.get('prelaunch_mods_check_failed', 'No se pudo verificar los mods remotos: {msg}').format(msg=report.errors[0]))
            self._start_java_ensure()
            return
        if report and report.up_to_date:
            self.log_to_console(self.lang_dict.get('mods_up_to_date_launch', 'Los mods de esta instancia están actualizados.'))
            self._start_java_ensure()
            return
        lang = self.lang_dict
        details = report.format_diff_details(lang) if report else ''
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle('Modpack')
        box.setText(lang.get('mods_update_before_launch', 'Hay actualizaciones de mods para esta instancia:\n\n{details}\n\n¿Actualizarlas antes de jugar?').format(details=details))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        box.button(QMessageBox.Yes).setText(lang.get('modpack_update_mods_btn', 'Actualizar mods'))
        box.button(QMessageBox.No).setText(lang.get('mods_update_skip_btn', 'Jugar sin actualizar'))
        box.button(QMessageBox.Cancel).setText(lang.get('cancel_button', 'Cancelar'))
        reply = box.exec()
        if reply == QMessageBox.Cancel:
            self._pending_launch = None
            self.launch_control_stack.setCurrentIndex(0)
            return
        if reply == QMessageBox.No:
            self._start_java_ensure()
            return
        self._prelaunch_update_pending = pending['selected_version']
        self._start_modpack_mods_update(manifest, getattr(self, '_prelaunch_instance_dir', '') or self.selected_instance_dir or '')
    def _start_java_ensure(self):
        pending = getattr(self, '_pending_launch', None)
        if not pending:
            return
        self.progress_bar.setFormat(self.lang_dict.get('java_installing', 'Preparando Java...'))
        self.log_to_console(self.lang_dict.get('java_installing', 'Preparando Java...'))
        preferred_java = (self.settings.get('java_path') or '').strip() or None
        effective_dir = self.selected_instance_dir if self.selected_instance_dir and os.path.isdir(self.selected_instance_dir) else self.minecraft_directory
        versions_dir = os.path.join(effective_dir, 'versions') if effective_dir else None
        self.java_ensure_worker = JavaEnsureWorker(pending['selected_version'], preferred_java, self, min_major=pending.get('required_java'), versions_dir=versions_dir)
        self.java_ensure_worker.status.connect(self._on_java_ensure_status)
        self.java_ensure_worker.finished.connect(self._on_java_ensure_finished)
        self.java_ensure_worker.start()
    def _on_java_ensure_status(self, message: str):
        self.progress_bar.setFormat(message)
        self.log_to_console(message)
    def _on_java_ensure_finished(self, java_path, error):
        pending = getattr(self, '_pending_launch', None)
        if not pending:
            return
        else:
            if not java_path:
                from kaz_launcher.utils.java_resolver import required_java_major
                lang = self.lang_dict
                msg = error or 'Java no disponible'
                mc_ver = pending['selected_version']
                required = pending.get('required_java') or required_java_major(mc_ver)
                self.on_launch_finished('error', {'type': 'java_not_found', 'mc_version': mc_ver, 'required': required, 'message': lang.get('java_install_failed', 'No se pudo instalar Java: {msg}').format(msg=msg)})
                return
            else:
                self.log_to_console(self.lang_dict.get('java_install_ok', f'Usando Java: {java_path}'))
                self._continue_minecraft_launch(java_path, pending)
    def _get_java_major_version(self, java_path: str) -> Optional[int]:
        if not java_path or not os.path.isfile(java_path):
            return None
        try:
            out = subprocess.run([java_path, '-version'], capture_output=True, text=True, timeout=5)
            text = (out.stderr or out.stdout or '').lower()
            m = re.search('version "(\\d+)', text)
            if m:
                return int(m.group(1))
            m = re.search('version "1\\.(\\d+)', text)
            if m:
                return int(m.group(1))
        except Exception:
            return None
        return None
    def _detect_version_needs_java22(self, selected_version: str, instance_dir: str) -> bool:
        version_json = os.path.join(instance_dir, 'versions', selected_version, f'{selected_version}.json')
        try:
            if os.path.isfile(version_json):
                with open(version_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for arg in data.get('arguments', {}).get('jvm', []):
                    if isinstance(arg, str) and 'sun-misc-unsafe-memory-access' in arg:
                        return True
        except Exception:
            return False
        return False
    def _continue_minecraft_launch(self, java_path, pending):
        username = pending['username']
        auth = pending['auth']
        selected_version = pending['selected_version']
        jvm_args_list = pending['jvm_args_list']
        def default_aikar_flags():
            return ['-XX:+UseG1GC', '-XX:+ParallelRefProcEnabled', '-XX:MaxGCPauseMillis=200', '-XX:+UnlockExperimentalVMOptions', '-XX:+DisableExplicitGC', '-XX:+AlwaysPreTouch', '-XX:G1NewSizePercent=30', '-XX:G1MaxNewSizePercent=40', '-XX:G1HeapRegionSize=8M', '-XX:G1ReservePercent=20', '-XX:G1HeapWastePercent=5', '-XX:G1MixedGCCountTarget=4', '-XX:InitiatingHeapOccupancyPercent=15', '-XX:G1MixedGCLiveThresholdPercent=90', '-XX:G1RSetUpdatingPauseTimePercent=5', '-XX:SurvivorRatio=32', '-XX:+PerfDisableSharedMem', '-XX:MaxTenuringThreshold=1', '-XX:+UseStringDeduplication', '-XX:+OptimizeStringConcat', '-XX:+UseFastUnorderedTimeStamps', '-XX:+UseCompressedOops', '-XX:+UseCompressedClassPointers', '-Djava.net.preferIPv4Stack=true', '-Dfile.encoding=UTF-8', '-Djava.net.useSystemProxies=true', '-Djava.awt.headless=false', '-Dfml.ignoreInvalidMinecraftCertificates=true', '-Dfml.ignorePatchDiscrepancies=true']
        merged_jvm = []
        java_opt_enabled = bool(self.settings.get('java_opt_enabled', True))
        if java_opt_enabled:
            seen = set()
            for arg in jvm_args_list + default_aikar_flags():
                key = arg.split('=')[0]
                if key not in seen:
                    merged_jvm.append(arg)
                    seen.add(key)
            unlock = '-XX:+UnlockExperimentalVMOptions'
            if any((a.startswith(unlock) for a in merged_jvm)):
                merged_jvm = [a for a in merged_jvm if not a.startswith(unlock)]
                merged_jvm.insert(0, unlock)
        else:
            merged_jvm = jvm_args_list
        options = {'executablePath': java_path, 'jvmArguments': merged_jvm, 'resolutionWidth': self.resolution_width_input.text(), 'resolutionHeight': self.resolution_height_input.text(), 'gameDirectory': self.selected_instance_dir if self.selected_instance_dir and os.path.isdir(self.selected_instance_dir) else self.minecraft_directory}
        mod_loader = self.current_version_type if self.current_version_type != 'vanilla' else None
        effective_dir = self.selected_instance_dir if self.selected_instance_dir and os.path.isdir(self.selected_instance_dir) else self.minecraft_directory
        self.worker = MinecraftWorker(mc_version=selected_version, username=username, minecraft_dir=effective_dir, client_token=self.settings.get('clientToken'), memory_gb=self.memory_slider.value(), fullscreen=self.fullscreen_checkbox.isChecked(), options=options, lang=self.current_language, mod_loader=mod_loader, auth_uuid=auth.get('id') if auth else None, auth_token=auth.get('access_token') if auth else None)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.log_message.connect(self.log_to_console)
        self.worker.finished.connect(self.on_launch_finished)
        self.worker.start()
        meta = load_instance_meta(self.selected_instance_dir) if self.selected_instance_dir else {}
        display_name = meta.get('name') or os.path.basename(self.selected_instance_dir or '') or 'Minecraft'
        from kaz_launcher.discord_presence import update_discord_playing
        update_discord_playing(display_name, mc_version=selected_version, loader=self.current_version_type or '')
    def cancel_launch(self):
        prelaunch = getattr(self, '_prelaunch_mods_worker', None)
        if prelaunch and prelaunch.isRunning():
            prelaunch.terminate()
            prelaunch.wait(500)
            self._pending_launch = None
            self.launch_control_stack.setCurrentIndex(0)
            self.log_to_console('Launch cancelled.')
        else:
            if getattr(self, 'java_ensure_worker', None) and self.java_ensure_worker.isRunning():
                self.java_ensure_worker.terminate()
                self.java_ensure_worker.wait(500)
                self.launch_control_stack.setCurrentIndex(0)
                self.log_to_console('Java setup cancelled.')
            else:
                if self.worker and self.worker.isRunning():
                    self.worker.stop()
                    self.cancel_button.setEnabled(False)
                    self.cancel_button.setText(self.lang_dict.get('cancelling', 'Cancelling...'))
    def create_title_bar(self, main_layout):
        self.title_bar = QWidget()
        self.title_bar.setObjectName('titleBar')
        self.title_bar.setFixedHeight(60)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(20, 10, 20, 10)
        self.title_label = QLabel()
        self.title_label.setFont(self.title_font)
        self.title_label.setObjectName('titleLabel')
        self.glow_effect = QGraphicsDropShadowEffect(self)
        self.glow_effect.setBlurRadius(25)
        self.glow_effect.setOffset(0, 0)
        self.title_label.setGraphicsEffect(self.glow_effect)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        self.minimize_button = QPushButton('—')
        self.minimize_button.setObjectName('minimizeButton')
        self.minimize_button.setFixedSize(30, 30)
        self.minimize_button.clicked.connect(self.showMinimized)
        self.close_button = QPushButton('✕')
        self.close_button.setObjectName('closeButton')
        self.close_button.setFixedSize(30, 30)
        self.close_button.clicked.connect(self.close)
        title_layout.addWidget(self.minimize_button)
        title_layout.addWidget(self.close_button)
        main_layout.addWidget(self.title_bar)
    def create_main_panel(self, content_layout):
        main_panel = QWidget()
        main_panel.setObjectName('mainPanel')
        self.main_panel = main_panel
        main_panel.setFixedWidth(400)
        panel_layout = QVBoxLayout(main_panel)
        panel_layout.setContentsMargins(20, 20, 20, 24)
        panel_layout.setSpacing(15)
        self.version_type_label = QLabel()
        self.version_type_label.setFont(self.subtitle_font)
        self.version_type_label.setObjectName('sectionLabel')
        self.version_type_group = QButtonGroup(self)
        self.vanilla_radio = QRadioButton()
        self.forge_radio = QRadioButton()
        self.fabric_radio = QRadioButton()
        version_type_map = {'vanilla': 0, 'forge': 1, 'fabric': 2}
        self.version_type_group.addButton(self.vanilla_radio, version_type_map['vanilla'])
        self.version_type_group.addButton(self.forge_radio, version_type_map['forge'])
        self.version_type_group.addButton(self.fabric_radio, version_type_map['fabric'])
        self.version_type_group.button(version_type_map.get(self.current_version_type, 0)).setChecked(True)
        self.version_type_group.idClicked.connect(self.change_version_type)
        self.install_status_label = QLabel('')
        self.install_status_label.setFont(self.minecraft_font)
        self.install_status_label.setObjectName('installStatusLabel')
        self.install_status_label.setWordWrap(True)
        self.install_status_label.setVisible(False)
        self.version_label = QLabel()
        self.version_label.setFont(self.subtitle_font)
        self.version_label.setObjectName('sectionLabel')
        version_layout = QHBoxLayout()
        version_icon_label = QLabel()
        version_icon_label.setPixmap(self.version_icon.pixmap(QSize(24, 24)))
        version_layout.addWidget(version_icon_label)
        version_layout.addWidget(self.version_label)
        version_layout.addStretch()
        self.version_combo = QComboBox()
        self.version_combo.setFont(self.minecraft_font)
        self.version_combo.setFixedHeight(40)
        self.version_combo.setIconSize(QSize(16, 16))
        self.version_combo.currentIndexChanged.connect(self.on_launch_version_combo_changed)
        self.username_label = QLabel()
        self.username_label.setFont(self.subtitle_font)
        self.username_label.setObjectName('sectionLabel')
        username_layout = QHBoxLayout()
        username_icon_label = QLabel()
        username_icon_label.setPixmap(self.username_icon.pixmap(QSize(24, 24)))
        username_layout.addWidget(username_icon_label)
        username_layout.addWidget(self.username_label)
        username_layout.addStretch()
        self.user_input = QLineEdit()
        self.user_input.setFont(self.minecraft_font)
        self.user_input.setFixedHeight(40)
        self.user_input.setText(self.settings.get('last_username', ''))
        self.user_input.textChanged.connect(self._on_username_changed)
        self.error_label = QLabel('')
        self.error_label.setFont(self.minecraft_font)
        self.error_label.setObjectName('errorLabel')
        self.error_label.setVisible(False)
        self.error_label.setWordWrap(True)
        self.account_status_row = QWidget()
        account_status_layout = QHBoxLayout(self.account_status_row)
        account_status_layout.setContentsMargins(0, 0, 0, 0)
        account_status_layout.setSpacing(6)
        self.login_status_label = QLabel('')
        self.login_status_label.setFont(self.minecraft_font)
        self.login_status_label.setObjectName('loginStatusLabel')
        self.login_status_label.setWordWrap(True)
        self.logout_account_btn = QPushButton('✕')
        self.logout_account_btn.setObjectName('logoutAccountButton')
        self.logout_account_btn.setFixedSize(26, 26)
        self.logout_account_btn.setToolTip(self.lang_dict.get('logout_account_tooltip', 'Cerrar sesión'))
        self.logout_account_btn.setVisible(False)
        self.logout_account_btn.clicked.connect(self.logout_current_premium_account)
        account_status_layout.addWidget(self.login_status_label, 1)
        account_status_layout.addWidget(self.logout_account_btn, 0, Qt.AlignTop)
        self.account_selector_label = QLabel()
        self.account_selector_label.setFont(self.subtitle_font)
        self.account_selector_label.setObjectName('sectionLabel')
        self.account_combo = QComboBox()
        self.account_combo.setFont(self.minecraft_font)
        self.account_combo.setFixedHeight(36)
        self.account_combo.currentIndexChanged.connect(self.on_account_combo_changed)
        panel_layout.addWidget(self.install_status_label)
        panel_layout.addSpacing(8)
        panel_layout.addLayout(version_layout)
        panel_layout.addWidget(self.version_combo)
        panel_layout.addSpacing(20)
        panel_layout.addLayout(username_layout)
        panel_layout.addWidget(self.user_input)
        panel_layout.addStretch()
        panel_layout.addWidget(self.error_label)
        panel_layout.addWidget(self.account_status_row)
        panel_layout.addWidget(self.account_selector_label)
        panel_layout.addWidget(self.account_combo)
        self.launch_wrap = QWidget()
        self.launch_wrap.setObjectName('launchButtonWrap')
        launch_wrap_layout = QVBoxLayout(self.launch_wrap)
        launch_wrap_layout.setContentsMargins(0, 4, 0, 8)
        launch_wrap_layout.setSpacing(0)
        self.launch_control_stack = QStackedWidget()
        self.launch_control_stack.setFixedHeight(48)
        self.launch_button = AnimatedButton('')
        self.launch_button.setObjectName('launchButton')
        self.launch_button.setFont(self.subtitle_font)
        self.launch_button.setIcon(self.play_icon)
        self.launch_button.setIconSize(QSize(24, 24))
        self.launch_button.setFixedHeight(48)
        self.launch_button.clicked.connect(self.start_minecraft)
        self.launch_control_stack.addWidget(self.launch_button)
        launch_wrap_layout.addWidget(self.launch_control_stack)
        progress_container = QWidget()
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(5)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFont(self.minecraft_font)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setFixedHeight(30)
        self.cancel_button = AnimatedButton('')
        self.cancel_button.setObjectName('cancelButton')
        self.cancel_button.setFont(self.minecraft_font)
        self.cancel_button.setIcon(self.cancel_icon)
        self.cancel_button.setIconSize(QSize(20, 20))
        self.cancel_button.setFixedSize(120, 50)
        self.cancel_button.clicked.connect(self.cancel_launch)
        progress_layout.addWidget(self.progress_bar, 1)
        progress_layout.addWidget(self.cancel_button)
        self.launch_control_stack.addWidget(progress_container)
        panel_layout.addWidget(self.launch_wrap)
        content_layout.addWidget(main_panel)
    def update_progress(self, current, max_val, status):
        if max_val > 0:
            self.progress_bar.setFormat(f'{status} - %p%')
        else:
            self.progress_bar.setFormat(status)
        self.progress_bar.setMaximum(max_val)
        self.progress_bar.setValue(current)
    def on_launch_finished(self, result, details=None):
        lang = self.lang_dict
        self.launch_control_stack.setCurrentIndex(0)
        if result == 'success':
            from kaz_launcher.discord_presence import reset_discord_launcher
            reset_discord_launcher(APP_VERSION)
            if self.close_launcher_checkbox.isChecked():
                self.close()
            return None
        else:
            self.cancel_button.setEnabled(True)
            self.cancel_button.setText(lang.get('cancel', 'Cancel'))
            if result == 'cancelled':
                self.log_to_console('Launch cancelled.')
            else:
                if details:
                    error_type = details.get('type')
                    self.log_to_console(f'Launch failed. Error type: {error_type}')
                    if error_type == 'file_lock_error':
                        QMessageBox.warning(self, lang.get('error_file_lock_title', 'File Lock Error'), lang.get('error_file_lock_desc', 'A file needed for installation is locked, possibly by an antivirus or a stuck process. Please try closing any Java processes in Task Manager and launch again.'))
                    else:
                        if error_type == 'network_error':
                            QMessageBox.critical(self, lang.get('error_network_title', 'Network Error'), lang.get('error_network_desc', 'Could not connect. Check your internet.'))
                        else:
                            if error_type == 'fabric_dependency_error':
                                dependency = details.get('dependency', 'required mods')
                                dialog = FixErrorDialog(lang['error_fabric_dependency_title'], lang['error_fabric_dependency_desc'].format(dependency=dependency), lang['error_fabric_dependency_fix'], lang, self, icon_svg=resources.DOWNLOAD_MOD_ICON_SVG)
                                if dialog.exec() == QDialog.Accepted:
                                    self.install_mod_dependency(dependency)
                            else:
                                if error_type == 'file_corruption':
                                    version_id = details.get('version_id', 'selected')
                                    dialog = FixErrorDialog(lang['error_file_corruption_title'], lang['error_file_corruption_desc'].format(version_id=version_id), lang['error_file_corruption_fix'], lang, self)
                                    if dialog.exec() == QDialog.Accepted:
                                        self.reinstall_version(version_id)
                                else:
                                    if error_type in ['java_version_mismatch', 'java_not_found']:
                                        self.settings['java_path'] = ''
                                        settings.save_settings(self.settings)
                                        required = details.get('required', 21)
                                        mc_version = details.get('mc_version', '')
                                        found = details.get('found')
                                        if error_type == 'java_not_found':
                                            dialog = FixErrorDialog(lang['error_java_not_found_title'], lang['error_java_not_found_desc'].format(mc_version=mc_version, required=required), lang['error_java_not_found_fix'].format(required=required), lang, self)
                                        else:
                                            if details.get('message'):
                                                dialog = FixErrorDialog(lang['error_java_version_title'], details['message'], lang['error_java_version_fix'].format(required=required), lang, self)
                                            else:
                                                dialog = FixErrorDialog(lang['error_java_version_title'], lang['error_java_version_desc'].format(mc_version=mc_version, required=required, found=found or '?'), lang['error_java_version_fix'].format(required=required), lang, self)
                                        if dialog.exec() == QDialog.Accepted:
                                            self.open_advanced_settings()
                                    else:
                                        if error_type == 'invalid_java_path':
                                            dialog = FixErrorDialog(lang['error_java_path_title'], lang['error_java_path_desc'], lang['error_java_path_fix'], lang, self)
                                            if dialog.exec() == QDialog.Accepted:
                                                self.settings['java_path'] = ''
                                                settings.save_settings(self.settings)
                                                self.log_to_console(lang.get('error_java_path_reset', 'Ruta de Java restablecida a detección automática.'))
                                                self.open_advanced_settings()
                                        else:
                                            if error_type == 'invalid_jvm_argument':
                                                dialog = FixErrorDialog(lang['error_jvm_args_title'], lang['error_jvm_args_desc'], lang['error_jvm_args_fix'], lang, self)
                                                if dialog.exec() == QDialog.Accepted:
                                                    self.open_advanced_settings()
                                            else:
                                                self.error_label.setText(details.get('message', lang['error_occurred']))
                                                self.error_label.setVisible(True)
                else:
                    self.error_label.setText(lang['error_occurred'])
                    self.error_label.setVisible(True)
    def create_tabs_panel(self, content_layout):
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(self.minecraft_font)
        self.tab_widget.setObjectName('tabWidget')
        self.create_news_tab()
        self.create_mods_tab()
        self.create_versions_tab()
        self.create_modpacks_tab()
        self.create_console_tab()
        self.create_settings_tab()
        content_layout.addWidget(self.tab_widget)
    def create_settings_tab(self):
        self.settings_tab_widget = QWidget()
        settings_layout = QVBoxLayout(self.settings_tab_widget)
        settings_layout.setContentsMargins(20, 20, 20, 20)
        settings_layout.setSpacing(15)
        self.accent_color_label = QLabel()
        self.accent_color_label.setFont(self.subtitle_font)
        self.color_picker_button = QPushButton()
        self.color_picker_button.setFixedHeight(36)
        self.color_picker_button.clicked.connect(self.open_color_picker)
        self.color_preview = QLabel()
        self.color_preview.setObjectName('colorPreview')
        self.color_preview.setFixedSize(33, 33)
        self.color_picker_secondary_button = QPushButton()
        self.color_picker_secondary_button.setFixedHeight(36)
        self.color_picker_secondary_button.clicked.connect(partial(self.open_color_picker, 'secondary'))
        self.color_preview_secondary = QLabel()
        self.color_preview_secondary.setObjectName('colorPreview')
        self.color_preview_secondary.setFixedSize(33, 33)
        self.update_color_preview()
        color_picker_layout = QHBoxLayout()
        color_picker_layout.addWidget(self.color_picker_button)
        color_picker_layout.addWidget(self.color_preview)
        color_picker_layout.addSpacing(10)
        color_picker_layout.addWidget(self.color_picker_secondary_button)
        color_picker_layout.addWidget(self.color_preview_secondary)
        color_picker_layout.addStretch()
        self.theme_style_label = QLabel()
        self.theme_style_label.setFont(self.subtitle_font)
        self.theme_style_combo = QComboBox()
        self.theme_style_combo.setFixedHeight(36)
        self.theme_style_combo.currentIndexChanged.connect(self.on_theme_style_changed)
        self.glass_extras_btn = QPushButton()
        self.glass_extras_btn.setObjectName('glassExtrasButton')
        self.glass_extras_btn.setFixedHeight(36)
        self.glass_extras_btn.clicked.connect(self.open_glass_gradient_editor)
        self.glass_extras_btn.setVisible(False)
        theme_style_row = QHBoxLayout()
        theme_style_row.addWidget(self.theme_style_label)
        theme_style_row.addWidget(self.theme_style_combo)
        theme_style_row.addWidget(self.glass_extras_btn)
        theme_style_row.addStretch()
        self.memory_label = QLabel()
        self.memory_label.setFont(self.subtitle_font)
        self.memory_slider = QSlider(Qt.Horizontal)
        try:
            self.total_system_memory = int(psutil.virtual_memory().total / 1073741824)
            self.memory_slider.setRange(1, self.total_system_memory)
        except Exception as e:
            logging.error(f'Unable to determine RAM capacity: {e}')
            self.total_system_memory = 16
            self.memory_slider.setRange(1, self.total_system_memory)
        current_mem = self.settings.get('memory', 4)
        if current_mem > self.total_system_memory:
            current_mem = self.total_system_memory
        self.memory_slider.setValue(current_mem)
        self.memory_slider.setTickPosition(QSlider.TicksBelow)
        self.memory_slider.setTickInterval(1)
        self.memory_value_label = QLabel(f'{self.memory_slider.value()} GB')
        self.memory_slider.valueChanged.connect(self.update_memory_feedback)
        self.memory_feedback_label = QLabel()
        self.memory_feedback_label.setAlignment(Qt.AlignCenter)
        self.update_memory_feedback(self.memory_slider.value())
        self.resolution_label = QLabel()
        self.resolution_label.setFont(self.subtitle_font)
        resolution_layout = QHBoxLayout()
        self.resolution_width_input = QLineEdit(self.settings.get('resolution_width', '1280'))
        self.resolution_width_input.setPlaceholderText('Width')
        self.resolution_width_input.setFixedHeight(36)
        self.resolution_height_input = QLineEdit(self.settings.get('resolution_height', '720'))
        self.resolution_height_input.setPlaceholderText('Height')
        self.resolution_height_input.setFixedHeight(36)
        resolution_layout.addWidget(self.resolution_width_input)
        resolution_layout.addWidget(QLabel('x'))
        resolution_layout.addWidget(self.resolution_height_input)
        self.fullscreen_checkbox = QCheckBox()
        self.fullscreen_checkbox.setChecked(self.settings.get('fullscreen', False))
        self.close_launcher_checkbox = QCheckBox()
        self.close_launcher_checkbox.setChecked(self.settings.get('close_launcher', True))
        self.ui_opacity_label = QLabel()
        self.ui_opacity_label.setFont(self.subtitle_font)
        self.ui_opacity_slider = QSlider(Qt.Horizontal)
        self.ui_opacity_slider.setRange(50, 100)
        self.ui_opacity_slider.setValue(int(self.settings.get('ui_glass_opacity', 88)))
        self.ui_opacity_slider.setTickPosition(QSlider.TicksBelow)
        self.ui_opacity_slider.setTickInterval(10)
        self.ui_opacity_value_label = QLabel(f'{self.ui_opacity_slider.value()}%')
        self.ui_opacity_slider.valueChanged.connect(self._on_ui_opacity_changed)
        self.ui_opacity_hint = QLabel()
        self.ui_opacity_hint.setObjectName('loginStatusLabel')
        self.ui_opacity_hint.setWordWrap(True)
        self.advanced_settings_button = QPushButton()
        self.advanced_settings_button.setCheckable(False)
        self.advanced_settings_button.clicked.connect(self.open_advanced_settings)
        settings_layout.addWidget(self.accent_color_label)
        settings_layout.addLayout(color_picker_layout)
        settings_layout.addSpacing(6)
        settings_layout.addLayout(theme_style_row)
        settings_layout.addSpacing(10)
        settings_layout.addSpacing(10)
        settings_layout.addWidget(self.memory_label)
        memory_layout = QHBoxLayout()
        memory_layout.addWidget(self.memory_slider)
        memory_layout.addWidget(self.memory_value_label)
        settings_layout.addLayout(memory_layout)
        settings_layout.addWidget(self.memory_feedback_label)
        settings_layout.addSpacing(10)
        settings_layout.addWidget(self.resolution_label)
        settings_layout.addLayout(resolution_layout)
        settings_layout.addSpacing(10)
        settings_layout.addWidget(self.fullscreen_checkbox)
        settings_layout.addWidget(self.close_launcher_checkbox)
        settings_layout.addSpacing(10)
        settings_layout.addWidget(self.ui_opacity_label)
        ui_opacity_layout = QHBoxLayout()
        ui_opacity_layout.addWidget(self.ui_opacity_slider)
        ui_opacity_layout.addWidget(self.ui_opacity_value_label)
        settings_layout.addLayout(ui_opacity_layout)
        settings_layout.addWidget(self.ui_opacity_hint)
        settings_layout.addStretch()
        settings_layout.addWidget(self.advanced_settings_button)
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QFrame.NoFrame)
        self.settings_scroll.viewport().setAutoFillBackground(False)
        self.settings_scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')
        # El viewport del QScrollArea pinta por defecto el fondo de la paleta
        # (gris/negro), ocultando el tema. Forzarlo transparente para que se
        # vea el fondo de la pestaña del tema seleccionado.
        self.settings_scroll.viewport().setStyleSheet('background: transparent;')
        self.settings_scroll.setWidget(self.settings_tab_widget)
        self.tab_widget.addTab(self.settings_scroll, self.settings_icon, '')
    def create_placeholder_tab(self, icon, tab_name):
        widget = QWidget()
        widget.setObjectName(tab_name)
        layout = QVBoxLayout(widget)
        label = QLabel(self.lang_dict['wip_notice'])
        label.setObjectName('wipLabel')
        label.setFont(self.subtitle_font)
        label.setAlignment(Qt.AlignCenter)
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()
        self.tab_widget.addTab(widget, icon, '')
    def create_news_tab(self):
        """Crea la pestaña de noticias con funcionalidad para mostrar noticias de Minecraft"""
        self.news_tab_widget = QWidget()
        self.news_tab_widget.setObjectName('news')
        news_layout = QVBoxLayout(self.news_tab_widget)
        news_layout.setContentsMargins(20, 20, 20, 20)
        news_layout.setSpacing(15)
        top_bar = QHBoxLayout()
        self.news_refresh_button = QPushButton()
        self.news_refresh_button.setIcon(self.news_icon)
        self.news_refresh_button.setIconSize(QSize(24, 24))
        self.news_refresh_button.clicked.connect(self.load_news)
        self.news_refresh_button.setToolTip(self.lang_dict.get('news_refresh', 'Actualizar noticias'))
        top_bar.addStretch()
        top_bar.addWidget(self.news_refresh_button)
        self.news_scroll = QListWidget()
        self.news_scroll.setObjectName('newsList')
        self.news_scroll.setSpacing(10)
        self.news_scroll.setWordWrap(True)
        news_layout.addLayout(top_bar)
        news_layout.addWidget(self.news_scroll, 1)
        self.tab_widget.addTab(self.news_tab_widget, self.news_icon, '')
        self.load_news()
    def load_news(self):
        """Carga las noticias de Minecraft"""
        if self.news_worker and self.news_worker.isRunning():
            return
        else:
            self.news_scroll.clear()
            loading_item = QListWidgetItem(self.lang_dict.get('news_loading', 'Cargando noticias...'))
            loading_item.setTextAlignment(Qt.AlignCenter)
            self.news_scroll.addItem(loading_item)
            self.news_worker = NewsWorker(NEWS_REMOTE_URL, self)
            self.news_worker.news_loaded.connect(self.on_news_loaded)
            self.news_worker.error_occurred.connect(self.on_news_error)
            self.news_worker.start()
    def on_news_loaded(self, news_items):
        """Maneja las noticias cargadas"""
        self.news_scroll.clear()
        if not news_items:
            item = QListWidgetItem(self.lang_dict.get('news_no_items', 'No hay noticias disponibles'))
            item.setTextAlignment(Qt.AlignCenter)
            self.news_scroll.addItem(item)
        else:
            for news in news_items:
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 120))
                news_widget = QWidget()
                news_widget.setObjectName('newsCard')
                news_layout = QVBoxLayout(news_widget)
                news_layout.setContentsMargins(12, 12, 12, 12)
                news_layout.setSpacing(5)
                title_label = QLabel(news.get('title', 'Sin título'))
                title_label.setFont(self.subtitle_font)
                title_label.setWordWrap(True)
                title_label.setObjectName('sectionLabel')
                desc_label = QLabel(news.get('description', '')[:200] + '...' if len(news.get('description', '')) > 200 else news.get('description', ''))
                desc_label.setFont(self.minecraft_font)
                desc_label.setWordWrap(True)
                date_label = QLabel(news.get('date', ''))
                date_label.setFont(self.minecraft_font)
                date_label.setObjectName('loginStatusLabel')
                news_layout.addWidget(title_label)
                news_layout.addWidget(desc_label)
                if news.get('date'):
                    news_layout.addWidget(date_label)
                self.news_scroll.addItem(item)
                self.news_scroll.setItemWidget(item, news_widget)
                if news.get('link'):
                    def open_link(link=news.get('link')):
                        QDesktopServices.openUrl(QUrl(link))
                    news_widget.mousePressEvent = lambda e: open_link() if e.button() == Qt.LeftButton else None
                    news_widget.setCursor(Qt.PointingHandCursor)
    def on_news_error(self, error_msg):
        """Maneja errores al cargar noticias"""
        self.news_scroll.clear()
        item = QListWidgetItem(self.lang_dict.get('news_error', 'Error al cargar noticias'))
        item.setTextAlignment(Qt.AlignCenter)
        self.news_scroll.addItem(item)
        self.log_to_console(f'Error cargando noticias: {error_msg}')
    def create_mods_tab(self):
        self.mods_tab_widget = QWidget()
        main_layout = QVBoxLayout(self.mods_tab_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.mods_sub_tabs = QTabWidget()
        self.mods_sub_tabs.setObjectName('modsSubTabs')
        main_layout.addWidget(self.mods_sub_tabs)
        search_widget = QWidget()
        search_layout = QVBoxLayout(search_widget)
        search_layout.setContentsMargins(10, 10, 10, 10)
        search_layout.setSpacing(10)
        filters_layout = QHBoxLayout()
        self.mod_sort_label = QLabel()
        self.mod_sort_combo = QComboBox()
        self.mod_refresh_button = QPushButton()
        self.mod_refresh_button.clicked.connect(lambda: self.update_mod_list(reset_page=True))
        filters_layout.addWidget(self.mod_sort_label)
        filters_layout.addWidget(self.mod_sort_combo)
        filters_layout.addStretch()
        filters_layout.addWidget(self.mod_refresh_button)
        self.mod_search_input = QLineEdit()
        self.mod_search_input.setObjectName('modSearchInput')
        self.mod_search_input.setFixedHeight(35)
        self.mod_search_input.returnPressed.connect(lambda: self.update_mod_list(reset_page=True))
        self.mod_results_list = QListWidget()
        self.mod_results_list.setObjectName('modList')
        self.mod_results_list.setSpacing(5)
        pagination_layout = QHBoxLayout()
        self.prev_page_button = QPushButton('<')
        self.prev_page_button.setFixedSize(35, 35)
        self.prev_page_button.clicked.connect(self.prev_mod_page)
        self.page_label = QLabel('Page 1')
        self.page_label.setAlignment(Qt.AlignCenter)
        self.next_page_button = QPushButton('>')
        self.next_page_button.setFixedSize(35, 35)
        self.next_page_button.clicked.connect(self.next_mod_page)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.prev_page_button)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_page_button)
        pagination_layout.addStretch()
        installed_widget = QWidget()
        installed_layout = QVBoxLayout(installed_widget)
        installed_layout.setContentsMargins(10, 10, 10, 10)
        installed_layout.setSpacing(10)
        installed_top_bar = QHBoxLayout()
        self.installed_search_input = QLineEdit()
        self.installed_search_input.setObjectName('modSearchInput')
        self.installed_search_input.setFixedHeight(35)
        self.installed_search_input.textChanged.connect(self._apply_installed_filter)
        self.installed_filter_combo = QComboBox()
        self.installed_filter_combo.setFixedHeight(35)
        self.installed_filter_combo.currentIndexChanged.connect(self._apply_installed_filter)
        installed_top_bar.addWidget(self.installed_search_input, 1)
        installed_top_bar.addWidget(self.installed_filter_combo)
        installed_top_bar.addSpacing(6)
        self.refresh_installed_button = QPushButton()
        self.refresh_installed_button.clicked.connect(self.refresh_installed_mods)
        installed_top_bar.addWidget(self.refresh_installed_button)
        self.installed_mods_list = QListWidget()
        self.installed_mods_list.setObjectName('modList')
        self.installed_mods_list.setSpacing(5)
        open_mods_folder_button_search = QPushButton()
        open_mods_folder_button_search.setObjectName('openModsFolderButton')
        open_mods_folder_button_search.setIcon(self.mods_icon)
        open_mods_folder_button_search.setIconSize(QSize(28, 28))
        open_mods_folder_button_search.setFixedSize(44, 44)
        open_mods_folder_button_search.clicked.connect(self.open_mods_folder)
        search_bottom_bar = QHBoxLayout()
        search_bottom_bar.addLayout(pagination_layout, 1)
        search_bottom_bar.addWidget(open_mods_folder_button_search)
        installed_bottom_bar = QHBoxLayout()
        installed_bottom_bar.addStretch()
        open_mods_folder_button_installed = QPushButton()
        open_mods_folder_button_installed.setObjectName('openModsFolderButton')
        open_mods_folder_button_installed.setIcon(self.mods_icon)
        open_mods_folder_button_installed.setIconSize(QSize(28, 28))
        open_mods_folder_button_installed.setFixedSize(44, 44)
        open_mods_folder_button_installed.clicked.connect(self.open_mods_folder)
        installed_bottom_bar.addWidget(open_mods_folder_button_installed)
        search_layout.addLayout(filters_layout)
        search_layout.addWidget(self.mod_search_input)
        search_layout.addWidget(self.mod_results_list, 1)
        search_layout.addLayout(search_bottom_bar)
        installed_layout.addLayout(installed_top_bar)
        installed_layout.addWidget(self.installed_mods_list, 1)
        installed_layout.addLayout(installed_bottom_bar)
        self.mods_sub_tabs.addTab(search_widget, '')
        self.mods_sub_tabs.addTab(installed_widget, '')
        self.tab_widget.addTab(self.mods_tab_widget, self.mods_icon, '')
        self.mods_sub_tabs.currentChanged.connect(self.on_mods_sub_tab_changed)
    def create_versions_tab(self):
        self.versions_tab_widget = QWidget()
        versions_layout = QVBoxLayout(self.versions_tab_widget)
        versions_layout.setContentsMargins(10, 10, 10, 10)
        versions_layout.setSpacing(10)
        top_bar_layout = QHBoxLayout()
        self.delete_selected_versions_button = QPushButton()
        self.delete_selected_versions_button.setObjectName('deleteSelectedButton')
        self.delete_selected_versions_button.setIcon(self.version_management_icons.get('delete'))
        self.delete_selected_versions_button.clicked.connect(self.delete_selected_versions)
        self.delete_selected_versions_button.setEnabled(False)
        top_bar_layout.addWidget(self.delete_selected_versions_button)
        self.new_installation_button = QPushButton()
        self.new_installation_button.setObjectName('newInstallationButton')
        self.new_installation_button.clicked.connect(self.open_new_installation_dialog)
        top_bar_layout.addWidget(self.new_installation_button)
        self.remote_instance_verify_btn = QPushButton()
        self.remote_instance_verify_btn.setObjectName('remoteInstanceVerifyButton')
        self.remote_instance_verify_btn.clicked.connect(self._verify_remote_instance_from_versions_tab)
        self.remote_instance_verify_btn.setVisible(False)
        top_bar_layout.addWidget(self.remote_instance_verify_btn)
        top_bar_layout.addStretch()
        self.refresh_versions_button = QPushButton()
        self.refresh_versions_button.clicked.connect(self.refresh_installed_versions_list)
        top_bar_layout.addWidget(self.refresh_versions_button)
        size_info_layout = QHBoxLayout()
        size_info_layout.setContentsMargins(0, 5, 10, 5)
        self.total_versions_size_label = QLabel()
        self.total_versions_size_label.setObjectName('totalSizeLabel')
        self.total_versions_size_label.setAlignment(Qt.AlignRight)
        size_info_layout.addStretch()
        size_info_layout.addWidget(self.total_versions_size_label)
        self.installed_versions_list = QListWidget()
        self.installed_versions_list.setObjectName('modList')
        self.installed_versions_list.setSpacing(5)
        self.installed_versions_list.currentItemChanged.connect(self._on_versions_current_item_changed)
        versions_layout.addLayout(top_bar_layout)
        versions_layout.addLayout(size_info_layout)
        versions_layout.addWidget(self.installed_versions_list, 1)
        self.tab_widget.addTab(self.versions_tab_widget, self.manage_versions_icon, '')
    def create_modpacks_tab(self):
        widget = QWidget()
        widget.setObjectName('modpacks')
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        self.modpack_info_title = QLabel(self.lang_dict.get('modpack_remote_title', 'Mods Evento/Serie'))
        self.modpack_info_title.setFont(self.subtitle_font)
        self.modpack_info_title.setObjectName('sectionLabel')
        self.modpack_status_label = QLabel(self.lang_dict.get('modpack_status_idle', 'Listo para buscar modpack...'))
        self.modpack_status_label.setFont(self.minecraft_font)
        self.modpack_status_label.setWordWrap(True)
        self.remote_modpacks_sync_btn = QPushButton()
        self.remote_modpacks_sync_btn.setFixedHeight(40)
        self.remote_modpacks_sync_btn.clicked.connect(self._sync_remote_modpacks)
        self.remote_modpacks_list = QListWidget()
        self.remote_modpacks_list.setObjectName('modList')
        self.remote_modpacks_list.setSpacing(6)
        self.remote_modpacks_list.setMinimumHeight(72)
        self.remote_modpacks_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.remote_modpacks_list.currentItemChanged.connect(self._on_remote_modpack_selection_changed)
        self.remote_modpack_install_btn = QPushButton()
        self.remote_modpack_install_btn.setFixedHeight(50)
        self.remote_modpack_install_btn.setFont(self.subtitle_font)
        self.remote_modpack_install_btn.clicked.connect(self._install_selected_remote_modpack)
        self.remote_modpack_install_btn.setEnabled(False)
        layout.addWidget(self.modpack_info_title)
        layout.addWidget(self.modpack_status_label)
        layout.addWidget(self.remote_modpacks_sync_btn)
        layout.addWidget(self.remote_modpacks_list)
        layout.addStretch()
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.remote_modpack_install_btn, 2)
        bottom_bar.addStretch()
        self.open_modpacks_folder_button = QPushButton()
        self.open_modpacks_folder_button.setObjectName('openModpacksFolderButton')
        self.open_modpacks_folder_button.setIcon(self.modpacks_icon)
        self.open_modpacks_folder_button.setIconSize(QSize(28, 28))
        self.open_modpacks_folder_button.setFixedSize(44, 44)
        self.open_modpacks_folder_button.clicked.connect(self.open_modpacks_folder)
        bottom_bar.addWidget(self.open_modpacks_folder_button)
        layout.addLayout(bottom_bar)
        self.tab_widget.addTab(widget, self.modpacks_icon, '')
        self._update_modpacks_tab_texts()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, self._sync_remote_modpacks)
    def create_console_tab(self):
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        self.clear_console_button = AnimatedButton('')
        self.clear_console_button.setFont(self.minecraft_font)
        self.clear_console_button.setFixedHeight(35)
        self.clear_console_button.clicked.connect(self.clear_console)
        self.console_output = QTextEdit()
        self.console_output.setFont(QFont('Consolas', 9))
        self.console_output.setObjectName('consoleOutput')
        self.console_output.setReadOnly(True)
        console_layout.addWidget(self.clear_console_button)
        console_layout.addWidget(self.console_output)
        self.tab_widget.addTab(console_widget, self.console_icon, '')
    def prev_mod_page(self):
        if self.mod_current_page > 1:
            self.mod_current_page -= 1
            self.update_mod_list(reset_page=False)
    def next_mod_page(self):
        if self.mod_current_page * MODS_PER_PAGE < self.mod_total_hits:
            self.mod_current_page += 1
            self.update_mod_list(reset_page=False)
    def update_pagination_controls(self):
        self.page_label.setText(f"{self.lang_dict.get('page', 'Page')} {self.mod_current_page}")
        is_prev_enabled = self.mod_current_page > 1
        self.prev_page_button.setEnabled(is_prev_enabled)
        self.prev_page_button.setStyleSheet('opacity: 1.0;' if is_prev_enabled else 'opacity: 0.4;')
        is_next_enabled = self.mod_current_page * MODS_PER_PAGE < self.mod_total_hits
        self.next_page_button.setEnabled(is_next_enabled)
        self.next_page_button.setStyleSheet('opacity: 1.0;' if is_next_enabled else 'opacity: 0.4;')
    def update_mod_list(self, reset_page=True):
        if self.mod_search_worker and self.mod_search_worker.isRunning():
            return
        else:
            if reset_page:
                self.mod_current_page = 1
            query = self.mod_search_input.text()
            game_version_full, _ = self._get_version_combo_selection()
            if not game_version_full:
                self.log_to_console('Select a game version to search for mods.')
                return
            else:
                game_version = helpers.get_base_version(game_version_full)
                loader = self.current_version_type
                if loader == 'vanilla':
                    self.mod_results_list.clear()
                    item = QListWidgetItem(self.lang_dict['select_mod_loader'])
                    item.setTextAlignment(Qt.AlignCenter)
                    self.mod_results_list.addItem(item)
                    return
                else:
                    sort_option = self.mod_sort_combo.currentData() or 'downloads'
                    offset = (self.mod_current_page - 1) * MODS_PER_PAGE
                    self.mod_refresh_button.setEnabled(False)
                    self.mod_results_list.clear()
                    item = QListWidgetItem(self.lang_dict.get('searching', 'Searching...'))
                    item.setTextAlignment(Qt.AlignCenter)
                    self.mod_results_list.addItem(item)
                    self.mod_search_worker = ModSearchWorker(query, game_version, loader, sort_option, self.lang_dict, offset, self)
                    self.mod_search_worker.finished.connect(self.on_mod_search_finished)
                    self.mod_search_worker.start()
    def on_mod_search_finished(self, results, total_hits):
        self.mod_total_hits = total_hits
        self.mod_results_list.clear()
        self.mod_list_item_map.clear()
        self.mod_refresh_button.setEnabled(True)
        try:
            version_id, _ = self._get_version_combo_selection()
            game_version = helpers.get_base_version(version_id) if version_id else None
        except (AttributeError, IndexError):
            game_version = None
        if not results:
            item = QListWidgetItem(self.lang_dict['no_mods_found'])
            item.setTextAlignment(Qt.AlignCenter)
            self.mod_results_list.addItem(item)
        else:
            installed_mods = self.get_installed_mods_info()
            for mod_data in results:
                project_id = mod_data.get('project_id')
                is_installed = project_id in installed_mods
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 84))
                card_widget = ModListItemWidget(mod_data, self.lang_dict, is_installed, game_version)
                card_widget.install_requested.connect(self.start_mod_download)
                card_widget.page_requested.connect(self.open_mod_page)
                card_widget.delete_requested.connect(self.delete_mod)
                self.mod_results_list.addItem(item)
                self.mod_results_list.setItemWidget(item, card_widget)
                self.mod_list_item_map[project_id] = card_widget
        self.update_pagination_controls()
    def refresh_installed_mods(self):
        if self.local_mods_scanner and self.local_mods_scanner.isRunning():
            return
        else:
            effective_dir = self.selected_instance_dir if self.selected_instance_dir and os.path.isdir(self.selected_instance_dir) else self.minecraft_directory
            mods_folder = os.path.join(effective_dir, 'mods')
            self.installed_mods_list.clear()
            item = QListWidgetItem(self.lang_dict.get('scanning', 'Scanning...'))
            item.setTextAlignment(Qt.AlignCenter)
            self.installed_mods_list.addItem(item)
            installed_data = self.get_installed_mods_info()
            self.local_mods_scanner = LocalModsScannerWorker(mods_folder, self.lang_dict, installed_data, self)
            self.local_mods_scanner.finished.connect(self.on_local_mods_scanned)
            self.local_mods_scanner.start()
    def on_local_mods_scanned(self, mods_list):
        self._installed_mods_cache = list(mods_list or [])
        self._apply_installed_filter()
    def _apply_installed_filter(self):
        if not hasattr(self, 'installed_mods_list'):
            return
        self.installed_mods_list.clear()
        query = self.installed_search_input.text().strip().lower()
        filter_key = self.installed_filter_combo.currentData() if hasattr(self, 'installed_filter_combo') else 'all'
        mods = []
        for mod_info in self._installed_mods_cache:
            if filter_key in (None, 'all') or mod_info.get('enabled') == (filter_key == 'enabled'):
                if (not query) or query in mod_info.get('name', '').lower() or query in str(mod_info.get('mod_id', '')).lower() or query in os.path.basename(str(mod_info.get('filepath', ''))).lower():
                    mods.append(mod_info)
        if not mods:
            item = QListWidgetItem(self.lang_dict.get('no_installed_mods_match', 'No se encontraron mods que coincidan.'))
            item.setTextAlignment(Qt.AlignCenter)
            self.installed_mods_list.addItem(item)
        else:
            for mod_info in sorted(mods, key=lambda x: x['name'].lower()):
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 90))
                widget = InstalledModListItemWidget(mod_info, self.lang_dict, main_font=self.minecraft_font, bold_font=self.subtitle_font)
                widget.delete_requested.connect(self.handle_mod_delete)
                widget.toggle_requested.connect(self.handle_mod_toggle)
                self.installed_mods_list.addItem(item)
                self.installed_mods_list.setItemWidget(item, widget)
    def handle_mod_delete(self, filepath):
        filename = os.path.basename(filepath)
        project_id_to_update = None
        installed_json = self.get_installed_mods_info()
        for pid, info in installed_json.items():
            if info.get('filename') == filename:
                project_id_to_update = pid
                break
        try:
            os.remove(filepath)
            self.log_to_console(f'Deleted mod file: {filename}')
            if project_id_to_update:
                self.remove_installed_mod_info(project_id_to_update)
                if project_id_to_update in self.mod_list_item_map:
                    widget = self.mod_list_item_map[project_id_to_update]
                    widget.is_installed = False
                    widget.update_view()
        except OSError as e:
            self.log_to_console(f'Error deleting file {filename}: {e}')
        self.refresh_installed_mods()
    def handle_mod_toggle(self, filepath, is_enabled):
        new_path = None
        if is_enabled and filepath.endswith('.jar.disabled'):
            new_path = filepath[:(-9)]
        else:
            if not is_enabled and filepath.endswith('.jar'):
                    new_path = filepath + '.disabled'
        if new_path:
            try:
                os.rename(filepath, new_path)
                status = 'enabled' if is_enabled else 'disabled'
                self.log_to_console(f'Mod {os.path.basename(new_path)} has been {status}.')
                self.refresh_installed_mods()
            except Exception as e:
                self.log_to_console(f'Error toggling mod {os.path.basename(filepath)}: {e}')
                self.refresh_installed_mods()
        else:
            logging.warning(f'Mod toggle for {os.path.basename(filepath)} skipped: already in desired state.')
    def update_version_display(self):
        self.version_status_label.setStyleSheet('color: #6E6E82;')
        self.version_status_label.setText(APP_VERSION)
    def _get_resolved_java_path(self, mc_version: str):
        """\n        Elige la instalación de Java más reciente que cumpla el mínimo de la versión de MC.\n        Devuelve (ruta_ejecutable, java_requerida, java_detectada_o_None).\n        """
        preferred = (self.settings.get('java_path') or '').strip() or None
        return resolve_java_for_minecraft(mc_version, preferred_exe=preferred)
    def open_folder(self, subfolder_name):
        folder_path = os.path.join(self.minecraft_directory, subfolder_name)
        os.makedirs(folder_path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
    def open_mods_folder(self):
        effective_dir = self.selected_instance_dir if self.selected_instance_dir and os.path.isdir(self.selected_instance_dir) else self.minecraft_directory
        folder_path = os.path.join(effective_dir, 'mods')
        os.makedirs(folder_path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
    def _sync_remote_modpacks(self):
        """Consulta automáticamente el manifest desde la URL configurada."""
        self.modpack_status_label.setText(self.lang_dict.get('modpack_fetching', 'Consultando modpack...'))
        self.remote_modpacks_sync_btn.setEnabled(False)
        self.remote_modpacks_list.clear()
        class FetchWorker(QThread):
            finished = Signal(list)
            def run(self):
                manifests = remote_modpack.fetch_remote_manifests(MODPACK_MANIFEST_URL)
                self.finished.emit(manifests or [])
        self.fetch_worker = FetchWorker(self)
        self.fetch_worker.finished.connect(self._on_manifests_fetched)
        self.fetch_worker.start()
    def _on_manifests_fetched(self, manifests):
        self.remote_modpacks_sync_btn.setEnabled(True)
        if not manifests:
            self.modpack_status_label.setText(self.lang_dict.get('modpack_fetch_error', 'No se pudo obtener el modpack.'))
            self.detected_remote_modpacks = []
            self.remote_modpack_install_btn.setEnabled(False)
            return
        else:
            self.detected_remote_modpacks = [{'manifest': m, 'name': m.get('name', 'Modpack')} for m in manifests]
            self.remote_modpacks_list.clear()
            for entry in self.detected_remote_modpacks:
                manifest = entry['manifest']
                card = ModpackListItemWidget(manifest, self.lang_dict)
                list_item = QListWidgetItem()
                list_item.setSizeHint(card.sizeHint())
                list_item.setData(Qt.UserRole, entry)
                self.remote_modpacks_list.addItem(list_item)
                self.remote_modpacks_list.setItemWidget(list_item, card)
            count = len(manifests)
            row_height = 68
            self.remote_modpacks_list.setFixedHeight(min(300, max(72, count * row_height + 12)))
            if self.remote_modpacks_list.count():
                self.remote_modpacks_list.setCurrentRow(0)
            else:
                self.modpack_status_label.setText(self.lang_dict.get('modpack_select_hint', 'Haz clic en un modpack de la lista para seleccionarlo.'))
                self.remote_modpack_install_btn.setEnabled(False)
            self._update_modpacks_tab_texts()
            self._update_remote_verify_button()
    def _on_remote_modpack_selection_changed(self, current, _previous=None):
        for index in range(self.remote_modpacks_list.count()):
            item = self.remote_modpacks_list.item(index)
            widget = self.remote_modpacks_list.itemWidget(item)
            if widget and hasattr(widget, 'set_selected'):
                    widget.set_selected(item is current)
        if not current:
            self.modpack_status_label.setText(self.lang_dict.get('modpack_select_hint', 'Haz clic en un modpack de la lista para seleccionarlo.'))
            self.remote_modpack_install_btn.setEnabled(False)
            return
        else:
            entry = current.data(Qt.UserRole) or {}
            manifest = entry.get('manifest') or {}
            name = entry.get('name') or manifest.get('name', 'Modpack')
            instance_dir = remote_modpack.resolve_instance_dir(self.minecraft_directory, manifest)
            installed = remote_modpack.instance_is_installed(instance_dir)
            actualizacion = remote_modpack.is_actualizacion_enabled(manifest)
            if installed and (not actualizacion):
                status = self.lang_dict.get('modpack_up_to_date', 'Ya tienes la última versión.')
            else:
                if installed and actualizacion:
                    status = self.lang_dict.get('modpack_ready_update', 'Instancia instalada. Verifica en la pestaña Versiones.')
                else:
                    status = self.lang_dict.get('modpack_selected', 'Seleccionado: {name}').format(name=name)
            self.modpack_status_label.setText(status)
            self.remote_modpack_install_btn.setEnabled(True)
    def _on_manifest_fetched(self, manifest):
        """Compatibilidad: un solo manifest."""
        self._on_manifests_fetched([manifest] if manifest else [])
    def _update_modpacks_tab_texts(self):
        lang = self.lang_dict
        if hasattr(self, 'modpack_info_title'):
            self.modpack_info_title.setText(lang.get('modpack_remote_title', 'Mods Evento/Serie'))
        if hasattr(self, 'remote_modpack_install_btn'):
            self.remote_modpack_install_btn.setText(lang.get('install_modpack', 'Instalar Modpack'))
        if hasattr(self, 'remote_instance_verify_btn'):
            self.remote_instance_verify_btn.setText(lang.get('verify_modpack', 'Verificar'))
            self.remote_instance_verify_btn.setToolTip(lang.get('verify_modpack_tooltip', 'Compara y actualiza solo la carpeta mods'))
        if hasattr(self, 'remote_modpacks_sync_btn'):
            self.remote_modpacks_sync_btn.setText(lang.get('refresh_modpack', 'Actualizar Consulta'))
    def _is_remote_instance_dir(self, instance_dir: str) -> bool:
        if not instance_dir or not os.path.isdir(instance_dir):
            return False
        else:
            meta = load_instance_meta(instance_dir)
            return meta.get('source', 'remote') == 'remote'
    def _find_manifest_for_instance(self, instance_dir: str):
        if not instance_dir:
            return
        else:
            target = os.path.normcase(os.path.abspath(instance_dir))
            folder_name = os.path.basename(instance_dir.rstrip('\\/'))
            meta = load_instance_meta(instance_dir)
            def matches(manifest: dict) -> bool:
                resolved = remote_modpack.resolve_instance_dir(self.minecraft_directory, manifest)
                if os.path.normcase(os.path.abspath(resolved)) == target:
                    return True
                else:
                    manifest_name = remote_modpack.sanitize_instance_name(manifest.get('name', ''))
                    meta_name = remote_modpack.sanitize_instance_name(meta.get('name', ''))
                    return manifest_name == folder_name or manifest_name == meta_name
            for entry in getattr(self, 'detected_remote_modpacks', []) or []:
                manifest = entry.get('manifest') or {}
                if not matches(manifest):
                    continue
                else:
                    return manifest
            for manifest in remote_modpack.fetch_remote_manifests(MODPACK_MANIFEST_URL):
                if not matches(manifest):
                    continue
                else:
                    return manifest
    def _prompt_modpack_password(self, manifest: dict) -> bool:
        required_pass = str(manifest.get('pass') or '').strip()
        if not required_pass:
            QMessageBox.warning(self, self.lang_dict.get('password_required_title', 'Contraseña requerida'), self.lang_dict.get('modpack_pass_missing', 'Cada modpack debe incluir su propia contraseña: \"pass\": \"tu_clave\"'))
            return False
        else:
            dialog = PasswordDialog(self.lang_dict.get('password_required_title', 'Contraseña requerida'), self.lang_dict.get('password_required_prompt', 'Este modpack requiere una contraseña.'), self.lang_dict, self)
            if dialog.exec() != QDialog.Accepted:
                return False
            else:
                if dialog.get_password() != required_pass:
                    QMessageBox.critical(self, 'Error', self.lang_dict.get('invalid_password', 'Contraseña incorrecta.'))
                    return False
                else:
                    return True
    def _update_remote_verify_button(self):
        if not hasattr(self, 'remote_instance_verify_btn'):
            return
        else:
            instance_dir = getattr(self, '_versions_selected_instance_dir', '') or ''
            source = getattr(self, '_versions_selected_source', '') or ''
            is_remote = bool(instance_dir) and source == 'remote'
            self.remote_instance_verify_btn.setVisible(is_remote)
            self.remote_instance_verify_btn.setEnabled(is_remote)
    def _on_versions_current_item_changed(self, current, previous):
        data = current.data(Qt.UserRole) if current else None
        if isinstance(data, dict):
            self._versions_selected_instance_dir = data.get('instance_dir', '') or ''
            self._versions_selected_source = data.get('source', '') or ''
        else:
            self._versions_selected_instance_dir = ''
            self._versions_selected_source = ''
        self._update_remote_verify_button()
    def _start_modpack_mods_update(self, manifest: dict, instance_dir: str):
        self.remote_instance_verify_btn.setEnabled(False)
        self.remote_instance_verify_btn.setText(self.lang_dict.get('verifying_modpack', 'Verificando...'))
        idx = self.tab_widget.indexOf(self.console_output.parentWidget())
        if idx >= 0:
            self.tab_widget.setCurrentIndex(idx)
        self._pending_install_manifest = manifest
        self._pending_instance_dir = instance_dir
        self.modpack_verify_worker = ModpackVerifyWorker(manifest, instance_dir, self.lang_dict, apply_updates=True, parent=self)
        self.modpack_verify_worker.progress_status.connect(self.log_to_console)
        self.modpack_verify_worker.finished.connect(self._on_modpack_verify_finished)
        self.modpack_verify_worker.start()
    def _run_modpack_verify(self, manifest: dict, instance_dir: str):
        from kaz_launcher.core.instance_sync import verify_remote_mods
        report = verify_remote_mods(manifest, instance_dir, self.lang_dict)
        if report.errors:
            QMessageBox.warning(self, 'Modpack', report.errors[0])
            return
        else:
            if report.up_to_date:
                QMessageBox.information(self, 'Modpack', self.lang_dict.get('modpack_up_to_date', 'Ya tienes la última versión.'))
                return
            else:
                details = report.format_diff_details(self.lang_dict)
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Warning)
                box.setWindowTitle('Modpack')
                box.setText(details)
                box.setInformativeText(self.lang_dict.get('modpack_update_mods_prompt', '¿Actualizar la carpeta mods? Se descargarán faltantes y se eliminarán sobrantes.'))
                box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                box.button(QMessageBox.Yes).setText(self.lang_dict.get('modpack_update_mods_btn', 'Actualizar mods'))
                box.button(QMessageBox.No).setText(self.lang_dict.get('cancel_button', 'Cancelar'))
                if box.exec() != QMessageBox.Yes:
                    return
                else:
                    self._start_modpack_mods_update(manifest, instance_dir)
    def _verify_remote_instance_from_versions_tab(self):
        if getattr(self, 'modpack_verify_worker', None) and self.modpack_verify_worker.isRunning():
            return
        else:
            instance_dir = getattr(self, '_versions_selected_instance_dir', '') or self.selected_instance_dir or self.settings.get('selected_instance_dir', '')
            if not self._is_remote_instance_dir(instance_dir):
                QMessageBox.information(self, 'Modpack', self.lang_dict.get('verify_remote_only', 'Solo disponible en instancias instaladas remotamente.'))
                return
            else:
                if not remote_modpack.instance_is_installed(instance_dir):
                    QMessageBox.information(self, 'Modpack', self.lang_dict.get('modpack_not_installed', 'Primero instala el modpack.'))
                    return
                else:
                    manifest = self._find_manifest_for_instance(instance_dir)
                    if not manifest:
                        QMessageBox.warning(self, 'Modpack', self.lang_dict.get('modpack_manifest_not_found', 'No se encontró el modpack remoto de esta instancia. Pulsa Actualizar Consulta.'))
                        return
                    else:
                        self._run_modpack_verify(manifest, instance_dir)
    def _install_selected_remote_modpack(self):
        items = self.remote_modpacks_list.selectedItems()
        if not items or (self.modpack_install_worker and self.modpack_install_worker.isRunning()):
            return None
        else:
            item = items[0].data(Qt.UserRole)
            if not item:
                return
            else:
                manifest = item['manifest']
                instance_dir = remote_modpack.resolve_instance_dir(self.minecraft_directory, manifest)
                already_installed = remote_modpack.instance_is_installed(instance_dir)
                if not already_installed and (not self._prompt_modpack_password(manifest)):
                    return
                else:
                    ok, err = remote_modpack.validate_manifest(manifest)
                    if not ok:
                        QMessageBox.warning(self, 'Modpack', err)
                        return
                    else:
                        instance_dir = remote_modpack.resolve_instance_dir(self.minecraft_directory, manifest)
                        os.makedirs(instance_dir, exist_ok=True)
                        installed = remote_modpack.instance_is_installed(instance_dir)
                        actualizacion = remote_modpack.is_actualizacion_enabled(manifest)
                        if installed and (not actualizacion):
                            QMessageBox.information(self, 'Modpack', self.lang_dict.get('modpack_up_to_date', 'Ya tienes la última versión.'))
                            return
                        else:
                            install_mode = 'mods_only' if installed and actualizacion else 'full'
                            self.remote_modpack_install_btn.setEnabled(False)
                            self.remote_modpack_install_btn.setText(self.lang_dict.get('installing_modpack', 'Instalando modpack...'))
                            self._set_installing_state(True, self.lang_dict.get('installing_modpack', 'Instalando modpack...'))
                            idx = self.tab_widget.indexOf(self.console_output.parentWidget())
                            if idx >= 0:
                                self.tab_widget.setCurrentIndex(idx)
                            mc_for_java = manifest.get('minecraft_version') or manifest.get('mc_version') or '1.21'
                            java_path, _, _ = self._get_resolved_java_path(mc_for_java)
                            self._pending_install_manifest = manifest
                            self._pending_instance_dir = instance_dir
                            self.modpack_install_worker = ModpackInstallWorker(manifest, self.minecraft_directory, self.lang_dict, java_path=java_path, target_instance_dir=instance_dir, mode=install_mode, parent=self)
                            self.modpack_install_worker.progress_status.connect(self.log_to_console)
                            self.modpack_install_worker.finished.connect(self._on_modpack_install_finished)
                            self.modpack_install_worker.start()
    def _on_modpack_verify_finished(self, success, msg):
        if hasattr(self, 'remote_instance_verify_btn'):
            self.remote_instance_verify_btn.setEnabled(True)
            self.remote_instance_verify_btn.setText(self.lang_dict.get('verify_modpack', 'Verificar'))
        self.remote_modpack_install_btn.setEnabled(True)
        self.remote_modpack_install_btn.setText(self.lang_dict.get('install_modpack', 'Instalar'))
        if getattr(self, '_prelaunch_update_pending', None):
            self._prelaunch_update_pending = None
            if success:
                self.log_to_console(msg)
                self._start_java_ensure()
            else:
                fail_msg = self.lang_dict.get('prelaunch_mods_update_failed', 'No se pudieron actualizar los mods: {msg}').format(msg=msg)
                self.log_to_console(fail_msg)
                reply = QMessageBox.question(self, 'Modpack', fail_msg + '\n\n¿Continuar con el inicio de todas formas?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self._start_java_ensure()
                else:
                    self._pending_launch = None
                    self.launch_control_stack.setCurrentIndex(0)
            return
        if success:
            self.log_to_console(msg)
            QMessageBox.information(self, 'Modpack', msg)
            self.refresh_installed_versions_list()
        else:
            self.log_to_console(self.lang_dict.get('modpack_verify_error', 'Error: {msg}').format(msg=msg))
            QMessageBox.warning(self, 'Modpack', msg)
    def open_new_installation_dialog(self):
        dialog = NewInstallationDialog(self, self.lang_dict)
        if dialog.exec() != QDialog.Accepted:
            return
        else:
            selection = dialog.get_selection()
            loader = selection.get('loader', 'vanilla')
            mc_version = selection.get('minecraft_version', '').strip()
            loader_version = selection.get('loader_version', '').strip()
            if not mc_version:
                QMessageBox.warning(self, self.lang_dict.get('new_installation_title', 'Nueva instalación'), self.lang_dict.get('no_versions_found', 'Selecciona una versión de Minecraft.'))
                return
            else:
                if loader != 'vanilla' and (not loader_version):
                    QMessageBox.warning(self, self.lang_dict.get('new_installation_title', 'Nueva instalación'), self.lang_dict.get('no_loader_versions', 'Selecciona una versión del mod loader.'))
                    return
                else:
                    self.new_installation_button.setEnabled(False)
                    self.new_installation_button.setText(self.lang_dict.get('installing_modpack', 'Instalando...'))
                    self._set_installing_state(True, self.lang_dict.get('installing_modpack', 'Instalando modpack...'))
                    idx = self.tab_widget.indexOf(self.console_output.parentWidget())
                    if idx >= 0:
                        self.tab_widget.setCurrentIndex(idx)
                    java_path, _, _ = self._get_resolved_java_path(mc_version)
                    self.manual_install_worker = ManualInstallWorker(loader, mc_version, loader_version, self.minecraft_directory, java_path=java_path, parent=self)
                    self.manual_install_worker.progress_status.connect(self.log_to_console)
                    self.manual_install_worker.finished.connect(self._on_manual_install_finished)
                    self.manual_install_worker.start()
    def _on_manual_install_finished(self, success, msg, result):
        self._set_installing_state(False)
        self.new_installation_button.setEnabled(True)
        self.new_installation_button.setText(self.lang_dict.get('new_installation', 'Nueva instalación'))
        if success:
            version_id = (result or {}).get('version_id')
            instance_dir = (result or {}).get('instance_dir') or ''
            if instance_dir and version_id:
                    self.selected_instance_dir = instance_dir
                    self.settings['selected_instance_dir'] = instance_dir
                    self.settings['last_version'] = version_id
                    self.settings['version_type'] = (result or {}).get('loader') or self.current_version_type
                    self.current_version_type = self.settings['version_type']
                    self.installed_mods_path = os.path.join(instance_dir, 'installed_mods.json')
                    settings.save_settings(self.settings)
                    self._select_instance_on_refresh = instance_dir
                    self.populate_versions(self.current_version_type)
            self.refresh_installed_versions_list()
            ok_text = self.lang_dict.get('manual_install_ok', 'Instalación completada correctamente.')
            self.log_to_console(ok_text)
            QMessageBox.information(self, self.lang_dict.get('new_installation_title', 'Nueva instalación'), ok_text)
        else:
            err_text = self.lang_dict.get('manual_install_error', 'Error en la instalación: {msg}').format(msg=msg)
            self.log_to_console(err_text)
            QMessageBox.critical(self, self.lang_dict.get('new_installation_title', 'Nueva instalación'), msg)
    def _on_modpack_install_finished(self, success, msg):
        self._set_installing_state(False)
        self.remote_modpack_install_btn.setEnabled(True)
        self.remote_modpack_install_btn.setText(self.lang_dict.get('install_modpack', 'Instalar'))
        self._update_remote_verify_button()
        if success:
            manifest = getattr(self, '_pending_install_manifest', {}) or {}
            instance_dir = getattr(self, '_pending_instance_dir', '') or ''
            loader = (manifest.get('loader') or 'forge').lower()
            game_ver = str(manifest.get('game_version') or '').strip()
            loader_ver = str(manifest.get('loader_version') or '').strip()
            modpack_name = manifest.get('name') or (os.path.basename(instance_dir) if instance_dir else 'Modpack')
            version_id = resolve_version_id(instance_dir, loader, game_ver, loader_ver) if instance_dir else None
            if instance_dir and version_id:
                    save_instance_meta(instance_dir, name=modpack_name, version_id=version_id, loader=loader, game_version=game_ver, manifest_url=MODPACK_MANIFEST_URL, manifest_revision=str(manifest.get('revision') or ''), actualizacion=remote_modpack.is_actualizacion_enabled(manifest))
                    self.selected_instance_dir = instance_dir
                    self.settings['selected_instance_dir'] = instance_dir
                    self.settings['version_type'] = loader
                    self.settings['last_version'] = version_id
                    self.current_version_type = loader
                    self.installed_mods_path = os.path.join(instance_dir, 'installed_mods.json')
                    settings.save_settings(self.settings)
                    self._select_instance_on_refresh = instance_dir
                    self.populate_versions(self.current_version_type)
            display_msg = msg or self.lang_dict.get('modpack_installed_ok', 'Modpack instalado correctamente.')
            self.log_to_console(display_msg)
            QMessageBox.information(self, 'Modpack', display_msg)
        else:
            self.log_to_console(self.lang_dict.get('modpack_install_error', 'Error: {msg}').format(msg=msg))
            QMessageBox.critical(self, 'Modpack', msg)
    def open_modpacks_folder(self):
        self.open_folder('modpacks')
    def open_color_picker(self, kind='primary'):
        current = self.current_accent_color_secondary if kind == 'secondary' else self.current_accent_color
        color = QColorDialog.getColor(QColor(current), self, 'Select Accent Color')
        if color.isValid():
            if kind == 'secondary':
                self.current_accent_color_secondary = color.name()
                self.settings['accent_color_secondary'] = self.current_accent_color_secondary
            else:
                self.current_accent_color = color.name()
                self.settings['accent_color'] = self.current_accent_color
            settings.save_settings(self.settings)
            self.update_color_preview()
            self.apply_theme()
    def open_java_path_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Java Executable', '', 'Executables (java.exe);;All files (*)')
        if file_path:
            self.java_path_input.setText(file_path)
    def update_color_preview(self):
        self.color_preview.setStyleSheet(f'background-color: {self.current_accent_color}; border: 2px solid rgba(255, 255, 255, 0.15); border-radius: 10px;')
        if hasattr(self, 'color_preview_secondary'):
            self.color_preview_secondary.setStyleSheet(f'background-color: {self.current_accent_color_secondary}; border: 2px solid rgba(255, 255, 255, 0.15); border-radius: 10px;')
    def update_title_glow(self):
        self.glow_effect.setColor(QColor(getattr(self, 'current_accent_color_secondary', self.current_accent_color)))
        self.title_label.setGraphicsEffect(self.glow_effect)
    def save_settings(self):
        self.settings['window_geometry'] = self.saveGeometry().toBase64().data().decode('utf-8')
        self.settings['jvm_args'] = self.settings.get('jvm_args', '')
        self.settings['java_path'] = self.settings.get('java_path', '')
        self.settings['selected_instance_dir'] = self.selected_instance_dir if getattr(self, 'selected_instance_dir', None) else self.settings.get('selected_instance_dir', '')
        self.settings.update({'memory': self.memory_slider.value(), 'fullscreen': self.fullscreen_checkbox.isChecked(), 'close_launcher': self.close_launcher_checkbox.isChecked(), 'last_username': self.user_input.text(), 'resolution_width': self.resolution_width_input.text(), 'resolution_height': self.resolution_height_input.text(), 'version_type': self.current_version_type, 'last_version': self._get_version_combo_selection()[0] or self.settings.get('last_version', ''), 'accent_color': self.current_accent_color, 'accent_color_secondary': getattr(self, 'current_accent_color_secondary', '#8B5CF6'), 'theme': getattr(self, 'current_theme', 'default'), 'glass_gradient': self.settings.get('glass_gradient') or ['#1E1B4B', '#312E81', '#0E7490', '#134E4A'], 'ui_glass_opacity': getattr(self, 'ui_opacity_slider', None) and self.ui_opacity_slider.value() or self.settings.get('ui_glass_opacity', 88), 'last_tab': self.tab_widget.currentIndex()})
        settings.save_settings(self.settings)
    def change_version_type(self, type_id):
        types_map = {0: 'vanilla', 1: 'forge', 2: 'fabric'}
        self.current_version_type = types_map.get(type_id, 'vanilla')
        self.populate_versions(self.current_version_type)
        self.mod_results_list.clear()
        self.mod_search_input.clear()
        self.on_tab_changed(self.tab_widget.currentIndex())
    def update_ui_text(self):
        lang = self.lang_dict
        self.setWindowTitle(lang.get('app_title', 'KazLauncher'))
        self.title_label.setText(lang['title'])
        self.version_label.setText(lang['version'])
        self.username_label.setText(lang['username'])
        self.launch_button.setText(lang['launch'])
        self.cancel_button.setText(lang.get('cancel', 'Cancel'))
        self.user_input.setPlaceholderText(lang['enter_username'])
        if hasattr(self, 'account_selector_label'):
            self.account_selector_label.setText(lang.get('account_selector_label', 'Seleccionar cuenta'))
        if hasattr(self, 'logout_account_btn'):
            self.logout_account_btn.setToolTip(lang.get('logout_account_tooltip', 'Cerrar sesión'))
        if hasattr(self, 'account_combo'):
            self._refresh_account_selector()
        if hasattr(self, 'login_status_label'):
            self._update_login_status_label()
        self.tab_widget.setTabText(0, lang['news'])
        self.tab_widget.setTabText(1, lang['mods'])
        self.tab_widget.setTabText(2, lang.get('versions_management', 'Versiones'))
        self.tab_widget.setTabText(3, lang['modpacks'])
        self.tab_widget.setTabText(4, '')
        self.tab_widget.setTabText(5, '')
        self.tab_widget.setTabToolTip(4, lang.get('tooltip_console', 'Consola'))
        self.tab_widget.setTabToolTip(5, lang.get('tooltip_settings', 'Configuración'))
        if hasattr(self, 'mods_sub_tabs'):
            self.mods_sub_tabs.setTabText(0, lang.get('search', 'Search'))
            self.mods_sub_tabs.setTabText(1, lang.get('installed', 'Installed'))
            self.refresh_installed_button.setText(lang.get('refresh', 'Refresh'))
        if hasattr(self, 'installed_search_input'):
            self.installed_search_input.setPlaceholderText(lang.get('installed_search_placeholder', 'Buscar mods instalados...'))
        if hasattr(self, 'installed_filter_combo'):
            current_filter = self.installed_filter_combo.currentData()
            self.installed_filter_combo.clear()
            self.installed_filter_combo.addItem(lang.get('installed_filter_all', 'Todos'), 'all')
            self.installed_filter_combo.addItem(lang.get('installed_filter_enabled', 'Habilitados'), 'enabled')
            self.installed_filter_combo.addItem(lang.get('installed_filter_disabled', 'Deshabilitados'), 'disabled')
            if current_filter:
                index = self.installed_filter_combo.findData(current_filter)
                if index != (-1):
                    self.installed_filter_combo.setCurrentIndex(index)
        if hasattr(self, 'new_installation_button'):
            self.new_installation_button.setText(lang.get('new_installation', 'Nueva instalación'))
            self.new_installation_button.setToolTip(lang.get('new_installation_tooltip', 'Instalar Vanilla, Forge, NeoForge o Fabric'))
        if hasattr(self, 'remote_instance_verify_btn'):
            self.remote_instance_verify_btn.setText(lang.get('verify_modpack', 'Verificar'))
            self.remote_instance_verify_btn.setToolTip(lang.get('verify_modpack_tooltip', 'Compara y actualiza solo la carpeta mods'))
        if hasattr(self, 'refresh_versions_button'):
            self.refresh_versions_button.setText(lang.get('versions_refresh', 'Refresh'))
            self.refresh_versions_button.setToolTip(lang.get('versions_refresh', 'Refresh'))
            if hasattr(self, 'delete_selected_versions_button'):
                delete_tooltip = lang.get('delete_selected', 'Delete Selected')
                self.delete_selected_versions_button.setText(delete_tooltip)
                self.delete_selected_versions_button.setToolTip(delete_tooltip)
        self.accent_color_label.setText(lang['accent_color'])
        if hasattr(self, 'theme_style_label'):
            self.theme_style_label.setText(lang.get('theme_style_label', 'Estilos'))
        if hasattr(self, 'glass_extras_btn'):
            self.glass_extras_btn.setText(lang.get('glass_extras_btn', 'Extras'))
            self.glass_extras_btn.setToolTip(lang.get('glass_gradient_title', 'Degradado de fondo (Glass)'))
        if hasattr(self, 'check_updates_button'):
            self._set_update_link_state(getattr(self, '_update_available', False))
        if hasattr(self, 'theme_style_combo'):
            self.theme_style_combo.blockSignals(True)
            self.theme_style_combo.clear()
            self.theme_style_combo.addItem(lang.get('theme_default', 'Default'), 'default')
            self.theme_style_combo.addItem(lang.get('theme_skeumorph', 'Skeumorph'), 'skeumorph')
            self.theme_style_combo.addItem(lang.get('theme_glass', 'Glass'), 'glass')
            index = self.theme_style_combo.findData(getattr(self, 'current_theme', 'default'))
            self.theme_style_combo.setCurrentIndex(index if index != (-1) else 0)
            self.theme_style_combo.blockSignals(False)
        self._update_glass_extras_visibility()
        if hasattr(self, 'ui_opacity_label'):
            self.ui_opacity_label.setText(lang.get('ui_glass_opacity', 'Opacidad del panel'))
        if hasattr(self, 'ui_opacity_hint'):
            self.ui_opacity_hint.setText(lang.get('ui_glass_opacity_hint', 'Más alto = menos transparencia'))
        self.color_picker_button.setText(lang['choose_color'])
        if hasattr(self, 'color_picker_secondary_button'):
            self.color_picker_secondary_button.setText(lang.get('choose_color_secondary', 'Color secundario'))
            self.color_picker_secondary_button.setToolTip(lang.get('choose_color_secondary', 'Color secundario'))
        self.memory_label.setText(lang['memory'])
        self.fullscreen_checkbox.setText(lang['fullscreen'])
        self.close_launcher_checkbox.setText(lang['close_launcher'])
        self.clear_console_button.setText(lang['clear_console'])
        self.advanced_settings_button.setText(lang['advanced_settings_show'])
        self.resolution_label.setText(lang.get('resolution', 'Game Resolution'))
        self.prev_page_button.setToolTip(lang.get('prev_page', 'Previous'))
        self.next_page_button.setToolTip(lang.get('next_page', 'Next'))
        self.page_label.setText(f"{lang.get('page', 'Page')} {self.mod_current_page}")
        self.version_type_label.setText(lang['version_type'])
        self.vanilla_radio.setText(lang['vanilla'])
        self.forge_radio.setText(lang['forge'])
        self.fabric_radio.setText(lang['fabric'])
        self.update_memory_feedback(self.memory_slider.value())
        if hasattr(self, 'open_mods_folder_button_search'):
            open_mods_folder_button_search.setToolTip(lang['open_mods_folder'])
        if hasattr(self, 'open_modpacks_folder_button'):
            self.open_modpacks_folder_button.setToolTip(lang['open_modpacks_folder'])
        if hasattr(self, '_update_modpacks_tab_texts'):
            self._update_modpacks_tab_texts()
        self.mod_search_input.setPlaceholderText(lang['search_mods_placeholder'])
        self.mod_sort_label.setText(lang['sort_by'])
        self.mod_refresh_button.setText(lang['refresh'])
        current_sort_data = self.mod_sort_combo.currentData()
        self.mod_sort_combo.clear()
        self.mod_sort_combo.addItem(lang['downloads'], 'downloads')
        self.mod_sort_combo.addItem(lang['relevance'], 'relevance')
        self.mod_sort_combo.addItem(lang['newest'], 'newest')
        if current_sort_data:
            index = self.mod_sort_combo.findData(current_sort_data)
            if index != (-1):
                self.mod_sort_combo.setCurrentIndex(index)
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'objectName') and tab.objectName() == 'news':
                    continue
    def _on_ui_opacity_changed(self, value: int):
        self.settings['ui_glass_opacity'] = value
        self.ui_opacity_value_label.setText(f'{value}%')
        self.apply_theme()
    def check_for_updates(self, silent: bool=False):
        """Consulta el manifest remoto en segundo plano."""
        if getattr(self, 'update_check_worker', None) and self.update_check_worker.isRunning():
            return
        if not hasattr(self, 'check_updates_button'):
            return
        self._update_check_silent = silent
        self.check_updates_button.setText(self.lang_dict.get('checking_updates', 'Buscando actualizaciones...'))
        worker = updater.UpdateCheckWorker(APP_VERSION, parent=self)
        self.update_check_worker = worker
        worker.finished_check.connect(self._on_update_check_finished)
        worker.start()
    def _on_update_check_finished(self, ok, info):
        silent = getattr(self, '_update_check_silent', False)
        if not ok:
            self._set_update_link_state(False)
            error = str((info or {}).get('error') or '')
            if not silent:
                message = self.lang_dict.get('error_checking_updates', 'Error al buscar actualizaciones')
                if error and error != 'update_manifest_missing':
                    message = f'{message}\n\n{error}'
                QMessageBox.warning(self, self.lang_dict.get('update_status_title', 'Actualización'), message)
            return
        available = bool(info.get('update_available'))
        remote_version = info.get('version', '')
        self._set_update_link_state(available)
        if available:
            text = self.lang_dict.get('update_available', 'Hay una nueva versión disponible: {version}').format(version=remote_version)
        else:
            text = self.lang_dict.get('latest_version', 'Tienes la última versión')
        self._update_info = info
        if silent and not available:
            return
        self._show_update_dialog({'is_update_available': available, 'text': text, 'info': info})
    def _set_update_link_state(self, available: bool = False):
        """Estado del enlace de actualización que acompaña a la versión."""
        self._update_available = bool(available)
        if self._update_available:
            self.check_updates_button.setText(self.lang_dict.get('update_available_link', 'Nueva actualización disponible'))
        else:
            self.check_updates_button.setText(self.lang_dict.get('check_updates_btn', 'Buscar actualizaciones'))
        self.check_updates_button.setProperty('updateAvailable', self._update_available)
        style = self.check_updates_button.style()
        style.unpolish(self.check_updates_button)
        style.polish(self.check_updates_button)
    def _show_update_dialog(self, status_info):
        fonts = {'main': self.minecraft_font, 'subtitle': self.subtitle_font}
        dialog = UpdateDialog(status_info, fonts, self.lang_dict, self)
        self._update_dialog = dialog
        dialog.update_requested.connect(self.start_update_download)
        dialog.exec()
        if getattr(self, '_update_dialog', None) is dialog:
            self._update_dialog = None
    def _ensure_writable_dir(self, directory: str) -> bool:
        probe = os.path.join(directory, '.kazlauncher_write_test')
        try:
            with open(probe, 'w', encoding='utf-8') as f:
                f.write('ok')
            os.remove(probe)
            return True
        except OSError:
            return False
    def start_update_download(self):
        """Descarga el exe nuevo, verifica el SHA-256 y programa el reemplazo."""
        info = getattr(self, '_update_info', None) or {}
        exe_path = updater.get_launcher_exe_path()
        if not exe_path:
            QMessageBox.information(self, self.lang_dict.get('update_status_title', 'Actualización'), self.lang_dict.get('update_not_frozen', 'La actualización automática solo está disponible en el ejecutable compilado.'))
            return
        url = info.get('url') or ''
        if not url:
            QMessageBox.warning(self, self.lang_dict.get('update_status_title', 'Actualización'), self.lang_dict.get('update_manifest_missing', 'No hay un servidor de actualizaciones configurado.'))
            return
        exe_dir = os.path.dirname(exe_path)
        if not self._ensure_writable_dir(exe_dir):
            QMessageBox.warning(self, self.lang_dict.get('update_status_title', 'Actualización'), self.lang_dict.get('update_apply_failed', 'No se pudo instalar la actualización: {msg}').format(msg='La carpeta del launcher no tiene permisos de escritura. Mueve KazLauncher.exe a una carpeta con permisos (p. ej. Documentos).'))
            return
        dest_path = os.path.join(exe_dir, 'KazLauncher_new.exe')
        try:
            if os.path.isfile(dest_path):
                os.remove(dest_path)
        except OSError:
            pass
        self._update_download_worker = updater.UpdateDownloadWorker(url, dest_path, info.get('sha256') or '', self)
        self._update_download_worker.progress.connect(self._on_update_download_progress)
        self._update_download_worker.status.connect(self._on_update_download_status)
        self._update_download_worker.finished_download.connect(self._on_update_download_finished)
        self._update_download_worker.start()
    def _on_update_download_progress(self, value: int):
        dialog = getattr(self, '_update_dialog', None)
        if dialog and getattr(dialog, 'set_progress', None):
            dialog.set_progress(value)
    def _on_update_download_status(self, message: str):
        dialog = getattr(self, '_update_dialog', None)
        if dialog and getattr(dialog, 'set_status', None):
            if message == 'Verificando integridad...':
                message = self.lang_dict.get('update_verifying', 'Verificando integridad...')
            dialog.set_status(message)
    def _on_update_download_finished(self, ok, dest_path, error):
        if not ok:
            message = self.lang_dict.get('update_download_failed', 'Error al descargar la actualización: {msg}').format(msg=error)
            self._set_update_link_state(False)
            dialog = getattr(self, '_update_dialog', None)
            if dialog and getattr(dialog, 'show_download_failed', None):
                dialog.show_download_failed(message)
            QMessageBox.warning(self, self.lang_dict.get('update_status_title', 'Actualización'), message)
            return
        exe_path = updater.get_launcher_exe_path()
        if not exe_path or not updater.spawn_apply_update(dest_path, exe_path):
            message = self.lang_dict.get('update_apply_failed', 'No se pudo instalar la actualización: {msg}').format(msg='No se pudo lanzar el instalador de la actualización.')
            dialog = getattr(self, '_update_dialog', None)
            if dialog and getattr(dialog, 'show_download_failed', None):
                dialog.show_download_failed(message)
            QMessageBox.warning(self, self.lang_dict.get('update_status_title', 'Actualización'), message)
            return
        QMessageBox.information(self, self.lang_dict.get('update_status_title', 'Actualización'), self.lang_dict.get('update_download_done', 'Actualización lista. El launcher se cerrará y se reabrirá automáticamente.'))
        dialog = getattr(self, '_update_dialog', None)
        if dialog:
            dialog.close()
            self._update_dialog = None
        self._set_update_link_state(False)
        QTimer.singleShot(400, self._quit_after_update)
    def _quit_after_update(self):
        """Cierra la app y, si algo la retiene, la fuerza a salir a los 5 s."""
        app = QApplication.instance()
        if app:
            app.quit()
        # Respaldo independiente del event loop de Qt: si algún hilo bloquea la
        # salida, se fuerza la terminación para que el finalizador pueda reemplazar
        # el exe (los procesos que retengan el archivo se cierran igualmente).
        import threading
        threading.Timer(5.0, lambda: os._exit(0)).start()
    def on_theme_style_changed(self, index: int):
        if index < 0:
            return None
        else:
            theme_key = self.theme_style_combo.itemData(index)
            if not theme_key or theme_key == getattr(self, 'current_theme', None):
                return None
            self.current_theme = theme_key
            self.settings['theme'] = theme_key
            settings.save_settings(self.settings)
            self.apply_theme()
            self._update_glass_extras_visibility()
    def _update_glass_extras_visibility(self):
        if hasattr(self, 'glass_extras_btn'):
            self.glass_extras_btn.setVisible(getattr(self, 'current_theme', 'default') == 'glass')
    def open_glass_gradient_editor(self):
        from kaz_launcher.ui.dialogs import GlassGradientDialog
        current = self.settings.get('glass_gradient') or ['#1E1B4B', '#312E81', '#0E7490', '#134E4A']
        dialog = GlassGradientDialog(self, self.lang_dict, current)
        if dialog.exec() != QDialog.Accepted:
            return None
        else:
            self.settings['glass_gradient'] = dialog.get_colors()
            settings.save_settings(self.settings)
            self.apply_theme()
    def apply_theme(self):
        glass_opacity = int(self.settings.get('ui_glass_opacity', 88))
        theme_key = getattr(self, 'current_theme', 'default') or 'default'
        secondary = getattr(self, 'current_accent_color_secondary', None) or None
        if theme_key == 'glass':
            base_style = themes.get_glassmorphism_theme(accent_color=self.current_accent_color, glass_opacity=glass_opacity, gradient_colors=self.settings.get('glass_gradient'), secondary_accent=secondary)
        else:
            if theme_key == 'skeumorph':
                base_style = themes.get_skeuomorphism_dark_theme(accent_color=self.current_accent_color, glass_opacity=glass_opacity, secondary_accent=secondary)
            else:
                base_style = themes.get_dark_theme(accent_color=self.current_accent_color, glass_opacity=glass_opacity, secondary_accent=secondary)
        custom_style = '\n            QPushButton {\n                outline: none;\n            }\n            QTabBar::tab:nth-last-child(1), QTabBar::tab:nth-last-child(2) {\n                width: 60px;\n                padding: 10px 15px;\n            }\n            #cancelButton {\n                background-color: rgba(255, 85, 85, 0.88);\n                color: #fff;\n                border: 1px solid rgba(255, 120, 120, 0.35);\n            }\n            #cancelButton:hover {\n                background-color: rgba(255, 112, 112, 0.95);\n            }\n            #deleteSelectedButton {\n                background-color: rgba(255, 85, 85, 0.88);\n                padding: 5px 10px;\n                border-radius: 8px;\n            }\n            #deleteSelectedButton:hover {\n                background-color: rgba(255, 112, 112, 0.95);\n            }\n            #deleteSelectedButton:disabled {\n                background-color: rgba(80, 80, 90, 0.5);\n                color: #888;\n            }\n            #logoutAccountButton {\n                background-color: transparent;\n                color: #ff6b6b;\n                border: 1px solid rgba(255, 107, 107, 0.45);\n                border-radius: 13px;\n                font-size: 11px;\n                font-weight: bold;\n                padding: 0;\n            }\n            #logoutAccountButton:hover {\n                background-color: rgba(255, 107, 107, 0.15);\n                color: #ff8a8a;\n            }\n            #installStatusLabel {\n                color: #f8b339;\n                font-weight: bold;\n                padding: 6px 10px;\n                background-color: rgba(248, 179, 57, 0.08);\n                border: 1px solid rgba(248, 179, 57, 0.3);\n                border-radius: 8px;\n            }\n        '
        full_style = base_style + custom_style
        self.setStyleSheet(full_style)
        # El viewport del QScrollArea de Configuración lleva un stylesheet propio
        # (fondo transparente) que anula el tema en todos sus descendientes.
        # Aplicar el tema también al contenedor interior restaura el estilo de
        # los controles (botones con el color de acento del tema, etc.).
        if hasattr(self, 'settings_tab_widget'):
            self.settings_tab_widget.setStyleSheet(full_style)
        self._apply_window_shadows()
        self.update_title_glow()
    def _apply_window_shadows(self):
        if not hasattr(self, '_container_shadow'):
            self._container_shadow = QGraphicsDropShadowEffect(self.container)
            self._container_shadow.setBlurRadius(56)
            self._container_shadow.setOffset(0, 14)
            self._container_shadow.setColor(QColor(0, 0, 0, 110))
            self.container.setGraphicsEffect(self._container_shadow)
        self.glow_effect.setBlurRadius(32)
        self.glow_effect.setOffset(0, 2)
    def _get_version_combo_selection(self):
        data = self.version_combo.currentData(Qt.UserRole) if hasattr(self, 'version_combo') else None
        if isinstance(data, dict) and data.get('version_id'):
            return (data['version_id'], data.get('instance_dir') or self.minecraft_directory)
        else:
            if isinstance(data, str) and data:
                return (data, self.selected_instance_dir or self.minecraft_directory)
            else:
                return (None, self.minecraft_directory)
    def _scan_remote_instances(self):
        return scan_remote_instances(self.minecraft_directory)
    def _set_version_type_controls_visible(self, visible: bool):
        for widget in [getattr(self, 'version_type_label', None), getattr(self, 'vanilla_radio', None), getattr(self, 'forge_radio', None), getattr(self, 'fabric_radio', None)]:
            if widget is not None:
                widget.setVisible(visible)
    def _set_installing_state(self, installing: bool, text: str = ''):
        self._installing = installing
        if hasattr(self, 'install_status_label'):
            self.install_status_label.setText(text)
            self.install_status_label.setVisible(installing and bool(text))
        if hasattr(self, 'launch_button'):
            self.launch_button.setEnabled(not installing)
            if installing:
                self._install_anim_frame = 0
                base = self.lang_dict.get('installing_modpack_btn', 'Instalando')
                self.launch_button.setText(base)
                self.launch_button.setIcon(QIcon())
                if not self._install_anim_timer.isActive():
                    self._install_anim_timer.start()
            else:
                if self._install_anim_timer.isActive():
                    self._install_anim_timer.stop()
                self.launch_button.setText(self.lang_dict.get('launch', 'JUGAR'))
                self.launch_button.setIcon(self.play_icon)
    def _tick_install_anim(self):
        if not getattr(self, '_installing', False):
            if self._install_anim_timer.isActive():
                self._install_anim_timer.stop()
            return
        self._install_anim_frame = (self._install_anim_frame + 1) % 4
        base = self.lang_dict.get('installing_modpack_btn', 'Instalando')
        dots = '.' * self._install_anim_frame
        if hasattr(self, 'launch_button'):
            self.launch_button.setText(f'{base}{dots}')
        if hasattr(self, 'install_status_label') and self.install_status_label.isVisible():
            current = self.install_status_label.text().rstrip('.')
            self.install_status_label.setText(f'{current}{dots}')
    def _apply_version_combo_selection(self, index: int):
        if index < 0:
            return
        else:
            data = self.version_combo.itemData(index)
            if not isinstance(data, dict) or not data.get('version_id'):
                return None
            else:
                self.selected_instance_dir = data.get('instance_dir', '')
                self.settings['selected_instance_dir'] = self.selected_instance_dir
                self.settings['last_version'] = data['version_id']
                self.current_version_type = data.get('loader', self.current_version_type)
                if self.selected_instance_dir:
                    self.installed_mods_path = os.path.join(self.selected_instance_dir, 'installed_mods.json')
                type_map = {'vanilla': 0, 'forge': 1, 'fabric': 2, 'neoforge': 1}
                btn = self.version_type_group.button(type_map.get(self.current_version_type, 1))
                if btn:
                    self.version_type_group.blockSignals(True)
                    btn.setChecked(True)
                    self.version_type_group.blockSignals(False)
                self._update_remote_verify_button()
    def on_launch_version_combo_changed(self, index: int):
        if self._refreshing_version_combo or index < 0:
            return None
        else:
            self._apply_version_combo_selection(index)
    def _populate_instance_version_combo(self, select_instance_dir=None):
        lang = self.lang_dict
        instances = self._scan_remote_instances()
        self._refreshing_version_combo = True
        self.version_combo.clear()
        if not instances:
            self.version_combo.addItem(lang.get('no_instances_hint', 'Haz una nueva instalación para comenzar a jugar'), None)
            self.version_combo.setEnabled(False)
            self._set_version_type_controls_visible(True)
            self._refreshing_version_combo = False
            return
        else:
            self._set_version_type_controls_visible(False)
            self.version_combo.setEnabled(True)
            select_index = 0
            preferred = select_instance_dir or self.settings.get('selected_instance_dir', '')
            for i, inst in enumerate(instances):
                label = lang.get('remote_instance_label', '{name}').format(name=inst['name'])
                payload = {'version_id': inst['version_id'], 'instance_dir': inst['instance_dir'], 'loader': inst.get('loader', 'forge')}
                self.version_combo.addItem(self.installed_icon, label, payload)
                if preferred and os.path.normcase(inst['instance_dir']) == os.path.normcase(preferred):
                        select_index = i
            self.version_combo.setCurrentIndex(select_index)
            self._refreshing_version_combo = False
            self._apply_version_combo_selection(select_index)
    def populate_versions(self, version_type='vanilla'):
        instances = self._scan_remote_instances()
        if instances:
            select_dir = getattr(self, '_select_instance_on_refresh', None) or self.settings.get('selected_instance_dir')
            self._populate_instance_version_combo(select_dir)
            self._select_instance_on_refresh = None
            return
        else:
            self._set_version_type_controls_visible(True)
            if self.version_loader and self.version_loader.isRunning():
                    self.version_loader.quit()
                    self.version_loader.wait()
            self.version_combo.clear()
            self.version_combo.setEnabled(False)
            self.version_combo.addItem(self.lang_dict.get('no_instances_hint', 'Haz una nueva instalación para comenzar a jugar'))
    def on_versions_loaded(self, version_list):
        self.mod_results_list.clear()
        self.mod_search_input.clear()
        self.version_combo.clear()
        effective_dir = self.selected_instance_dir if self.selected_instance_dir and os.path.isdir(self.selected_instance_dir) else self.minecraft_directory
        installed_ids = {v['id'] for v in minecraft_launcher_lib.utils.get_installed_versions(effective_dir)}
        model = QStandardItemModel(self)
        for version_id in version_list:
            display_text = version_id
            if self.current_version_type in ['forge', 'fabric']:
                display_text = helpers.get_base_version(version_id)
            item = QStandardItem(display_text)
            item.setData(version_id, Qt.UserRole)
            is_installed = False
            if self.current_version_type == 'forge':
                mc_ver, forge_ver_build = version_id.split('-', 1)
                for installed_id in installed_ids:
                    if 'forge' in installed_id and installed_id.startswith(mc_ver) and installed_id.endswith(forge_ver_build):
                                is_installed = True
                                break
            else:
                if self.current_version_type == 'fabric':
                    for installed_id in installed_ids:
                        if 'fabric-loader' in installed_id and version_id in installed_id:
                                is_installed = True
                                break
                else:
                    is_installed = version_id in installed_ids
            if is_installed:
                item.setIcon(self.installed_icon)
            else:
                item.setData(QColor('#888888'), Qt.ForegroundRole)
            model.appendRow(item)
        self.version_combo.setModel(model)
        last_version = self.settings.get('last_version')
        if last_version:
            for i in range(model.rowCount()):
                if model.item(i).data(Qt.UserRole) == last_version:
                    self.version_combo.setCurrentIndex(i)
                    break
        self.version_combo.setEnabled(True)
    def on_version_load_error(self, error_msg):
        self.version_combo.clear()
        self.version_combo.addItem('Error loading versions')
        self.error_label.setText(f'Failed to load version list: {error_msg}')
        self.error_label.setVisible(True)
        self.log_to_console(f'Failed to load version list: {error_msg}')
    def on_tab_changed(self, index):
        current_widget = self.tab_widget.widget(index)
        if current_widget == self.mods_tab_widget:
            self.on_mods_sub_tab_changed(self.mods_sub_tabs.currentIndex())
        else:
            if current_widget == self.versions_tab_widget:
                self.refresh_installed_versions_list()
    def on_mods_sub_tab_changed(self, index):
        if index == 0:
            if self.mod_results_list.count() == 0:
                self.mod_search_input.clear()
                self.update_mod_list()
        else:
            if index == 1:
                self.refresh_installed_mods()
    def start_mod_download(self, mod_data):
        project_id = mod_data.get('project_id')
        if project_id in self.mod_download_workers and self.mod_download_workers[project_id].isRunning():
            return
        else:
            game_version_full, effective_dir = self._get_version_combo_selection()
            if not game_version_full:
                self.log_to_console('Error: no game version selected.')
                return
            else:
                game_version = helpers.get_base_version(game_version_full)
                self.selected_instance_dir = effective_dir
                loader = self.current_version_type
                worker = ModDownloadWorker(project_id, game_version, loader, effective_dir, self.lang_dict, self)
                worker.progress.connect(self.on_mod_download_progress)
                worker.finished.connect(self.on_mod_download_finished)
                worker.mod_info_signal.connect(self.add_installed_mod_info)
                worker.finished.connect(worker.deleteLater)
                self.mod_download_workers[project_id] = worker
                worker.start()
    def install_mod_dependency(self, dependency_name):
        mods_tab_index = self.tab_widget.indexOf(self.mods_tab_widget)
        if mods_tab_index != (-1):
            self.tab_widget.setCurrentIndex(mods_tab_index)
        self.mods_sub_tabs.setCurrentIndex(0)
        self.mod_search_input.setText(dependency_name)
        self.update_mod_list(reset_page=True)
        self.log_to_console(f'Automatically searching for dependency: {dependency_name}')
    def on_mod_download_progress(self, project_id, percentage):
        if project_id in self.mod_list_item_map:
            card_widget = self.mod_list_item_map[project_id]
            if percentage > 100:
                card_widget.update_view(is_installing=False)
            else:
                card_widget.update_view(is_installing=True, progress=percentage)
    def on_mod_download_finished(self, project_id, success, message):
        self.log_to_console(message)
        if project_id in self.mod_download_workers:
            del self.mod_download_workers[project_id]
        if project_id in self.mod_list_item_map:
            card_widget = self.mod_list_item_map[project_id]
            if success:
                card_widget.is_installed = True
            card_widget.update_view()
    def open_mod_page(self, mod_data):
        project_slug = mod_data.get('slug')
        if project_slug:
            url = QUrl(f'https://modrinth.com/mod/{project_slug}')
            QDesktopServices.openUrl(url)
    def get_installed_mods_info(self):
        try:
            if self.installed_mods_path and os.path.exists(self.installed_mods_path):
                with open(self.installed_mods_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            self.log_to_console(f'Error reading installed_mods.json: {e}')
        return {}
    def add_installed_mod_info(self, project_id, file_info):
        installed = self.get_installed_mods_info()
        installed[project_id] = file_info
        try:
            with open(self.installed_mods_path, 'w', encoding='utf-8') as f:
                json.dump(installed, f, indent=4)
        except IOError as e:
            self.log_to_console(f'Error saving the list of installed mods: {e}')
    def remove_installed_mod_info(self, project_id):
        installed = self.get_installed_mods_info()
        if project_id in installed:
            del installed[project_id]
            try:
                with open(self.installed_mods_path, 'w', encoding='utf-8') as f:
                    json.dump(installed, f, indent=4)
            except IOError as e:
                self.log_to_console(f'Error saving the list of installed mods: {e}')
    def delete_mod(self, mod_data):
        project_id = mod_data.get('project_id')
        installed_mods = self.get_installed_mods_info()
        if project_id in installed_mods:
            file_name = installed_mods[project_id].get('filename')
            if file_name:
                effective_dir = self.selected_instance_dir if self.selected_instance_dir and os.path.isdir(self.selected_instance_dir) else self.minecraft_directory
                file_path = os.path.join(effective_dir, 'mods', file_name)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        self.log_to_console(f'Error deleting file {file_name}: {e}')
            self.remove_installed_mod_info(project_id)
            if project_id in self.mod_list_item_map:
                card_widget = self.mod_list_item_map[project_id]
                card_widget.is_installed = False
                card_widget.update_view()
    def reinstall_version(self, version_id, instance_dir=None):
        effective_dir = instance_dir or (self.selected_instance_dir if self.selected_instance_dir and os.path.isdir(self.selected_instance_dir) else self.minecraft_directory)
        version_path = os.path.join(effective_dir, 'versions', version_id)
        self.log_to_console(f'Attempting to reinstall version {version_id}. Path: {version_path}')
        if os.path.exists(version_path):
            try:
                shutil.rmtree(version_path)
                self.log_to_console(f'Version folder \'{version_id}\' successfully deleted.')
                self.populate_versions(self.current_version_type)
            except Exception as e:
                self.log_to_console(f'Could not delete version folder: {e}')
                QMessageBox.critical(self, 'Error', f'Could not delete folder \'{version_path}\'.\nCheck if the game is running or delete it manually.', QMessageBox.Ok)
        else:
            self.log_to_console(f'Version folder \'{version_id}\' not found for deletion.')
        if self.tab_widget.currentWidget() == self.versions_tab_widget:
            self.refresh_installed_versions_list()
    def log_to_console(self, message):
        self.console_output.append(message)
        logging.info(f'CONSOLE: {message}')
    def clear_console(self):
        self.console_output.clear()
    def update_memory_feedback(self, value):
        self.memory_value_label.setText(f'{value} GB')
        lang = self.lang_dict
        if value <= 1:
            text, color = (lang['mem_feedback_risky'], '#E23D28')
        else:
            if value <= 3:
                text, color = (lang['mem_feedback_low'], '#F8B339')
            else:
                if value <= 6:
                    text, color = (lang['mem_feedback_optimal'], self.current_accent_color)
                else:
                    if value <= 8:
                        text, color = (lang['mem_feedback_good'], self.current_accent_color)
                    else:
                        text, color = (lang['mem_feedback_excessive'], '#F8B339')
        self.memory_feedback_label.setText(text)
        self.memory_feedback_label.setStyleSheet(f'color: {color}; font-weight: bold;')
    def open_advanced_settings(self):
        dialog = AdvancedSettingsDialog(self)
        dialog.exec()
    def _on_username_changed(self):
        if self.account_mode == 'offline':
            self._refresh_account_selector()
        self._update_login_status_label()
    def _find_premium_account(self, account_id: str):
        return find_account(self.settings, account_id)
    def _sync_account_state_from_settings(self):
        self.premium_accounts = list(self.settings.get('premium_accounts') or [])
        self.selected_account_id = self.settings.get('selected_account_id', '')
        self.account_mode = self.settings.get('account_mode', 'offline')
        self.premium_session = self.settings.get('premium_session') or {}
        self.offline_mode = self.account_mode == 'offline'
    def _refresh_account_selector(self):
        if not hasattr(self, 'account_combo'):
            return
        else:
            lang = self.lang_dict
            self._refreshing_account_combo = True
            self.account_combo.clear()
            offline_name = self.user_input.text().strip() or self.settings.get('last_username', '') or 'Player'
            self.account_combo.addItem(lang.get('account_offline_option', 'Offline — {name}').format(name=offline_name), 'offline')
            for acc in self.premium_accounts:
                name = acc.get('name') or 'Microsoft'
                self.account_combo.addItem(lang.get('account_online_option', 'Microsoft — {name}').format(name=name), acc.get('id', ''))
            self.account_combo.addItem(lang.get('account_add_new', '+ Añadir cuenta Microsoft'), 'add')
            target_index = 0
            if self.account_mode == 'online' and self.selected_account_id:
                    for i in range(self.account_combo.count()):
                        if self.account_combo.itemData(i) == self.selected_account_id:
                            target_index = i
                            break
            self.account_combo.setCurrentIndex(target_index)
            self._refreshing_account_combo = False
    def _update_login_status_label(self):
        lang = self.lang_dict
        status = lang.get('login_status_none', 'Sin cuenta seleccionada')
        show_logout = False
        if self.account_mode == 'offline':
            name = self.user_input.text().strip() or self.settings.get('last_username', '') or 'Player'
            status = lang.get('login_status_offline', '{name} (offline)').format(name=name)
        else:
            session = self._find_premium_account(self.selected_account_id) or self.premium_session
            if session and session.get('name'):
                    status = lang.get('login_status_premium', '{name}').format(name=session.get('name'))
                    show_logout = True
        if hasattr(self, 'login_status_label'):
            self.login_status_label.setText(lang.get('login_status_label', '{status}').format(status=status))
        if hasattr(self, 'logout_account_btn'):
            self.logout_account_btn.setVisible(show_logout)
    def on_account_combo_changed(self, index: int):
        if self._refreshing_account_combo or index < 0:
            return None
        else:
            data = self.account_combo.itemData(index)
            if data == 'offline':
                self.use_offline_account()
            else:
                if data == 'add':
                    self.start_premium_login()
                else:
                    if data:
                        self.use_online_account(data)
    def use_offline_account(self):
        set_account_mode(self.settings, 'offline')
        settings.save_settings(self.settings)
        self._sync_account_state_from_settings()
        self._refresh_account_selector()
        self._update_login_status_label()
    def use_online_account(self, account_id: str | None=None):
        account_id = account_id or self.selected_account_id
        account = self._find_premium_account(account_id)
        if not account:
            if self.premium_accounts:
                account_id = self.premium_accounts[0].get('id', '')
                account = self.premium_accounts[0]
            else:
                self.start_premium_login()
                return
        set_account_mode(self.settings, 'online', account_id)
        settings.save_settings(self.settings)
        self._sync_account_state_from_settings()
        self._apply_premium_session(account)
        self._refresh_account_selector()
        self._update_login_status_label()
    def logout_current_premium_account(self):
        if self.account_mode != 'online' or not self.selected_account_id:
            return None
        else:
            account = self._find_premium_account(self.selected_account_id)
            if not account:
                return
            else:
                name = account.get('name', 'Microsoft')
                confirm = QMessageBox.question(self, self.lang_dict.get('logout_account', 'Cerrar sesión'), self.lang_dict.get('logout_account_confirm', '¿Cerrar sesión y quitar la cuenta {name}?').format(name=name), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if confirm != QMessageBox.Yes:
                    return
                else:
                    remove_account(self.settings, self.selected_account_id)
                    settings.save_settings(self.settings)
                    self._sync_account_state_from_settings()
                    self._refresh_account_selector()
                    self._update_login_status_label()
                    self.log_to_console(f'Cuenta Microsoft eliminada: {name}')
    def _get_auth_port(self):
        preferred_port = 8080
        for port in [preferred_port] + list(range(8081, 8090)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('localhost', port))
                sock.close()
                return port
            except OSError:
                sock.close()
            else:
                pass
        raise OSError('No hay puertos disponibles (8080-8089)')
    def _pkce_pair(self):
        ver = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(ver.encode('ascii')).digest()).decode('ascii').rstrip('=')
        return (ver, challenge)
    def _build_auth_url(self, client_id, redirect_uri, code_challenge, state):
        params = {'client_id': client_id, 'response_type': 'code', 'redirect_uri': redirect_uri, 'response_mode': 'query', 'scope': 'XboxLive.signin offline_access', 'state': state, 'prompt': 'select_account', 'code_challenge': code_challenge, 'code_challenge_method': 'S256'}
        return urllib.parse.urlunparse(('https', 'login.microsoftonline.com', '/consumers/oauth2/v2.0/authorize', '', urllib.parse.urlencode(params), ''))
    def start_premium_login(self):
        if getattr(self, 'premium_token_worker', None) and self.premium_token_worker.isRunning():
            return
        self._login_restore = {'account_mode': self.account_mode, 'selected_account_id': self.selected_account_id}
        self.log_to_console(self.lang_dict.get('premium_login_start', 'Iniciando sesión premium...'))
        if not webengine_available() or PremiumLoginDialog is None:
            self.log_to_console(self.lang_dict.get('premium_webengine_missing', 'Falta el componente de navegador del launcher.'))
            self._start_external_browser_login()
            return
        try:
            port = self._get_auth_port()
        except OSError as e:
            QMessageBox.warning(self, 'Premium', str(e))
            return
        redirect_uri = f'http://localhost:{port}/callback'
        state = secrets.token_urlsafe(16)
        code_verifier, code_challenge = self._pkce_pair()
        auth_url = self._build_auth_url(PREMIUM_CLIENT_ID, redirect_uri, code_challenge, state)
        try:
            dialog = PremiumLoginDialog(auth_url, redirect_uri, self.lang_dict, self)
            result = dialog.exec()
        except Exception as exc:
            logging.warning('Fallo el diálogo de login interno (%s); usando navegador externo.', exc)
            self._start_external_browser_login(auth_url, redirect_uri, state, code_verifier)
            return
        if result != QDialog.DialogCode.Accepted:
            error = dialog.auth_error or 'cancelled'
            if error == 'external_fallback':
                self._start_external_browser_login(auth_url, redirect_uri, state, code_verifier)
                return
            self._revert_failed_premium_login(error)
            if error != 'cancelled':
                QMessageBox.warning(self, 'Premium', self._format_premium_login_error(error))
            return
        self._complete_premium_auth(redirect_uri, dialog.auth_code, state, dialog.auth_state, code_verifier)
    def _start_external_browser_login(self, auth_url=None, redirect_uri=None, state=None, code_verifier=None):
        """Flujo sin QtWebEngine: abre el navegador del sistema y el usuario pega la URL final.
        Es el plan B cuando el WebView interno no está disponible o falla (crash en algunas PCs).
        """
        port = None
        if auth_url is None:
            try:
                port = self._get_auth_port()
            except OSError as e:
                QMessageBox.warning(self, 'Premium', str(e))
                return
            redirect_uri = f'http://localhost:{port}/callback'
            state = secrets.token_urlsafe(16)
            code_verifier, code_challenge = self._pkce_pair()
            auth_url = self._build_auth_url(PREMIUM_CLIENT_ID, redirect_uri, code_challenge, state)
        if port is not None:
            try:
                start_oauth_callback_server(port)
            except Exception as exc:
                logging.warning('No se pudo levantar el servidor OAuth local: %s', exc)
        try:
            webbrowser.open(auth_url)
        except Exception as exc:
            logging.warning('No se pudo abrir el navegador externo: %s', exc)
        QMessageBox.information(self, self.lang_dict.get('premium_paste_url_title', 'Completar inicio de sesión'), self.lang_dict.get('premium_browser_opened', 'Se abrió tu navegador. Inicia sesión con Microsoft y, al terminar, copia la URL de la barra de direcciones y pégala aquí.'))
        pasted, ok = QInputDialog.getText(self, self.lang_dict.get('premium_paste_url_title', 'Completar inicio de sesión'), self.lang_dict.get('premium_paste_url_prompt', 'Pega la URL a la que te redirigió Microsoft y pulsa Aceptar.'))
        if not ok or not (pasted or '').strip():
            self._revert_failed_premium_login('cancelled')
            return
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(pasted.strip()).query)
        code = qs.get('code', [None])[0]
        received_state = qs.get('state', [None])[0]
        error = qs.get('error', [None])[0]
        if error or not code:
            self._revert_failed_premium_login(error or 'cancelled')
            QMessageBox.warning(self, 'Premium', self._format_premium_login_error(error or 'cancelled'))
            return
        self._complete_premium_auth(redirect_uri, code, state, received_state or '', code_verifier)
    def _complete_premium_auth(self, redirect_uri, code, state, received_state, code_verifier):
        self.log_to_console('Completando autenticación...')
        self.premium_token_worker = PremiumTokenWorker(PREMIUM_CLIENT_ID, redirect_uri, code, state, received_state, code_verifier, self)
        self.premium_token_worker.finished.connect(self._on_premium_login_finished)
        self.premium_token_worker.start()
    def _revert_failed_premium_login(self, error: str=''):
        """Tras un login fallido, no dejar la UI en modo \'sesión iniciada\'."""
        set_account_mode(self.settings, 'offline')
        settings.save_settings(self.settings)
        self._sync_account_state_from_settings()
        self._refresh_account_selector()
        self._update_login_status_label()
    def _invalidate_stored_premium_account(self, account_id: str):
        if account_id:
            remove_account(self.settings, account_id)
        set_account_mode(self.settings, 'offline')
        settings.save_settings(self.settings)
        self._sync_account_state_from_settings()
        self._refresh_account_selector()
        self._update_login_status_label()
    def _format_premium_login_error(self, error: str) -> str:
        err = str(error or '').strip()
        if '__MINECRAFT_NOT_OWNED__' in err or 'NOT_FOUND' in err:
            return self.lang_dict.get('premium_no_minecraft', 'Esta cuenta de Microsoft no tiene Minecraft: Java Edition vinculado.')
        else:
            if err == 'cancelled':
                return self.lang_dict.get('premium_login_cancelled', 'Inicio de sesión cancelado.')
            else:
                if err == 'state_mismatch':
                    return 'La sesión de login no coincide. Vuelve a intentar.'
                else:
                    if 'redirect_uri' in err:
                        return err
                    else:
                        return err or self.lang_dict.get('premium_login_failed', 'No se pudo iniciar sesión.')
    def _on_premium_login_finished(self, success, profile, error):
        if not success:
            self.log_to_console(self.lang_dict.get('premium_login_failed', 'No se pudo iniciar sesión premium.'))
            self._revert_failed_premium_login(error)
            message = self._format_premium_login_error(error)
            if 'redirect_uri' in str(message):
                message = f'{message}\n\nRegistra exactamente este redirect URI en tu app de Azure:\nhttp://localhost:8080/callback'
            QMessageBox.critical(self, 'Premium', message)
            return
        else:
            upsert_account(self.settings, profile)
            settings.save_settings(self.settings)
            self._sync_account_state_from_settings()
            active = self._find_premium_account(self.selected_account_id)
            if active:
                self._apply_premium_session(active)
            self._refresh_account_selector()
            self._update_login_status_label()
            self.log_to_console('Login exitoso')
            self.log_to_console(self.lang_dict.get('premium_login_ok', 'Cuenta Microsoft añadida correctamente.'))
    def _apply_premium_session(self, session):
        name = session.get('name')
        if name and hasattr(self, 'user_input'):
                self.user_input.setText(name)
                self.settings['last_username'] = name
        self._update_login_status_label()
    def _get_premium_auth(self):
        if self.account_mode == 'offline':
            return
        else:
            session = self._find_premium_account(self.selected_account_id) or self.premium_session
            if not session or not session.get('refresh_token'):
                return None
            else:
                try:
                    profile = refresh_minecraft_profile(PREMIUM_CLIENT_ID, session['refresh_token'])
                    updated = {'id': profile.get('id'), 'name': profile.get('name'), 'access_token': profile.get('access_token'), 'refresh_token': profile.get('refresh_token', session['refresh_token'])}
                    upsert_account(self.settings, updated)
                    settings.save_settings(self.settings)
                    self._sync_account_state_from_settings()
                    self._apply_premium_session(updated)
                    return updated
                except InvalidRefreshToken:
                    self._invalidate_stored_premium_account(session.get('id', ''))
                    return
                except Exception as e:
                    if is_minecraft_profile_error(str(e)):
                        self._invalidate_stored_premium_account(session.get('id', ''))
                    return None
    def on_version_sizes_scanned(self, sizes, total_size):
        total_size_str = helpers.format_size(total_size)
        total_label_text = self.lang_dict.get('total_versions_size', 'Total size: {size}').format(size=total_size_str)
        self.total_versions_size_label.setText(total_label_text)
        for key, widget in self.version_widget_map.items():
            instance_dir = key[0] if isinstance(key, tuple) else self.selected_instance_dir
            widget.update_size(sizes.get(instance_dir, 0))
    def refresh_installed_versions_list(self):
        self.installed_versions_list.clear()
        self.grouped_versions.clear()
        self.version_widget_map.clear()
        self.selected_versions_for_deletion.clear()
        self._versions_selected_instance_dir = ''
        self._versions_selected_source = ''
        self.update_delete_button_state()
        self.total_versions_size_label.setText(self.lang_dict.get('calculating_size', 'Calculating size...'))
        try:
            instances = []
            try:
                base_installed = minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_directory)
            except Exception:
                base_installed = []
            if base_installed:
                instances.append({'name': self.lang_dict.get('base_instance_name', 'Base'), 'instance_dir': self.minecraft_directory, 'source': ''})
            for inst in self._scan_remote_instances():
                instances.append({'name': inst.get('name') or os.path.basename(inst['instance_dir'].rstrip('\\/')), 'instance_dir': inst['instance_dir'], 'source': inst.get('source', 'remote')})
            if not instances:
                item = QListWidgetItem(self.lang_dict.get('no_versions_installed', 'No versions installed.'))
                item.setTextAlignment(Qt.AlignCenter)
                self.installed_versions_list.addItem(item)
                self.total_versions_size_label.setText('')
                self._update_remote_verify_button()
                return
            all_instance_dirs = []
            for inst in instances:
                instance_dir = inst['instance_dir']
                all_instance_dirs.append(instance_dir)
                try:
                    installed = minecraft_launcher_lib.utils.get_installed_versions(instance_dir)
                except Exception:
                    installed = []
                if not installed:
                    continue
                instance_name = inst.get('name') or os.path.basename(instance_dir.rstrip('\\/'))
                source = inst.get('source', '')
                can_rename = source in ('manual', 'mrpack') or not source
                by_base = {}
                for version_info in installed:
                    version_id = version_info['id']
                    base_v = helpers.get_base_version(version_id)
                    by_base.setdefault(base_v, []).append(version_id)
                for base_version, id_list in sorted(by_base.items(), key=lambda item: helpers.version_key(item[0]), reverse=True):
                    key = (instance_dir, base_version)
                    self.grouped_versions[key] = id_list
                    version_types = sorted(list(set((helpers.get_version_type(vid) for vid in id_list))))
                    item = QListWidgetItem()
                    item.setSizeHint(QSize(0, 85))
                    item.setData(Qt.UserRole, {'instance_dir': instance_dir, 'source': source, 'base_version': base_version})
                    display_name = f'{base_version} — {instance_name}'
                    widget = VersionListItemWidget(display_name, version_types, self.version_management_icons, self.lang_dict, can_rename=can_rename)
                    widget.delete_requested.connect(partial(self.handle_version_action, 'delete', base_version, instance_dir))
                    widget.repair_requested.connect(partial(self.handle_version_action, 'repair', base_version, instance_dir))
                    widget.open_folder_requested.connect(partial(self.handle_version_action, 'open_folder', base_version, instance_dir))
                    widget.rename_requested.connect(partial(self.handle_rename_instance, base_version, instance_dir))
                    widget.selection_changed.connect(partial(self.on_version_selection_changed, instance_dir))
                    self.installed_versions_list.addItem(item)
                    self.installed_versions_list.setItemWidget(item, widget)
                    self.version_widget_map[key] = widget
            if self.version_size_scanner and self.version_size_scanner.isRunning():
                self.version_size_scanner.requestInterruption()
                self.version_size_scanner.wait()
            self.version_size_scanner = VersionSizeScannerWorker(all_instance_dirs, self)
            self.version_size_scanner.finished.connect(self.on_version_sizes_scanned)
            self.version_size_scanner.start()
            if self.installed_versions_list.count():
                self.installed_versions_list.setCurrentRow(0)
            self._update_remote_verify_button()
        except Exception as e:
            self.log_to_console(f'Error scanning for installed versions: {e}')
            logging.error(f'Error scanning for installed versions: {traceback.format_exc()}')
            item = QListWidgetItem(self.lang_dict.get('error_scanning_versions', 'Error during scan.'))
            item.setTextAlignment(Qt.AlignCenter)
            self.installed_versions_list.addItem(item)
            self.total_versions_size_label.setText('')
            return None
    def handle_version_action(self, action_type, base_version, instance_dir=None, *args):
        if action_type == 'open_folder':
            effective_dir = instance_dir or (self.selected_instance_dir if self.selected_instance_dir and os.path.isdir(self.selected_instance_dir) else self.minecraft_directory)
            if os.path.exists(effective_dir):
                QDesktopServices.openUrl(QUrl.fromLocalFile(effective_dir))
            else:
                QMessageBox.warning(self, 'Error', f'Folder for instance \'{effective_dir}\' not found.')
        else:
            if action_type == 'delete':
                effective_dir = instance_dir or (self.selected_instance_dir if self.selected_instance_dir and os.path.isdir(self.selected_instance_dir) else self.minecraft_directory)
                instance_name = os.path.basename(effective_dir.rstrip('\\/'))
                confirm_title = self.lang_dict.get('confirm_delete_title', 'Confirmar Eliminación')
                confirm_text = self.lang_dict.get('confirm_multi_delete_text', '¿Estás seguro de que quieres eliminar las siguientes {count} versiones?\n\n - {versions}').format(count=1, versions=instance_name)
                reply = QMessageBox.question(self, confirm_title, confirm_text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    try:
                        if os.path.isdir(effective_dir):
                            shutil.rmtree(effective_dir)
                        if self.selected_instance_dir and os.path.normcase(self.selected_instance_dir) == os.path.normcase(effective_dir):
                            self.selected_instance_dir = ''
                            self.settings['selected_instance_dir'] = ''
                            settings.save_settings(self.settings)
                            self.installed_mods_path = os.path.join(self.minecraft_directory, 'installed_mods.json')
                        self.refresh_installed_versions_list()
                        self.populate_versions(self.current_version_type)
                        self.log_to_console(f'Instance \'{instance_name}\' deleted.')
                    except Exception as e:
                        QMessageBox.critical(self, 'Error', f'Couldn\'t delete instance folder:\n{e}')
                        return
            else:
                versions_in_group = self.grouped_versions.get((instance_dir, base_version), [])
                version_to_act_on = None
                if len(versions_in_group) == 1:
                    version_to_act_on = versions_in_group[0]
                else:
                    if len(versions_in_group) > 1:
                        title = self.lang_dict.get('select_version_dialog_title', 'Select Version')
                        prompt = self.lang_dict.get('select_version_prompt', 'Select which version for \'{base_version}\' to {action}:').format(base_version=base_version, action=action_type)
                        action_text = self.lang_dict.get(f'action_button_{action_type}', action_type.title())
                        dialog = VersionSelectionDialog(title, prompt, versions_in_group, action_text, self.lang_dict, self)
                        if dialog.exec() == QDialog.Accepted:
                            version_to_act_on = dialog.get_selected_version()
                if not version_to_act_on:
                    return
                else:
                    if action_type in ['delete', 'repair']:
                        confirm_title = self.lang_dict.get(f'confirm_{action_type}_title', f'Confirm {action_type.title()}')
                        confirm_text = self.lang_dict.get(f'confirm_{action_type}_text', 'Are you sure?').format(version_id=version_to_act_on)
                        reply = QMessageBox.question(self, confirm_title, confirm_text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                        if reply == QMessageBox.Yes:
                            self.reinstall_version(version_to_act_on, instance_dir)
    def handle_rename_instance(self, base_version=None, instance_dir=None, _display_name=None):
        instance_dir = instance_dir or self.selected_instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            QMessageBox.warning(self, 'Error', 'No instance selected.')
            return
        else:
            meta = load_instance_meta(instance_dir)
            old_name = meta.get('name') or os.path.basename(instance_dir.rstrip('\\/'))
            from PySide6.QtWidgets import QInputDialog
            new_name, ok = QInputDialog.getText(self, self.lang_dict.get('rename_instance', 'Rename instance'), self.lang_dict.get('rename_instance_prompt', 'New name:'), text=old_name)
            if not ok or not new_name.strip():
                return None
            else:
                new_name = new_name.strip()
                meta['name'] = new_name
                save_instance_meta(instance_dir, name=new_name, version_id=meta.get('version_id', ''), loader=meta.get('loader', 'forge'), game_version=meta.get('game_version', ''), source=meta.get('source', 'remote'), loader_version=meta.get('loader_version', ''), manifest_url=meta.get('manifest_url', ''), manifest_revision=meta.get('manifest_revision', ''), actualizacion=bool(meta.get('actualizacion')))
                self.log_to_console(self.lang_dict.get('instance_renamed', 'Instance renamed to \'{name}\'.').format(name=new_name))
                self.refresh_installed_versions_list()
                self.populate_versions(self.current_version_type)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.title_bar.underMouse():
                self.old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event):
        self.old_pos = None
    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.mrpack'):
                    event.acceptProposedAction()
                    break
    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.mrpack'):
                self._install_mrpack(file_path)
                break
    def _install_mrpack(self, mrpack_path):
        worker = MrpackInstallWorker(mrpack_path, self.minecraft_directory, self.lang_dict, self)
        worker.progress_status.connect(self.log_to_console)
        worker.finished.connect(self._on_mrpack_install_finished)
        idx = self.tab_widget.indexOf(self.console_output.parentWidget())
        if idx >= 0:
            self.tab_widget.setCurrentIndex(idx)
        self.log_to_console(f'Installing mrpack: {os.path.basename(mrpack_path)}...')
        self._set_installing_state(True, self.lang_dict.get('installing_modpack', 'Instalando modpack...'))
        worker.start()
        self._mrpack_worker = worker
    def _on_mrpack_install_finished(self, success, msg, result):
        self._set_installing_state(False)
        if success:
            self.log_to_console(msg)
            instance_dir = (result or {}).get('instance_dir', '')
            version_id = (result or {}).get('version_id', '')
            loader = (result or {}).get('loader', 'forge')
            if instance_dir and version_id:
                    self.selected_instance_dir = instance_dir
                    self.settings['selected_instance_dir'] = instance_dir
                    self.settings['last_version'] = version_id
                    self.settings['version_type'] = loader
                    self.current_version_type = loader
                    self.installed_mods_path = os.path.join(instance_dir, 'installed_mods.json')
                    settings.save_settings(self.settings)
                    self._select_instance_on_refresh = instance_dir
                    self.populate_versions(self.current_version_type)
            QMessageBox.information(self, 'Mrpack', msg)
        else:
            self.log_to_console(f'Mrpack install error: {msg}')
            QMessageBox.critical(self, 'Mrpack', msg)
    def stop_all_threads(self):
        logging.info('Received command to stop all threads.')
        for worker in list(self.mod_download_workers.values()):
            if worker.isRunning():
                worker.stop()
                worker.quit()
                worker.wait(500)
        self.mod_download_workers.clear()
        if self.worker and self.worker.isRunning():
                self.worker.stop()
        if hasattr(self, '_mrpack_worker') and self._mrpack_worker and self._mrpack_worker.isRunning():
                    self._mrpack_worker.stop()
                    self._mrpack_worker.wait(500)
        worker_list = ['worker', 'java_ensure_worker', 'version_loader', 'mod_search_worker', 'local_mods_scanner', 'version_size_scanner', 'prelaunch_mods_worker']
        for worker_attr in worker_list:
            worker = getattr(self, worker_attr, None)
            if worker and worker.isRunning():
                    worker.quit()
                    worker.wait(500)
        logging.info('All threads stopped.')
    def closeEvent(self, event):
        logging.info('Application closing. Saving settings and stopping threads...')
        self.save_settings()
        self.stop_all_threads()
        try:
            from kaz_launcher.discord_presence import stop_discord_presence
            stop_discord_presence()
        except Exception:
            pass
        event.accept()
    def show(self):
        super().show()
        self.fade_in_animation.start()
    def on_version_selection_changed(self, instance_dir, base_version, is_selected):
        key = (instance_dir, base_version)
        if is_selected:
            self.selected_versions_for_deletion.add(key)
        else:
            self.selected_versions_for_deletion.discard(key)
        self.update_delete_button_state()
    def update_delete_button_state(self):
        is_enabled = len(self.selected_versions_for_deletion) > 0
        if hasattr(self, 'delete_selected_versions_button'):
            self.delete_selected_versions_button.setEnabled(is_enabled)
    def delete_selected_versions(self):
        if not self.selected_versions_for_deletion:
            return
        else:
            versions_to_delete = []
            for key in self.selected_versions_for_deletion:
                versions_to_delete.extend(self.grouped_versions.get(key, []))
            if not versions_to_delete:
                return
            else:
                confirm_title = self.lang_dict.get('confirm_multi_delete_title', 'Confirm Deletion')
                display_list = sorted(versions_to_delete)
                if len(display_list) > 10:
                    display_list = display_list[:10] + ['...']
                versions_list_str = '\n - '.join(display_list)
                confirm_text = self.lang_dict.get('confirm_multi_delete_text', 'Are you sure you want to delete the following {count} versions?\n\n - {versions}').format(count=len(versions_to_delete), versions=versions_list_str)
                reply = QMessageBox.question(self, confirm_title, confirm_text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.log_to_console(f'Starting deletion of {len(versions_to_delete)} selected versions...')
                    for key in sorted(self.selected_versions_for_deletion):
                        instance_dir = key[0]
                        for version_id in self.grouped_versions.get(key, []):
                            self.reinstall_version(version_id, instance_dir)
                    self.log_to_console('Deletion complete.')
                    self.refresh_installed_versions_list()