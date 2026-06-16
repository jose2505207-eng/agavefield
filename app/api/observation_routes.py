"""Observation API routes."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agents import hermes_agent
from app.config import settings
from app.db import get_db
from app.models.database import FieldObservation
from app.models.schemas import (
    CorrectRequest,
    EvidenceRecordCreate,
    FieldNoteReview,
    HermesInput,
    ObservationDetail,
    ObservationRead,
    ValidateRequest,
    VerifyRequest,
    WeatherRead,
)
from app.services import observation_service

logger = logging.getLogger("agave.api.observations")
router = APIRouter(prefix="/observations", tags=["observations"])


def _to_detail(obs: FieldObservation) -> ObservationDetail:
    detail = ObservationDetail.model_validate(obs)
    if obs.weather_snapshots:
        detail.weather = WeatherRead.model_validate(obs.weather_snapshots[-1])
    detail.escalations = [e for e in obs.escalations]  # type: ignore[assignment]
    return detail


@router.get("", response_model=list[ObservationRead])
def list_observations(
    severity: Optional[str] = None,
    suspected_issue: Optional[str] = None,
    lot_id: Optional[int] = None,
    needs_review: Optional[bool] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return observation_service.list_observations(
        db,
        severity=severity,
        suspected_issue=suspected_issue,
        lot_id=lot_id,
        needs_review=needs_review,
        limit=limit,
        offset=offset,
    )


@router.get("/{observation_id}", response_model=ObservationDetail)
def get_observation(observation_id: int, db: Session = Depends(get_db)):
    obs = observation_service.get_observation(db, observation_id)
    if not obs:
        raise HTTPException(404, "Observation not found")
    return _to_detail(obs)


@router.post("", response_model=ObservationDetail, status_code=201)
def create_observation(payload: EvidenceRecordCreate, db: Session = Depends(get_db)):
    """Create a human-entered field record (MVP). A manual note is required and
    NO LLM/CV is invoked. If ENABLE_AI_IMAGE_ANALYSIS is on (V2), the image is
    additionally run through the Hermes pipeline."""
    obs = observation_service.create_evidence_record(
        db,
        manual_note=payload.manual_note,
        event_type=payload.event_type.value,
        process_type=payload.process_type,
        responsible_person=payload.responsible_person,
        follow_up_needed=payload.follow_up_needed,
        follow_up_date=payload.follow_up_date,
        lot_id=payload.lot_id,
        passport_id=payload.passport_id,
        image_url=payload.image_url,
        thumbnail_url=payload.thumbnail_url,
        latitude=payload.latitude,
        longitude=payload.longitude,
        observed_at=payload.observed_at,
        source_channel=payload.source_channel,
        user_id=payload.user_id,
    )
    if settings.enable_ai_image_analysis and payload.image_url:
        hermes_agent.run(
            db,
            HermesInput(
                image_url=payload.image_url,
                caption=payload.manual_note,
                user_id=payload.user_id,
                source_channel=payload.source_channel,
                latitude=payload.latitude,
                longitude=payload.longitude,
                timestamp=payload.observed_at,
                lot_id=payload.lot_id,
            ),
        )
    db.commit()
    obs = observation_service.get_observation(db, obs.id)
    return _to_detail(obs)


@router.get("/queue/review", response_model=list[ObservationRead])
def field_notes_review_queue(limit: int = Query(100, le=300), db: Session = Depends(get_db)):
    """Field Notes Review queue: human records awaiting supervisor review."""
    return observation_service.records_pending_review(db, limit=limit)


@router.patch("/{observation_id}/review", response_model=ObservationRead)
def review_record(observation_id: int, payload: FieldNoteReview, db: Session = Depends(get_db)):
    try:
        obs = observation_service.review_record(db, observation_id, payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    db.commit()
    db.refresh(obs)
    return obs


@router.patch("/{observation_id}/verify", response_model=ObservationRead)
def verify_observation(observation_id: int, payload: VerifyRequest, db: Session = Depends(get_db)):
    try:
        obs = observation_service.verify_observation(db, observation_id, payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    db.commit()
    db.refresh(obs)
    return obs


@router.get("/queue/needs-review", response_model=list[ObservationRead])
def needs_review_queue(limit: int = Query(100, le=300), db: Session = Depends(get_db)):
    """Human validation queue: low-confidence or high-severity observations."""
    return observation_service.observations_needing_review(db, limit=limit)


@router.patch("/{observation_id}/validate", response_model=ObservationRead)
def validate_observation(observation_id: int, payload: ValidateRequest, db: Session = Depends(get_db)):
    try:
        obs = observation_service.validate_observation(db, observation_id, payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    db.commit()
    db.refresh(obs)
    return obs


@router.patch("/{observation_id}/correct", response_model=ObservationRead)
def correct_observation(observation_id: int, payload: CorrectRequest, db: Session = Depends(get_db)):
    try:
        obs = observation_service.correct_observation(db, observation_id, payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    db.commit()
    db.refresh(obs)
    return obs


@router.post("/{observation_id}/escalate", response_model=ObservationDetail)
def escalate_observation(observation_id: int, db: Session = Depends(get_db)):
    """Manual escalation (bypasses rule evaluation, still recorded)."""
    obs = observation_service.get_observation(db, observation_id)
    if not obs:
        raise HTTPException(404, "Observation not found")
    # Reconstruct a minimal HermesOutput view for the message builder.
    from app.models.schemas import HermesOutput
    from app.services import escalation_service

    hermes_view = HermesOutput(
        severity=obs.severity,
        suspected_issue=obs.suspected_issue,
        confidence=obs.confidence,
        agronomic_summary=obs.ai_summary or "",
        recommended_next_step=obs.recommended_next_step or "",
    )
    escalation_service.maybe_escalate(db, obs, hermes_view, obs.original_caption, force=True)
    db.commit()
    obs = observation_service.get_observation(db, observation_id)
    return _to_detail(obs)
