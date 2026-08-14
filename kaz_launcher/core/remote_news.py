"""Noticias remotas desde JSON (ClaroDrive, GitHub raw, Google Drive, etc.)."""
from __future__ import annotations
import logging
from typing import Any
from .remote_url import fetch_remote_json
def _normalize_item(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return
    else:
        title = str(raw.get('title') or raw.get('titulo') or '').strip()
        if not title:
            return
        else:
            return {'title': title, 'description': str(raw.get('description') or raw.get('descripcion') or raw.get('desc') or '').strip(), 'date': str(raw.get('date') or raw.get('fecha') or '').strip(), 'link': str(raw.get('link') or raw.get('url') or raw.get('enlace') or '').strip()}
def parse_news_payload(payload: Any) -> list[dict]:
    """Acepta {\"news\":[...]}, {\"noticias\":[...]} o una lista directa."""
    if isinstance(payload, list):
        items = payload
    else:
        if isinstance(payload, dict):
            items = payload.get('news') or payload.get('noticias') or payload.get('items') or []
        else:
            return []
    result = []
    for entry in items:
        normalized = _normalize_item(entry)
        if normalized:
            result.append(normalized)
    return result
def fetch_remote_news(url: str) -> list[dict]:
    """Descarga y parsea news.json remoto."""
    if not (url or '').strip():
        return []
    else:
        try:
            payload = fetch_remote_json(url)
            items = parse_news_payload(payload)
            if not items:
                logging.warning('Manifest de noticias vacío o sin entradas válidas: %s', url)
            return items
        except Exception as exc:
            logging.error('Error al obtener noticias remotas: %s', exc)
            raise