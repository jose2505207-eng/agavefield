"""Telegram intake webhook.

MVP (human-centered): receives photo messages and stores them as historical
field evidence with a manual note + event type + optional follow-up/location.
NO LLM/CV is invoked on upload. The AI (Hermes) path is gated behind
ENABLE_AI_IMAGE_ANALYSIS (off by default, for a future version).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.agents import hermes_agent
from app.config import settings
from app.db import session_scope
from app.integrations import telegram_client
from app.models.database import FieldObservation
from app.models.schemas import HermesInput
from app.services import image_service, observation_service

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

        needs_note = False
        with session_scope() as db:
            user = observation_service.get_or_create_user(
                db, telegram_user_id=telegram_user_id, full_name=full_name
            )
            if settings.enable_ai_image_analysis:
                # Version 2+ AI path (disabled by default).
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
            else:
                # MVP: store the photo as historical evidence + manual note.
                # NO LLM/CV is invoked.
                obs = observation_service.create_evidence_record(
                    db,
                    manual_note=caption,
                    image_url=stored.image_url,
                    thumbnail_url=stored.thumbnail_url,
                    latitude=latitude,
                    longitude=longitude,
                    observed_at=ts,
                    user_id=user.id,
                    source_channel="telegram",
                )
                needs_note = not (caption and caption.strip())
                reply = (
                    f"📸 Photo saved to the timeline (record #{obs.id}).\n"
                    "Pick what this photo is about:"
                )
                keyboard = telegram_client.build_record_keyboard(obs.id)

        telegram_client.send_message(chat_id, reply, reply_markup=keyboard)
        if needs_note:
            telegram_client.send_message(
                chat_id,
                "✍️ Please reply with a short note describing this photo "
                "(required for the field record).",
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Telegram photo processing failed: %s", exc)
        telegram_client.send_message(chat_id, "⚠️ Something went wrong analyzing that photo.")


def _handle_callback(callback: dict) -> None:
    data = callback.get("data", "")
    cq_id = callback.get("id")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    parts = data.split(":")
    action = parts[0] if parts else ""

    ack, msg = "Done", ""
    try:
        if action == "evt" and len(parts) == 3:
            event_type, oid = parts[1], int(parts[2])
            with session_scope() as db:
                obs = db.get(FieldObservation, oid)
                if obs:
                    obs.event_type = event_type
            label = event_type.replace("_", " ")
            ack = f"Event: {label}"
            msg = f"Record #{oid} marked as “{label}”."
        elif action == "followup" and len(parts) == 2:
            oid = int(parts[1])
            with session_scope() as db:
                obs = db.get(FieldObservation, oid)
                if obs:
                    obs.follow_up_needed = True
                    obs.review_status = "needs_followup"
            ack = "Flagged for follow-up"
            msg = (
                f"Record #{oid} flagged for follow-up. A supervisor can set the "
                "date in Field Notes Review."
            )
        elif action == "reqloc" and len(parts) == 2:
            ack = "Location"
            if chat_id:
                telegram_client.send_message(
                    chat_id,
                    "📍 Tap to share this record's location:",
                    reply_markup=telegram_client.build_location_request_keyboard(),
                )
        else:
            ack = "Unknown action"
    except (ValueError, IndexError):
        ack = "Bad action"

    telegram_client.answer_callback_query(cq_id, ack)
    if chat_id and msg:
        telegram_client.send_message(chat_id, msg)


def _attach_note(telegram_user_id: str, text: str, chat_id) -> None:
    """Treat a plain text reply as the manual note for the latest note-less record."""
    with session_scope() as db:
        user = observation_service.get_or_create_user(db, telegram_user_id=telegram_user_id)
        obs = observation_service.latest_note_pending_record(db, user.id)
        if not obs:
            telegram_client.send_message(
                chat_id,
                "👋 Send a photo of the field to start a record, then reply with your note.",
            )
            return
        obs.manual_note = text
        if not obs.original_caption:
            obs.original_caption = text
        oid = obs.id
    telegram_client.send_message(chat_id, f"✍️ Note saved to record #{oid}. Thank you.")


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
        telegram_client.send_message(chat_id, "📷 Photo received — saving to your field timeline…")
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

    # Plain text (not a command) → treat as the note for the latest note-less record.
    text = message.get("text")
    if text and telegram_user_id and not text.startswith("/"):
        if settings.telegram_webhook_sync:
            _attach_note(telegram_user_id, text, chat_id)
        else:
            background.add_task(_attach_note, telegram_user_id, text, chat_id)
        return {"ok": True}

    if chat_id:
        telegram_client.send_message(
            chat_id,
            "👋 Send a photo of an agave plant, row, or field condition. I'll save it to "
            "the timeline — then reply with a note and pick the event type.",
        )
    return {"ok": True}
