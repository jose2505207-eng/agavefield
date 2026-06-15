"""Dashboard API routes (overview, gallery, lot risk, map points)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.schemas import MapPoint, ObservationRead
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    return dashboard_service.summary(db)


@router.get("/recent-observations", response_model=list[ObservationRead])
def recent(limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    return dashboard_service.recent_observations(db, limit=limit)


@router.get("/gallery", response_model=list[ObservationRead])
def gallery(
    lot_id: Optional[int] = None,
    severity: Optional[str] = None,
    suspected_issue: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(60, le=200),
    db: Session = Depends(get_db),
):
    return dashboard_service.gallery(
        db,
        lot_id=lot_id,
        severity=severity,
        suspected_issue=suspected_issue,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


@router.get("/lot-risk-ranking")
def lot_risk_ranking(limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    return dashboard_service.lot_risk_ranking(db, limit=limit)


@router.get("/map-points", response_model=list[MapPoint])
def map_points(db: Session = Depends(get_db)):
    return dashboard_service.map_points(db)
