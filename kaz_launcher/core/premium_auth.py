"""Autenticación Microsoft / Minecraft para cuentas premium."""
from __future__ import annotations
import http.server
import threading
import urllib.parse
import requests
MINECRAFT_NOT_OWNED = '__MINECRAFT_NOT_OWNED__'
def is_minecraft_profile_error(error: str) -> bool:
    err = str(error or '')
    return MINECRAFT_NOT_OWNED in err or 'NOT_FOUND' in err
def fetch_minecraft_profile(msa_access_token: str) -> dict:
    """Flujo manual XBL → XSTS → Minecraft sin depender de minecraft_launcher_lib."""
    xbl_resp = requests.post('https://user.auth.xboxlive.com/user/authenticate', json={'Properties': {'AuthMethod': 'RPS', 'SiteName': 'user.auth.xboxlive.com', 'RpsTicket': f'd={msa_access_token}'}, 'RelyingParty': 'http://auth.xboxlive.com', 'TokenType': 'JWT'}, headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, timeout=20)
    xbl_resp.raise_for_status()
    xbl = xbl_resp.json()
    xbl_token = xbl['Token']
    userhash = xbl['DisplayClaims']['xui'][0]['uhs']
    xsts_resp = requests.post('https://xsts.auth.xboxlive.com/xsts/authorize', json={'Properties': {'SandboxId': 'RETAIL', 'UserTokens': [xbl_token]}, 'RelyingParty': 'rp://api.minecraftservices.com/', 'TokenType': 'JWT'}, headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, timeout=20)
    xsts = xsts_resp.json()
    if 'Token' not in xsts:
        raise RuntimeError(f'XSTS error: {xsts}')
    else:
        xsts_token = xsts['Token']
        mc_resp = requests.post('https://api.minecraftservices.com/authentication/login_with_xbox', json={'identityToken': f'XBL3.0 x={userhash};{xsts_token}'}, headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, timeout=20)
        mc = mc_resp.json()
        if 'access_token' not in mc:
            raise RuntimeError(f'Minecraft auth error: {mc}')
        else:
            mc_token = mc['access_token']
            profile_resp = requests.get('https://api.minecraftservices.com/minecraft/profile', headers={'Authorization': f'Bearer {mc_token}'}, timeout=20)
            profile = profile_resp.json()
            if profile_resp.status_code == 404 or profile.get('error') == 'NOT_FOUND':
                raise RuntimeError(MINECRAFT_NOT_OWNED)
            else:
                if 'error' in profile:
                    raise RuntimeError(f'Profile error: {profile}')
                else:
                    profile['access_token'] = mc_token
                    return profile


def exchange_auth_code(client_id: str, redirect_uri: str, code: str, code_verifier: str, expected_state: str, received_state: str) -> dict:
    """Intercambia el código OAuth por perfil Minecraft."""
    if expected_state and received_state != expected_state:
        raise RuntimeError('state_mismatch')
    else:
        token_endpoint = 'https://login.microsoftonline.com/consumers/oauth2/v2.0/token'
        data = {'client_id': client_id, 'scope': 'XboxLive.signin offline_access', 'code': code, 'redirect_uri': redirect_uri, 'grant_type': 'authorization_code', 'code_verifier': code_verifier}
        resp = requests.post(token_endpoint, data=data, timeout=20)
        try:
            tok = resp.json()
        except Exception:
            tok = {}
        if 'access_token' not in tok:
            raise RuntimeError(tok.get('error_description') or 'token_error')
        else:
            profile = fetch_minecraft_profile(tok['access_token'])
            profile['refresh_token'] = tok.get('refresh_token', '')
            return profile
def refresh_minecraft_profile(client_id: str, refresh_token: str) -> dict:
    """Renueva tokens y devuelve perfil Minecraft actualizado."""
    from minecraft_launcher_lib.exceptions import InvalidRefreshToken
    token_endpoint = 'https://login.microsoftonline.com/consumers/oauth2/v2.0/token'
    data = {'client_id': client_id, 'scope': 'XboxLive.signin offline_access', 'refresh_token': refresh_token, 'grant_type': 'refresh_token'}
    resp = requests.post(token_endpoint, data=data, timeout=20)
    tok = resp.json()
    if 'access_token' not in tok:
        if tok.get('error') in ['invalid_grant', 'interaction_required']:
            raise InvalidRefreshToken(tok.get('error_description') or tok.get('error', ''))
        else:
            raise RuntimeError(tok.get('error_description') or 'token_error')
    else:
        profile = fetch_minecraft_profile(tok['access_token'])
        profile['refresh_token'] = tok.get('refresh_token', refresh_token)
        return profile
try:
    from PySide6.QtCore import QThread, Signal

    class PremiumTokenWorker(QThread):
        finished = Signal(bool, dict, str)

        def __init__(self, client_id: str, redirect_uri: str, code: str, expected_state: str, received_state: str, code_verifier: str, parent):
            super().__init__(parent)
            self.client_id = client_id
            self.redirect_uri = redirect_uri
            self.code = code
            self.expected_state = expected_state
            self.received_state = received_state
            self.code_verifier = code_verifier

        def run(self):
            try:
                profile = exchange_auth_code(self.client_id, self.redirect_uri, self.code, self.code_verifier, self.expected_state, self.received_state)
                self.finished.emit(True, profile, '')
            except Exception as e:
                self.finished.emit(False, {}, str(e))
except ImportError:
    PremiumTokenWorker = None


class _OAuthRedirectHandler(http.server.BaseHTTPRequestHandler):
    """Captura el redirect de Microsoft hacia localhost:<puerto>/callback."""

    def log_message(self, *args):
        pass

    def _reply(self, text):
        body = text.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if getattr(self.server, 'result', None) is not None:
            self._reply('<html><body><h3>Ya puedes cerrar esta pestaña y volver al launcher.</h3></body></html>')
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.rstrip('/') == '/callback':
            qs = urllib.parse.parse_qs(parsed.query)
            self.server.result = {
                'code': qs.get('code', [None])[0],
                'state': qs.get('state', [None])[0],
                'error': qs.get('error', [None])[0],
            }
            self._reply('<html><body><h3>Login recibido. Ya puedes cerrar esta pestaña y volver al launcher.</h3></body></html>')
        else:
            self._reply('<html><body><h3>Servidor de autorización de KazLauncher.</h3></body></html>')


class _OAuthCallbackServer(http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port):
        super().__init__(('127.0.0.1', port), _OAuthRedirectHandler)
        self.result = None


def start_oauth_callback_server(port) -> _OAuthCallbackServer:
    """Levanta un mini servidor local que captura el redirect OAuth sin bloquear."""
    server = _OAuthCallbackServer(port)
    threading.Thread(target=server.serve_forever, daemon=True, name='oauth-callback').start()
    return server