"""WhatsApp Cloud API webhook (optional, gated behind WHATSAPP_* env vars).

GET  /webhooks/whatsapp  -> verification handshake
POST /webhooks/whatsapp  -> inbound text/media messages
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.db import session_scope
from app.integrations import whatsapp_client
from app.models.schemas import HermesInput
from app.agents import hermes_agent
from app.services import image_service, observation_service

logger = logging.getLogger("agave.api.whatsapp")
router = APIRouter(tags=["webhooks"])


@router.get("/webhooks/whatsapp")
def whatsapp_verify(
    hub_mode: Optional[str] = Query(default=None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(default=None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
):
    challenge = whatsapp_client.verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    if challenge is None:
        raise HTTPException(403, "Verification failed")
    return Response(content=str(challenge), media_type="text/plain")


def _process_message(msg: dict) -> None:
    sender = msg.get("from")
    caption = msg.get("caption") or msg.get("text")
    media_id = msg.get("image_id")
    ts = (
        datetime.utcfromtimestamp(int(msg["timestamp"]))
        if msg.get("timestamp")
        else None
    )

    if not media_id:
        whatsapp_client.send_text(
            sender, "👋 Send a photo of an agave plant or symptom to create an observation."
        )
        return

    data = whatsapp_client.download_media(media_id)
    if not data:
        whatsapp_client.send_text(sender, "Could not download the image. Please retry.")
        return
    stored = image_service.store_image_bytes(data)

    with session_scope() as db:
        user = observation_service.get_or_create_user(db, whatsapp_phone=sender)
        result = hermes_agent.run(
            db,
            HermesInput(
                image_url=stored.image_url,
                thumbnail_url=stored.thumbnail_url,
                caption=caption,
                user_id=user.id,
                source_channel="whatsapp",
                timestamp=ts,
            ),
        )
        reply = result.reply_text

    whatsapp_client.send_text(sender, reply)


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    payload = await request.json()
    for msg in whatsapp_client.parse_inbound(payload):
        try:
            _process_message(msg)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("WhatsApp message processing failed: %s", exc)
    return {"status": "received"}
