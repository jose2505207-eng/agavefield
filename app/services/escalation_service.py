"""Escalation engine: rule-based first, AI-assisted second.

Decides whether an observation should be escalated, builds the message,
enforces a cooldown to avoid spam, and dispatches via WhatsApp (preferred)
with a Telegram fallback. Every attempt is persisted as an ``Escalation`` row.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations import telegram_client, whatsapp_client
from app.models.database import Escalation, FieldObservation
from app.models.schemas import HermesOutput

logger = logging.getLogger("agave.escalation")

URGENT_TERMS = [
    "urgent",
    "urgente",
    "escalar",
    "plaga fuerte",
    "riesgo alto",
    "se está extendiendo",
    "se esta extendiendo",
    "revisar hoy",
]

REPEAT_WINDOW_DAYS = 10
REPEAT_THRESHOLD = 3


# --------------------------------------------------------------------------- #
# Rule evaluation
# --------------------------------------------------------------------------- #
def caption_has_urgent_terms(caption: Optional[str]) -> bool:
    if not caption:
        return False
    low = caption.lower()
    return any(term in low for term in URGENT_TERMS)


def _repeated_medium_in_lot(db: Session, lot_id: Optional[int]) -> bool:
    if not lot_id:
        return False
    since = datetime.utcnow() - timedelta(days=REPEAT_WINDOW_DAYS)
    count = (
        db.query(FieldObservation)
        .filter(
            FieldObservation.lot_id == lot_id,
            FieldObservation.severity == "medium",
            FieldObservation.observed_at >= since,
        )
        .count()
    )
    return count >= REPEAT_THRESHOLD


def evaluate_rules(
    db: Session,
    observation: FieldObservation,
    hermes: HermesOutput,
    caption: Optional[str] = None,
    force: bool = False,
) -> tuple[bool, Optional[str]]:
    """Return (should_escalate, reason). Pure rules, no side effects."""
    if force:
        return True, "Manual escalation requested by user"

    if observation.severity in ("high", "critical"):
        return True, f"Severity is {observation.severity}"

    if hermes.escalation_recommended and hermes.confidence >= 0.75:
        return True, hermes.escalation_reason or "AI recommended escalation with high confidence"

    if caption_has_urgent_terms(caption):
        return True, "Caption contains urgent terms"

    if _repeated_medium_in_lot(db, observation.lot_id):
        return True, (
            f"{REPEAT_THRESHOLD}+ medium-severity observations in this lot "
            f"within {REPEAT_WINDOW_DAYS} days"
        )

    return False, None


# --------------------------------------------------------------------------- #
# Cooldown / dedup
# --------------------------------------------------------------------------- #
def _in_cooldown(db: Session, observation: FieldObservation) -> bool:
    """True if an escalation for the same lot+issue went out recently."""
    cutoff = datetime.utcnow() - timedelta(hours=settings.escalation_cooldown_hours)
    issue = observation.suspected_issue
    lot_id = observation.lot_id

    q = (
        db.query(Escalation)
        .join(FieldObservation, Escalation.observation_id == FieldObservation.id)
        .filter(
            Escalation.status == "sent",
            Escalation.created_at >= cutoff,
        )
    )
    # Dedup key: same lot (if known) AND same suspected issue.
    if lot_id is not None:
        q = q.filter(FieldObservation.lot_id == lot_id)
    else:
        q = q.filter(FieldObservation.id == observation.id)
    if issue is not None:
        q = q.filter(FieldObservation.suspected_issue == issue)
    return db.query(q.exists()).scalar()


# --------------------------------------------------------------------------- #
# Message building
# --------------------------------------------------------------------------- #
def build_message(observation: FieldObservation, reason: str) -> str:
    lot = observation.lot.lot_code if observation.lot else "unknown"
    loc = (
        f"{observation.latitude:.5f}, {observation.longitude:.5f}"
        if observation.latitude is not None and observation.longitude is not None
        else "not shared"
    )
    ts = (observation.observed_at or datetime.utcnow()).strftime("%Y-%m-%d %H:%M")
    return (
        "🚨 AGAVE FIELD ESCALATION 🚨\n"
        f"Reason: {reason}\n\n"
        f"Severity: {observation.severity.upper()}\n"
        f"Lot: {lot}\n"
        f"Suspected issue: {observation.suspected_issue or 'unknown'}\n\n"
        f"AI summary: {observation.ai_summary or '(none)'}\n"
        f"Recommended next step: {observation.recommended_next_step or '(none)'}\n\n"
        f"Image: {observation.image_url or '(none)'}\n"
        f"Location: {loc}\n"
        f"Observed at: {ts}\n\n"
        "⚠️ AI-assisted alert. A human agronomist must verify before action."
    )


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
def _dispatch(observation: FieldObservation, body: str) -> list[tuple[str, str, bool]]:
    """Send via WhatsApp (preferred) else Telegram. Returns delivery attempts."""
    attempts: list[tuple[str, str, bool]] = []

    if whatsapp_client.is_enabled() and settings.whatsapp_recipients:
        for recipient in settings.whatsapp_recipients:
            ok = whatsapp_client.send_text(recipient, body)
            attempts.append(("whatsapp", recipient, ok))
        return attempts

    # Telegram fallback: notify the reporting user (supervisor routing can be
    # configured later via a dedicated escalation chat id).
    if observation.user and observation.user.telegram_user_id:
        recipient = observation.user.telegram_user_id
        ok = telegram_client.send_message(recipient, body)
        attempts.append(("telegram", recipient, ok))
    else:
        attempts.append(("none", "no_recipient", False))
    return attempts


def maybe_escalate(
    db: Session,
    observation: FieldObservation,
    hermes: HermesOutput,
    caption: Optional[str] = None,
    force: bool = False,
) -> Optional[Escalation]:
    """Full pipeline: evaluate -> cooldown -> dispatch -> persist."""
    should, reason = evaluate_rules(db, observation, hermes, caption, force)
    if not should:
        observation.escalation_status = "none"
        return None

    if not force and _in_cooldown(db, observation):
        logger.info("Escalation suppressed by cooldown for obs %s", observation.id)
        observation.escalation_status = "suppressed_cooldown"
        return None

    body = build_message(observation, reason or "Escalation")
    attempts = _dispatch(observation, body)
    delivered = any(ok for _, _, ok in attempts)

    channel, recipient, _ = attempts[0]
    esc = Escalation(
        observation_id=observation.id,
        channel=channel,
        recipient=recipient,
        escalation_reason=reason,
        message_body=body,
        status="sent" if delivered else "failed",
        sent_at=datetime.utcnow() if delivered else None,
    )
    db.add(esc)
    observation.escalation_status = "sent" if delivered else "failed"
    db.flush()

    # Mirror into the unified Alert feed for the dashboard (no external resend:
    # the escalation dispatch above already handled delivery).
    from app.services import notification_service

    notification_service.create_alert(
        db,
        title=f"Escalation: {reason or 'field alert'}",
        message=body,
        severity=observation.severity,
        reason=reason,
        channel="dashboard",
        passport_id=observation.passport_id,
        observation_id=observation.id,
    )

    logger.info(
        "Escalation %s for obs %s via %s (delivered=%s)",
        esc.status,
        observation.id,
        channel,
        delivered,
    )
    return esc
