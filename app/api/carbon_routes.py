"""Carbon reporting API — reads stored snapshots only (no recompute)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import carbon_report_service as carbon

router = APIRouter(prefix="/api/carbon", tags=["carbon"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    return carbon.summary(db)


@router.get("/by-season")
def by_season(db: Session = Depends(get_db)):
    return carbon.by_season(db)


@router.get("/by-activity")
def by_activity(db: Session = Depends(get_db)):
    return carbon.by_activity(db)


@router.get("/by-product")
def by_product(db: Session = Depends(get_db)):
    return carbon.by_product(db)


@router.get("/by-lot")
def by_lot(db: Session = Depends(get_db)):
    return carbon.by_lot(db)


@router.get("/by-field")
def by_field(db: Session = Depends(get_db)):
    return carbon.by_field(db)


@router.get("/missing-data")
def missing_data(db: Session = Depends(get_db)):
    return carbon.missing_data_report(db)


@router.get("/overrides")
def overrides(db: Session = Depends(get_db)):
    return carbon.override_report(db)
