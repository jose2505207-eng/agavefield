"""Observation API routes."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agents import hermes_agent
from app.db import get_db
from app.models.database import FieldObservation
from app.models.schemas import (
    CorrectRequest,
    HermesInput,
    ObservationCreate,
    ObservationDetail,
    ObservationRead,
    ValidateRequest,
    VerifyRequest,
    WeatherRead,
)
from app.services import escalation_service, observation_service

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
def create_observation(payload: ObservationCreate, db: Session = Depends(get_db)):
    """Create an observation from an image URL by running the Hermes pipeline."""
    if not payload.image_url:
        raise HTTPException(400, "image_url is required")
    result = hermes_agent.run(
        db,
        HermesInput(
            image_url=payload.image_url,
            caption=payload.original_caption,
            user_id=payload.user_id,
            source_channel=payload.source_channel,
            latitude=payload.latitude,
            longitude=payload.longitude,
            timestamp=payload.observed_at,
            lot_id=payload.lot_id,
        ),
    )
    obs = observation_service.get_observation(db, result.observation.id)
    return _to_detail(obs)


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
