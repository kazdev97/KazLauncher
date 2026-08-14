import os
import json
import uuid
from kaz_launcher.utils.paths import get_launcher_data_dir
SETTINGS_FILE_PATH = os.path.join(get_launcher_data_dir(), 'launcher_settings.json')
def load_settings():
    """Loads launcher settings from the JSON file."""
    defaults = {'language': 'en', 'memory': 4, 'fullscreen': False, 'close_launcher': False, 'last_username': '', 'version_type': 'vanilla', 'last_version': '', 'accent_color': '#1DB954', 'accent_color_secondary': '#8B5CF6', 'theme': 'default', 'glass_gradient': ['#1E1B4B', '#312E81', '#0E7490', '#134E4A'], 'ui_glass_opacity': 88, 'last_tab': 0, 'window_geometry': '', 'jvm_args': '', 'java_path': '', 'clientToken': uuid.uuid4().hex, 'remote_modpacks_folder': '', 'premium_session': {}, 'premium_accounts': [], 'selected_account_id': '', 'account_mode': 'offline', 'java_opt_enabled': True, 'offline_mode': False}
    if os.path.exists(SETTINGS_FILE_PATH):
        try:
            with open(SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            for key, value in defaults.items():
                if key not in settings:
                    settings[key] = value
            from kaz_launcher.utils.account_store import migrate_account_settings
            return migrate_account_settings(settings)
        except (json.JSONDecodeError, IOError) as e:
            print(f'Error loading settings: {e}. Using defaults.')
            defaults['clientToken'] = uuid.uuid4().hex
            from kaz_launcher.utils.account_store import migrate_account_settings
            return migrate_account_settings(defaults)
    else:
        from kaz_launcher.utils.account_store import migrate_account_settings
        return migrate_account_settings(defaults)
def save_settings(settings_dict):
    """Saves launcher settings to the JSON file."""
    try:
        with open(SETTINGS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings_dict, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f'Error saving settings: {e}')