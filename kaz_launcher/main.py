import os
import sys
import traceback
import logging
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from kaz_launcher.discord_presence import start_discord_presence, stop_discord_presence
from kaz_launcher.utils.robust_download import apply_download_patches
from kaz_launcher.ui.main_window import APP_VERSION, MinecraftLauncher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def global_exception_hook(exctype, value, tb):
    logging.critical('--- GLOBAL EXCEPTION (CRASH) ---')
    logging.critical(''.join(traceback.format_exception(exctype, value, tb)))
    logging.critical('----------------------------------')
    sys.__excepthook__(exctype, value, tb)

def main():
    sys.excepthook = global_exception_hook

    logging.info('Iniciando aplicación KazLauncher.')
    apply_download_patches()
    # QtWebEngine requiere este atributo antes de crear QApplication.
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    # Render por software y sin sandbox para máxima compatibilidad del WebView.
    os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
    os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
    app = QApplication(sys.argv)

    try:
        launcher = MinecraftLauncher()
        start_discord_presence(APP_VERSION)
        app.aboutToQuit.connect(stop_discord_presence)
        launcher.show()
        sys.exit(app.exec())
    except Exception as e:
        logging.critical(f'Critical error during application initialization: {e}', exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
