"""Agave Passport API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.schemas import (
    ObservationRead,
    PassportCreate,
    PassportDetail,
    PassportRead,
    PassportUpdate,
    TaskRead,
)
from app.services import comparison_service, passport_service

router = APIRouter(prefix="/api/passports", tags=["passports"])


@router.get("", response_model=list[PassportRead])
def list_passports(db: Session = Depends(get_db)):
    return passport_service.list_passports(db)


@router.post("", response_model=PassportRead, status_code=201)
def create_passport(payload: PassportCreate, db: Session = Depends(get_db)):
    p = passport_service.create_passport(db, **payload.model_dump())
    db.commit()
    db.refresh(p)
    return p


@router.get("/{passport_id}", response_model=PassportDetail)
def get_passport(passport_id: int, db: Session = Depends(get_db)):
    p = passport_service.get_passport(db, passport_id)
    if not p:
        raise HTTPException(404, "Passport not found")
    detail = PassportDetail.model_validate(p)
    detail.observations = [ObservationRead.model_validate(o) for o in p.observations]
    detail.tasks = [TaskRead.model_validate(t) for t in p.tasks]
    return detail


@router.patch("/{passport_id}", response_model=PassportRead)
def update_passport(passport_id: int, payload: PassportUpdate, db: Session = Depends(get_db)):
    p = passport_service.update_passport(db, passport_id, **payload.model_dump())
    if not p:
        raise HTTPException(404, "Passport not found")
    db.commit()
    db.refresh(p)
    return p


@router.get("/{passport_id}/photos/compare")
def compare_photos(passport_id: int, db: Session = Depends(get_db)):
    if not passport_service.get_passport(db, passport_id):
        raise HTTPException(404, "Passport not found")
    return comparison_service.compare_passport_photos(db, passport_id)


@router.get("/{passport_id}/timeline", response_model=list[ObservationRead])
def passport_timeline(passport_id: int, db: Session = Depends(get_db)):
    """Chronological human-entered record history for this passport (oldest first)."""
    p = passport_service.get_passport(db, passport_id)
    if not p:
        raise HTTPException(404, "Passport not found")
    records = sorted(p.observations, key=lambda o: o.observed_at or o.created_at)
    return [ObservationRead.model_validate(o) for o in records]
