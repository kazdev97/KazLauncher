"""Diálogo de login Microsoft embebido en el launcher (sin navegador externo)."""
from __future__ import annotations
import urllib.parse
from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEnginePage
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    QWebEngineView = None
    QWebEnginePage = None
def webengine_available() -> bool:
    return WEBENGINE_AVAILABLE
if WEBENGINE_AVAILABLE:
    class _OAuthPage(QWebEnginePage):
        def __init__(self, redirect_uri: str, on_redirect, parent=None):
            super().__init__(parent)
            self._redirect_uri = redirect_uri.rstrip('/')
            self._on_redirect = on_redirect
        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
            if is_main_frame and self._try_capture(url):
                return False
            else:
                return super().acceptNavigationRequest(url, nav_type, is_main_frame)
        def _try_capture(self, url: QUrl) -> bool:
            url_str = url.toString()
            if not url_str.startswith(self._redirect_uri):
                return False
            else:
                parsed = urllib.parse.urlparse(url_str)
                expected_path = urllib.parse.urlparse(self._redirect_uri).path.rstrip('/') or '/callback'
                if parsed.path.rstrip('/') != expected_path.rstrip('/'):
                    return False
                else:
                    qs = urllib.parse.parse_qs(parsed.query)
                    code = qs.get('code', [None])[0]
                    state = qs.get('state', [None])[0]
                    error = qs.get('error', [None])[0]
                    self._on_redirect(code, state, error)
                    return True
    class PremiumLoginDialog(QDialog):
        """Ventana con WebView para completar el login OAuth de Microsoft."""
        def __init__(self, auth_url: str, redirect_uri: str, lang_dict: dict, parent=None):
            super().__init__(parent)
            self.lang_dict = lang_dict
            self.redirect_uri = redirect_uri
            self.auth_code = ''
            self.auth_state = ''
            self.auth_error = ''
            self._captured = False
            self.setWindowTitle(lang_dict.get('premium_login_dialog_title', 'Iniciar sesión con Microsoft'))
            self.setModal(True)
            self.resize(540, 700)
            # QtWebEngine no soporta ventanas translúcidas; el diálogo debe ser opaco.
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)
            hint = QLabel(lang_dict.get('premium_login_in_app_hint', 'Usa la cuenta de Microsoft que tiene Minecraft: Java Edition.'))
            hint.setWordWrap(True)
            hint.setObjectName('loginStatusLabel')
            layout.addWidget(hint)
            self.web_view = QWebEngineView(self)
            page = _OAuthPage(redirect_uri, self._handle_redirect, self.web_view)
            self.web_view.setPage(page)
            self.web_view.urlChanged.connect(self._on_url_changed)
            self.web_view.load(QUrl(auth_url))
            layout.addWidget(self.web_view, 1)
            buttons = QHBoxLayout()
            buttons.addStretch()
            external_btn = QPushButton(lang_dict.get('premium_external_browser_btn', '¿Problemas? Usar navegador externo'))
            external_btn.clicked.connect(self._use_external_browser)
            buttons.addWidget(external_btn)
            cancel_btn = QPushButton(lang_dict.get('cancel_button', 'Cancelar'))
            cancel_btn.clicked.connect(self._cancel)
            buttons.addWidget(cancel_btn)
            layout.addLayout(buttons)
        def _handle_redirect(self, code, state, error):
            if self._captured:
                return
            else:
                self._captured = True
                if error or not code:
                    self.auth_error = error or 'cancelled'
                    self.reject()
                else:
                    self.auth_code = code
                    self.auth_state = state or ''
                    self.accept()
        def _on_url_changed(self, url: QUrl):
            page = self.web_view.page()
            if hasattr(page, '_try_capture'):
                page._try_capture(url)
        def _use_external_browser(self):
            """El usuario prefiere completar el login en su navegador predeterminado."""
            self.auth_error = 'external_fallback'
            self.reject()
        def _cancel(self):
            self.auth_error = 'cancelled'
            self.reject()
else:
    PremiumLoginDialog = None