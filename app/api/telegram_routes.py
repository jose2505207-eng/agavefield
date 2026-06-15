"""Telegram intake webhook.

Receives photo messages (caption, user id, timestamp, optional shared
location), stores the image, runs Hermes in the background, and replies with a
concise summary plus action buttons. Also handles button callbacks for the
confirm / change-lot / false-positive / escalate / request-location workflow.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.agents import hermes_agent
from app.config import settings
from app.db import session_scope
from app.integrations import telegram_client
from app.models.schemas import (
    CorrectRequest,
    HermesInput,
    HermesOutput,
    VerifyRequest,
)
from app.services import escalation_service, image_service, observation_service

logger = logging.getLogger("agave.api.telegram")
router = APIRouter(tags=["webhooks"])


def _largest_photo(photos: list[dict]) -> Optional[dict]:
    if not photos:
        return None
    return max(photos, key=lambda p: p.get("file_size", p.get("width", 0)))


def _process_photo(
    chat_id: int,
    telegram_user_id: str,
    full_name: Optional[str],
    file_id: str,
    caption: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    ts: Optional[datetime],
) -> None:
    """Background worker: download -> store -> Hermes -> reply."""
    try:
        file_url = telegram_client.get_file_url(file_id)
        if not file_url:
            telegram_client.send_message(chat_id, "Could not download the image. Try again.")
            return
        stored = image_service.store_image_from_url(file_url)

        with session_scope() as db:
            user = observation_service.get_or_create_user(
                db, telegram_user_id=telegram_user_id, full_name=full_name
            )
            result = hermes_agent.run(
                db,
                HermesInput(
                    image_url=stored.image_url,
                    thumbnail_url=stored.thumbnail_url,
                    caption=caption,
                    user_id=user.id,
                    source_channel="telegram",
                    latitude=latitude,
                    longitude=longitude,
                    timestamp=ts,
                ),
            )
            reply = result.reply_text
            keyboard = telegram_client.build_action_keyboard(result.observation.id)
            needs_location = result.observation.latitude is None

        telegram_client.send_message(chat_id, reply, reply_markup=keyboard)
        # Offer one-tap location capture when the photo had no GPS.
        if needs_location:
            telegram_client.send_message(
                chat_id,
                "📍 Tap to attach this plant's location (one tap after allowing it):",
                reply_markup=telegram_client.build_location_request_keyboard(),
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Telegram photo processing failed: %s", exc)
        telegram_client.send_message(chat_id, "⚠️ Something went wrong analyzing that photo.")


def _handle_callback(callback: dict) -> None:
    data = callback.get("data", "")
    cq_id = callback.get("id")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    if ":" not in data:
        telegram_client.answer_callback_query(cq_id, "Unknown action")
        return
    action, raw_id = data.split(":", 1)
    try:
        obs_id = int(raw_id)
    except ValueError:
        telegram_client.answer_callback_query(cq_id, "Bad observation id")
        return

    msg, ack = "", "Done"
    with session_scope() as db:
        if action == "confirm":
            observation_service.verify_observation(db, obs_id, VerifyRequest(human_verified=True))
            ack, msg = "Confirmed ✅", f"Observation #{obs_id} confirmed. Thank you."
        elif action == "falsepos":
            observation_service.correct_observation(
                db, obs_id, CorrectRequest(human_correction="Marked as false positive by user")
            )
            ack, msg = "Marked false positive", f"Observation #{obs_id} marked as false positive."
        elif action == "changelot":
            ack = "Send the lot code"
            msg = (
                f"To change the lot for observation #{obs_id}, reply with: "
                f"lot <LOT_CODE> (lot editing via dashboard/API is also available)."
            )
        elif action == "reqloc":
            ack = "Location requested"
            # Send the one-tap reply keyboard rather than a plain text hint.
            if chat_id:
                telegram_client.send_message(
                    chat_id,
                    "📍 Tap to share this plant's location:",
                    reply_markup=telegram_client.build_location_request_keyboard(),
                )
        elif action == "escalate":
            obs = observation_service.get_observation(db, obs_id)
            if obs:
                hermes_view = HermesOutput(
                    severity=obs.severity,
                    suspected_issue=obs.suspected_issue,
                    confidence=obs.confidence,
                    agronomic_summary=obs.ai_summary or "",
                    recommended_next_step=obs.recommended_next_step or "",
                )
                escalation_service.maybe_escalate(
                    db, obs, hermes_view, obs.original_caption, force=True
                )
                ack, msg = "Escalated ⚠️", f"Observation #{obs_id} escalated to the field team."
            else:
                ack, msg = "Not found", "Observation not found."
        else:
            ack = "Unknown action"

    telegram_client.answer_callback_query(cq_id, ack)
    if chat_id and msg:
        telegram_client.send_message(chat_id, msg)


def _attach_location(telegram_user_id: str, latitude: float, longitude: float, chat_id) -> None:
    """Attach a shared location to the user's most recent un-located observation."""
    with session_scope() as db:
        user = observation_service.get_or_create_user(db, telegram_user_id=telegram_user_id)
        obs = observation_service.latest_unlocated_observation(db, user.id)
        if not obs:
            telegram_client.send_message(
                chat_id,
                "📍 Got your location — now send a photo (or tap Share location right "
                "after a photo) and I'll attach it.",
                reply_markup=telegram_client.remove_keyboard(),
            )
            return
        observation_service.set_observation_location(db, obs, latitude, longitude)
        lot = obs.lot.lot_code if obs.lot else "unknown"
        oid = obs.id
    telegram_client.send_message(
        chat_id,
        f"📍 Location saved to observation #{oid} (lot: {lot}). It now appears on the map.",
        reply_markup=telegram_client.remove_keyboard(),
    )


@router.post("/webhooks/telegram")
async def telegram_webhook(
    request: Request,
    background: BackgroundTasks,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(403, "Invalid webhook secret")

    update = await request.json()

    # Button callbacks.
    if "callback_query" in update:
        _handle_callback(update["callback_query"])
        return {"ok": True}

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    from_user = message.get("from", {})
    telegram_user_id = str(from_user.get("id")) if from_user.get("id") else None
    full_name = " ".join(
        filter(None, [from_user.get("first_name"), from_user.get("last_name")])
    ) or from_user.get("username")
    ts = datetime.utcfromtimestamp(message["date"]) if message.get("date") else None

    location = message.get("location") or {}
    latitude = location.get("latitude")
    longitude = location.get("longitude")

    photos = message.get("photo")
    if photos:
        photo = _largest_photo(photos)
        telegram_client.send_message(chat_id, "📷 Photo received — Hermes is analyzing it…")
        args = (
            chat_id,
            telegram_user_id,
            full_name,
            photo["file_id"],
            message.get("caption"),
            latitude,
            longitude,
            ts,
        )
        if settings.telegram_webhook_sync:
            # Serverless-safe: finish processing before returning 200 so the work
            # is never cut off by the instance freezing after the response.
            _process_photo(*args)
        else:
            background.add_task(_process_photo, *args)
        return {"ok": True}

    if latitude is not None and longitude is not None and telegram_user_id:
        # A shared location (from the one-tap button) — attach it to the user's
        # most recent observation that still lacks coordinates.
        if settings.telegram_webhook_sync:
            _attach_location(telegram_user_id, latitude, longitude, chat_id)
        else:
            background.add_task(_attach_location, telegram_user_id, latitude, longitude, chat_id)
        return {"ok": True}

    if chat_id:
        telegram_client.send_message(
            chat_id,
            "👋 Send a photo of an agave plant, row, or symptom and I'll create a field observation.",
        )
    return {"ok": True}
