"""Weekly report API routes (on-demand)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/weekly")
def get_weekly(
    scope_type: str = Query("all"),
    scope_id: Optional[int] = None,
    regenerate: bool = False,
    db: Session = Depends(get_db),
):
    """Return the latest stored report, or generate one on demand."""
    if not regenerate:
        existing = report_service.latest_report(db, scope_type, scope_id)
        if existing:
            return existing
    return report_service.generate_weekly_report(db, scope_type=scope_type, scope_id=scope_id)


@router.post("/weekly/generate")
def generate_weekly(
    scope_type: str = Query("all"),
    scope_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    report = report_service.generate_weekly_report(
        db, scope_type=scope_type, scope_id=scope_id, persist=True
    )
    db.commit()
    return report
