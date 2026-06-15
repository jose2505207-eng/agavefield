"""Hermes — the agent that turns a field photo into structured evidence.

Flow (each step is a tool call, see app/agents/tools.py):
  analyze image -> validate JSON -> (weather + lot matching happen inside
  observation creation) -> persist observation + model output -> decide &
  maybe trigger escalation -> produce a human-facing reply + missing-field ask.

Hermes never owns integrations directly and never writes unvalidated data.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from datetime import datetime, timedelta

from sqlalchemy import select

from app.agents import tools
from app.models.database import AgavePassport, FieldObservation, Lot
from app.models.schemas import HermesInput, HermesOutput
from app.services import (
    notification_service,
    passport_service,
    task_service,
)

logger = logging.getLogger("agave.hermes")

_CONFIDENCE_LABEL = "Confidence"


@dataclass
class HermesResult:
    observation: FieldObservation
    hermes: HermesOutput
    escalated: bool
    reply_text: str
    missing_fields: List[str] = field(default_factory=list)


def _confidence_pct(conf: float) -> str:
    return f"{round(conf * 100)}%"


def _repeated_issue(db, passport_id: int, diagnosis: str | None, window_days: int = 10) -> bool:
    """True if the same passport/zone shows the same diagnosis 2+ times recently."""
    if not diagnosis:
        return False
    since = datetime.utcnow() - timedelta(days=window_days)
    count = (
        db.query(FieldObservation)
        .filter(
            FieldObservation.passport_id == passport_id,
            FieldObservation.diagnosis == diagnosis,
            FieldObservation.observed_at >= since,
        )
        .count()
    )
    return count >= 2


def build_reply_text(obs: FieldObservation, hermes: HermesOutput, escalated: bool) -> str:
    """The concise confirmation message sent back to the agronomist."""
    lot = obs.lot.lot_code if obs.lot else "unknown"
    issue = hermes.suspected_issue or hermes.plant_condition.value.replace("_", " ")
    lines = [
        "✅ Observation saved.",
        "",
        f"Possible issue: {issue}",
        f"Severity: {hermes.severity.value}",
        f"{_CONFIDENCE_LABEL}: {_confidence_pct(hermes.confidence)}",
        f"Lot: {lot}",
        "",
        "Recommended next step:",
        hermes.recommended_next_step or "Have an agronomist inspect the plant.",
    ]
    if hermes.needs_human_review:
        lines += ["", "🔎 Needs human review — Hermes is not certain."]
    if hermes.missing_fields:
        lines += ["", "Missing info: " + ", ".join(hermes.missing_fields)]
    if escalated:
        lines += ["", "⚠️ This case was escalated to the field team."]
    lines += ["", "Choose an action below."]
    return "\n".join(lines)


def run(db: Session, payload: HermesInput) -> HermesResult:
    """Execute the full Hermes pipeline for one inbound image."""
    logger.info(
        "Hermes run: channel=%s user=%s coords=(%s,%s)",
        payload.source_channel,
        payload.user_id,
        payload.latitude,
        payload.longitude,
    )

    # 1) Vision analysis (validated against the strict schema).
    hermes, model_name, raw = tools.tool_analyze_image(
        payload.image_url, payload.caption, payload.latitude, payload.longitude
    )

    # 2) Persist observation (lot match + weather happen inside the service).
    obs = tools.tool_create_observation(
        db,
        hermes=hermes,
        model_name=model_name,
        raw_json=raw,
        user_id=payload.user_id,
        lot_id=payload.lot_id,
        source_channel=payload.source_channel,
        image_url=payload.image_url,
        thumbnail_url=payload.thumbnail_url,
        caption=payload.caption,
        latitude=payload.latitude,
        longitude=payload.longitude,
        observed_at=payload.timestamp,
    )

    # 3) Upsert the Agave Passport (the plant/zone memory) and link it.
    lot = db.get(Lot, obs.lot_id) if obs.lot_id else None
    passport = passport_service.get_or_create_for_observation(
        db, lot=lot, latitude=payload.latitude, longitude=payload.longitude
    )
    obs.passport_id = passport.id
    passport_service.update_from_observation(db, passport, obs)

    # 4) Auto-create recommended tasks (dangerous ones stay gated for approval).
    task_service.create_tasks_from_recommendations(
        db, hermes.recommended_tasks, observation=obs, passport=passport
    )

    # 5) Compute missing fields the agronomist should provide.
    missing = list(hermes.missing_fields)
    if obs.lot_id is None and "lot" not in missing:
        missing.append("lot")
    if (payload.latitude is None or payload.longitude is None) and "location" not in missing:
        missing.append("location")

    # 6) Escalation decision (rules + cooldown handled in the service).
    esc = tools.tool_maybe_escalate(db, obs, hermes, payload.caption, force=False)
    escalation_attempted = esc is not None  # a record/alert was already created
    escalated = esc is not None and esc.status == "sent"  # actually delivered

    # 7) Alert-only conditions that don't meet escalation thresholds
    #    (repeated issue in the same passport/zone, or weather risk).
    if not escalation_attempted:
        repeated = _repeated_issue(db, passport.id, obs.diagnosis)
        weather_risk = any(
            w.heat_risk == "high" or w.drought_risk == "high" for w in obs.weather_snapshots
        )
        should, reason = notification_service.should_alert(
            db, obs, repeated_issue=repeated, weather_risk=weather_risk
        )
        if should:
            notification_service.create_alert(
                db,
                title=f"Field alert: {obs.diagnosis or obs.plant_condition}",
                message=obs.ai_summary or "Observation flagged for attention.",
                severity=obs.severity,
                reason=reason,
                passport_id=passport.id,
                observation_id=obs.id,
            )

    db.commit()
    db.refresh(obs)

    reply = build_reply_text(obs, hermes, escalated)
    return HermesResult(
        observation=obs,
        hermes=hermes,
        escalated=escalated,
        reply_text=reply,
        missing_fields=missing,
    )
