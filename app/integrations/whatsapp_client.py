"""WhatsApp Cloud API client (optional).

Everything is gated behind WHATSAPP_* env vars. With no credentials the client
is "disabled": sends are logged and return False, webhook verification still
works for local testing. This keeps WhatsApp fully optional for the MVP while
making it the preferred escalation channel when configured.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("agave.whatsapp")

GRAPH_BASE = "https://graph.facebook.com/v20.0"


def is_enabled() -> bool:
    return settings.whatsapp_enabled


def verify_webhook(mode: Optional[str], token: Optional[str], challenge: Optional[str]):
    """Return the challenge string if the verify handshake is valid, else None."""
    if mode == "subscribe" and token and token == settings.whatsapp_verify_token:
        return challenge
    return None


def send_text(to: str, body: str) -> bool:
    if not is_enabled():
        logger.warning("WhatsApp disabled; would send to %s: %s", to, body[:80])
        return False
    url = f"{GRAPH_BASE}/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body[:4096]},
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("WhatsApp send failed to %s: %s", to, exc)
        return False


def download_media(media_id: str, timeout: float = 30.0) -> Optional[bytes]:
    """Resolve a WhatsApp media id to bytes (two-step Graph API call)."""
    if not is_enabled():
        return None
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    try:
        with httpx.Client(timeout=timeout) as client:
            meta = client.get(f"{GRAPH_BASE}/{media_id}", headers=headers)
            meta.raise_for_status()
            url = meta.json().get("url")
            if not url:
                return None
            media = client.get(url, headers=headers)
            media.raise_for_status()
            return media.content
    except Exception as exc:
        logger.error("WhatsApp media download failed for %s: %s", media_id, exc)
        return None


def parse_inbound(payload: dict) -> list[dict]:
    """Flatten a WhatsApp webhook payload into simple message dicts."""
    messages = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                messages.append(
                    {
                        "from": msg.get("from"),
                        "type": msg.get("type"),
                        "text": (msg.get("text") or {}).get("body"),
                        "image_id": (msg.get("image") or {}).get("id"),
                        "caption": (msg.get("image") or {}).get("caption"),
                        "timestamp": msg.get("timestamp"),
                    }
                )
    return messages
