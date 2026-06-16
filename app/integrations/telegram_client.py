"""Thin Telegram Bot API client.

Only the calls the MVP needs: resolve+download a photo file, send a text
message with inline buttons, and acknowledge button taps. Fails gracefully /
logs when TELEGRAM_BOT_TOKEN is absent.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger("agave.telegram")

API_BASE = "https://api.telegram.org"


def _token() -> Optional[str]:
    return settings.telegram_bot_token or None


def _api_url(method: str) -> str:
    return f"{API_BASE}/bot{settings.telegram_bot_token}/{method}"


def get_file_url(file_id: str) -> Optional[str]:
    """Resolve a Telegram file_id into a direct download URL."""
    if not _token():
        logger.warning("Telegram token missing; cannot resolve file %s", file_id)
        return None
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(_api_url("getFile"), params={"file_id": file_id})
        resp.raise_for_status()
        result = resp.json().get("result", {})
    file_path = result.get("file_path")
    if not file_path:
        return None
    return f"{API_BASE}/file/bot{settings.telegram_bot_token}/{file_path}"


def build_action_keyboard(observation_id: int) -> dict:
    """Inline keyboard for the post-save confirmation workflow."""
    oid = observation_id
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Confirm", "callback_data": f"confirm:{oid}"},
                {"text": "📍 Change lot", "callback_data": f"changelot:{oid}"},
            ],
            [
                {"text": "🚫 False positive", "callback_data": f"falsepos:{oid}"},
                {"text": "⚠️ Escalate", "callback_data": f"escalate:{oid}"},
            ],
            [
                {"text": "🗺️ Request location", "callback_data": f"reqloc:{oid}"},
            ],
        ]
    }


def build_location_request_keyboard() -> dict:
    """One-tap reply keyboard that sends the user's current location.

    After the user grants Telegram the OS location permission, tapping this
    button shares their location in a single tap (Telegram cannot read location
    passively — this is the lowest-friction option).
    """
    return {
        "keyboard": [[{"text": "📍 Share location", "request_location": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def remove_keyboard() -> dict:
    """Markup that clears a custom reply keyboard."""
    return {"remove_keyboard": True}


def build_record_keyboard(observation_id: int) -> dict:
    """Inline keyboard for a human field record: pick event type, flag a
    follow-up, or attach location. No AI actions."""
    o = observation_id
    return {
        "inline_keyboard": [
            [
                {"text": "🌱 Observation", "callback_data": f"evt:observation:{o}"},
                {"text": "💧 Irrigation", "callback_data": f"evt:irrigation:{o}"},
            ],
            [
                {"text": "🧪 Fertilization", "callback_data": f"evt:fertilization:{o}"},
                {"text": "🍂 Compost", "callback_data": f"evt:compost:{o}"},
            ],
            [
                {"text": "🐛 Pest treatment", "callback_data": f"evt:pest_treatment:{o}"},
                {"text": "🌿 Herbicide", "callback_data": f"evt:herbicide:{o}"},
            ],
            [
                {"text": "✂️ Weed control", "callback_data": f"evt:weed_control:{o}"},
                {"text": "🔧 Maintenance", "callback_data": f"evt:maintenance:{o}"},
            ],
            [
                {"text": "⏰ Needs follow-up", "callback_data": f"followup:{o}"},
                {"text": "📍 Add location", "callback_data": f"reqloc:{o}"},
            ],
        ]
    }


def send_message(
    chat_id: Any,
    text: str,
    reply_markup: Optional[dict] = None,
) -> bool:
    if not _token():
        logger.warning("Telegram token missing; would send to %s: %s", chat_id, text[:80])
        return False
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(_api_url("sendMessage"), json=payload)
            resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Telegram sendMessage failed: %s", exc)
        return False


def answer_callback_query(callback_query_id: str, text: str = "") -> None:
    if not _token():
        return
    try:
        with httpx.Client(timeout=15.0) as client:
            client.post(
                _api_url("answerCallbackQuery"),
                json={"callback_query_id": callback_query_id, "text": text},
            )
    except Exception as exc:  # pragma: no cover
        logger.warning("answerCallbackQuery failed: %s", exc)
