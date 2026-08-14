"""Persistencia y migración de cuentas premium (multi-cuenta)."""
from __future__ import annotations
from typing import Any
def _session_from_legacy(raw: dict) -> dict | None:
    if not raw or not (raw.get('refresh_token') or raw.get('id')):
        return None
    else:
        return {'id': raw.get('id', ''), 'name': raw.get('name', ''), 'access_token': raw.get('access_token', ''), 'refresh_token': raw.get('refresh_token', '')}
def migrate_account_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Migra premium_session/offline_mode al esquema multi-cuenta."""
    if 'premium_accounts' not in settings:
        accounts = []
        legacy = _session_from_legacy(settings.get('premium_session') or {})
        if legacy:
            accounts.append(legacy)
        settings['premium_accounts'] = accounts
    settings.setdefault('selected_account_id', '')
    settings.setdefault('account_mode', 'offline')
    if settings.get('account_mode') not in ['offline', 'online']:
        settings['account_mode'] = 'offline'
    if settings.get('offline_mode') and settings['account_mode'] != 'offline':
        settings['account_mode'] = 'offline'
    else:
        if not settings.get('offline_mode') and settings.get('premium_accounts') and (settings['account_mode'] == 'offline'):
                    if not settings['selected_account_id']:
                        settings['selected_account_id'] = settings['premium_accounts'][0].get('id', '')
                    settings['account_mode'] = 'online'
    settings['offline_mode'] = settings['account_mode'] == 'offline'
    active = find_account(settings, settings.get('selected_account_id', ''))
    settings['premium_session'] = active or {}
    return settings
def find_account(settings: dict[str, Any], account_id: str) -> dict | None:
    if not account_id:
        return
    else:
        for acc in settings.get('premium_accounts') or []:
            if acc.get('id') == account_id:
                return acc
        return
def upsert_account(settings: dict[str, Any], profile: dict) -> str:
    """Añade o actualiza una cuenta; devuelve su id."""
    account_id = profile.get('id', '')
    entry = {'id': account_id, 'name': profile.get('name', ''), 'access_token': profile.get('access_token', ''), 'refresh_token': profile.get('refresh_token', '')}
    accounts = list(settings.get('premium_accounts') or [])
    replaced = False
    for i, acc in enumerate(accounts):
        if acc.get('id') == account_id:
            accounts[i] = entry
            replaced = True
            break
    if not replaced:
        accounts.append(entry)
    settings['premium_accounts'] = accounts
    settings['selected_account_id'] = account_id
    settings['account_mode'] = 'online'
    settings['offline_mode'] = False
    settings['premium_session'] = entry
    return account_id
def remove_account(settings: dict[str, Any], account_id: str) -> None:
    accounts = [a for a in settings.get('premium_accounts') or [] if a.get('id') != account_id]
    settings['premium_accounts'] = accounts
    if settings.get('selected_account_id') == account_id:
        if accounts:
            settings['selected_account_id'] = accounts[0].get('id', '')
            settings['account_mode'] = 'online'
            settings['offline_mode'] = False
            settings['premium_session'] = accounts[0]
        else:
            settings['selected_account_id'] = ''
            settings['account_mode'] = 'offline'
            settings['offline_mode'] = True
            settings['premium_session'] = {}
    else:
        if settings.get('selected_account_id'):
            active = find_account(settings, settings['selected_account_id'])
            settings['premium_session'] = active or {}
        else:
            settings['premium_session'] = {}
def set_account_mode(settings: dict[str, Any], mode: str, account_id: str='') -> None:
    settings['account_mode'] = mode
    settings['offline_mode'] = mode == 'offline'
    if mode == 'online' and account_id:
        settings['selected_account_id'] = account_id
        settings['premium_session'] = find_account(settings, account_id) or {}
    else:
        if mode == 'offline':
            settings['premium_session'] = find_account(settings, settings.get('selected_account_id', '')) or {}