"""Observation lifecycle: create from Hermes output, verify, correct, query.

This is the heart of "every photo becomes structured evidence". It composes
lot matching + weather enrichment + immutable model-output logging, and keeps
human corrections as training-quality feedback WITHOUT overwriting the
original AI output (requirement 12).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.database import (
    FieldObservation,
    Lot,
    ModelOutput,
    User,
    WeatherSnapshot,
)
from app.models.schemas import CorrectRequest, HermesOutput, VerifyRequest
from app.services import lot_matching_service, weather_service

logger = logging.getLogger("agave.observation")


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
def get_or_create_user(
    db: Session,
    *,
    telegram_user_id: Optional[str] = None,
    whatsapp_phone: Optional[str] = None,
    full_name: Optional[str] = None,
) -> User:
    user = None
    if telegram_user_id:
        user = db.execute(
            select(User).where(User.telegram_user_id == str(telegram_user_id))
        ).scalar_one_or_none()
    elif whatsapp_phone:
        user = db.execute(
            select(User).where(User.whatsapp_phone == whatsapp_phone)
        ).scalar_one_or_none()
    if user:
        return user
    user = User(
        telegram_user_id=str(telegram_user_id) if telegram_user_id else None,
        whatsapp_phone=whatsapp_phone,
        full_name=full_name,
        role="agronomist",
    )
    db.add(user)
    db.flush()
    return user


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #
def create_observation(
    db: Session,
    *,
    hermes: HermesOutput,
    model_name: str,
    raw_json: dict,
    user_id: Optional[int] = None,
    lot_id: Optional[int] = None,
    source_channel: str = "telegram",
    image_url: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    caption: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    observed_at: Optional[datetime] = None,
    fetch_weather: bool = True,
) -> FieldObservation:
    # 1) Lot matching (if not explicitly provided).
    lot: Optional[Lot] = None
    if lot_id:
        lot = db.get(Lot, lot_id)
    elif latitude is not None and longitude is not None:
        lot = lot_matching_service.match_lot(db, latitude, longitude)

    # Validation rules: low confidence OR high/critical severity force review.
    high_severity = hermes.severity.value in ("high", "critical")
    needs_review = (
        hermes.needs_human_review or hermes.confidence < 0.75 or high_severity
    )

    obs = FieldObservation(
        user_id=user_id,
        lot_id=lot.id if lot else None,
        farm_id=lot.farm_id if lot else None,
        source_channel=source_channel,
        image_url=image_url,
        thumbnail_url=thumbnail_url,
        original_caption=caption,
        latitude=latitude,
        longitude=longitude,
        observed_at=observed_at or datetime.utcnow(),
        image_type=hermes.image_type.value,
        plant_condition=hermes.plant_condition.value,
        suspected_issue=hermes.suspected_issue,
        diagnosis=hermes.diagnosis or hermes.suspected_issue,
        severity=hermes.severity.value,
        confidence=hermes.confidence,
        visible_symptoms_json=hermes.visible_symptoms,
        ai_summary=hermes.agronomic_summary,
        recommended_next_step=hermes.recommended_next_step,
        needs_human_review=needs_review,
        human_validation_status="pending",
        status="new",
    )
    db.add(obs)
    db.flush()  # assign obs.id

    # 2) Immutable model-output log (never overwritten).
    db.add(
        ModelOutput(
            observation_id=obs.id,
            model_name=model_name,
            raw_json=raw_json,
            confidence=hermes.confidence,
        )
    )

    # 3) Weather enrichment.
    if fetch_weather and latitude is not None and longitude is not None:
        wdata = weather_service.fetch_weather(latitude, longitude, observed_at)
        if wdata:
            db.add(WeatherSnapshot(observation_id=obs.id, **wdata))

    db.flush()
    logger.info(
        "Created observation %s severity=%s lot=%s",
        obs.id,
        obs.severity,
        obs.lot_id,
    )
    return obs


# --------------------------------------------------------------------------- #
# Human-in-the-loop
# --------------------------------------------------------------------------- #
def verify_observation(db: Session, observation_id: int, payload: VerifyRequest) -> FieldObservation:
    obs = db.get(FieldObservation, observation_id)
    if not obs:
        raise ValueError(f"Observation {observation_id} not found")
    obs.human_verified = payload.human_verified
    if payload.lot_id is not None:
        lot = db.get(Lot, payload.lot_id)
        obs.lot_id = payload.lot_id
        obs.farm_id = lot.farm_id if lot else obs.farm_id
    if payload.status:
        obs.status = payload.status
    else:
        obs.status = "verified" if payload.human_verified else obs.status
    obs.needs_human_review = False
    db.flush()
    return obs


def validate_observation(db: Session, observation_id: int, payload) -> FieldObservation:
    """Human validation queue action: confirm / correct / reject.

    Records an immutable ``HumanValidation`` row (training data) and updates the
    observation's validation state. The original ``model_outputs`` are preserved.
    """
    from app.models.database import HumanValidation

    obs = db.get(FieldObservation, observation_id)
    if not obs:
        raise ValueError(f"Observation {observation_id} not found")

    db.add(
        HumanValidation(
            observation_id=obs.id,
            status=payload.status,
            original_diagnosis=obs.diagnosis,
            corrected_label=payload.corrected_label,
            original_confidence=obs.confidence,
            notes=payload.notes,
            validated_by=payload.validated_by,
        )
    )

    obs.human_validation_status = payload.status
    obs.human_verified = payload.status in ("confirmed", "corrected")
    obs.needs_human_review = False
    obs.human_notes = payload.notes
    obs.validated_by = payload.validated_by
    obs.validated_at = datetime.utcnow()

    if payload.status == "corrected":
        if payload.corrected_label:
            obs.human_corrected_label = payload.corrected_label
            obs.diagnosis = payload.corrected_label
        if payload.corrected_severity:
            obs.severity = payload.corrected_severity.value
        obs.status = "corrected"
    elif payload.status == "rejected":
        obs.status = "rejected"
    else:  # confirmed
        obs.status = "verified"

    db.flush()
    logger.info("Observation %s validated as %s by %s",
                observation_id, payload.status, payload.validated_by)
    return obs


def observations_needing_review(db: Session, limit: int = 100) -> list[FieldObservation]:
    return list(
        db.execute(
            select(FieldObservation)
            .where(FieldObservation.needs_human_review.is_(True))
            .where(FieldObservation.human_validation_status == "pending")
            .order_by(FieldObservation.observed_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def correct_observation(db: Session, observation_id: int, payload: CorrectRequest) -> FieldObservation:
    """Store an agronomist correction as training-quality feedback.

    The original AI output in ``model_outputs`` is preserved untouched; we only
    update the working observation fields and record the human note.
    """
    obs = db.get(FieldObservation, observation_id)
    if not obs:
        raise ValueError(f"Observation {observation_id} not found")

    obs.human_correction = payload.human_correction
    obs.human_verified = True
    obs.needs_human_review = False
    obs.status = "corrected"
    if payload.corrected_plant_condition:
        obs.plant_condition = payload.corrected_plant_condition.value
    if payload.corrected_severity:
        obs.severity = payload.corrected_severity.value
    if payload.corrected_suspected_issue is not None:
        obs.suspected_issue = payload.corrected_suspected_issue
    db.flush()
    logger.info("Observation %s corrected by human", observation_id)
    return obs


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #
def get_observation(db: Session, observation_id: int) -> Optional[FieldObservation]:
    return db.execute(
        select(FieldObservation)
        .where(FieldObservation.id == observation_id)
        .options(
            selectinload(FieldObservation.weather_snapshots),
            selectinload(FieldObservation.escalations),
            selectinload(FieldObservation.lot),
        )
    ).scalar_one_or_none()


def list_observations(
    db: Session,
    *,
    severity: Optional[str] = None,
    suspected_issue: Optional[str] = None,
    lot_id: Optional[int] = None,
    needs_review: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[FieldObservation]:
    stmt = select(FieldObservation)
    if severity:
        stmt = stmt.where(FieldObservation.severity == severity)
    if suspected_issue:
        stmt = stmt.where(FieldObservation.suspected_issue == suspected_issue)
    if lot_id:
        stmt = stmt.where(FieldObservation.lot_id == lot_id)
    if needs_review is not None:
        stmt = stmt.where(FieldObservation.needs_human_review == needs_review)
    stmt = stmt.order_by(FieldObservation.observed_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())
