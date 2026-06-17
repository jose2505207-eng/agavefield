"""System readiness / environment status (staff-only; no secrets exposed)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import system_status_service

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
def system_status(db: Session = Depends(get_db)):
    return system_status_service.status(db)
