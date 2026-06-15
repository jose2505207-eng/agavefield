"""Lot API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.database import Lot
from app.models.schemas import LotCreate, LotRead, ObservationRead
from app.services import observation_service

router = APIRouter(prefix="/lots", tags=["lots"])


@router.get("", response_model=list[LotRead])
def list_lots(db: Session = Depends(get_db)):
    return list(db.execute(select(Lot).order_by(Lot.lot_code)).scalars().all())


@router.post("", response_model=LotRead, status_code=201)
def create_lot(payload: LotCreate, db: Session = Depends(get_db)):
    lot = Lot(**payload.model_dump())
    db.add(lot)
    db.commit()
    db.refresh(lot)
    return lot


@router.get("/{lot_id}", response_model=LotRead)
def get_lot(lot_id: int, db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Lot not found")
    return lot


@router.get("/{lot_id}/observations", response_model=list[ObservationRead])
def lot_observations(lot_id: int, db: Session = Depends(get_db)):
    if not db.get(Lot, lot_id):
        raise HTTPException(404, "Lot not found")
    return observation_service.list_observations(db, lot_id=lot_id, limit=200)
