"""Alert API routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.database import Alert, FieldObservation
from app.models.schemas import AlertRead, EscalateRequest
from app.services import notification_service

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertRead])
def list_alerts(
    severity: Optional[str] = None,
    unread_only: bool = False,
    limit: int = Query(100, le=300),
    db: Session = Depends(get_db),
):
    stmt = select(Alert)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if unread_only:
        stmt = stmt.where(Alert.read.is_(False))
    stmt = stmt.order_by(Alert.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


@router.post("/escalate", response_model=AlertRead, status_code=201)
def escalate(payload: EscalateRequest, db: Session = Depends(get_db)):
    """Manual escalation: raise an alert on demand (human-requested)."""
    obs = db.get(FieldObservation, payload.observation_id) if payload.observation_id else None
    title = payload.title or "Manual escalation"
    message = payload.message or (obs.ai_summary if obs else "Manual escalation requested.")
    alert = notification_service.create_alert(
        db,
        title=title,
        message=message or "Manual escalation requested.",
        severity=payload.severity,
        reason="Manual escalation",
        channel=payload.channel,
        recipient=payload.recipient,
        passport_id=payload.passport_id or (obs.passport_id if obs else None),
        observation_id=payload.observation_id,
    )
    db.commit()
    db.refresh(alert)
    return alert


@router.patch("/{alert_id}/read", response_model=AlertRead)
def mark_read(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.read = True
    db.commit()
    db.refresh(alert)
    return alert
