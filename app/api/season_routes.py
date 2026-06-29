"""Season directory API routes (crop cycles / campaigns)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.ops_schemas import SeasonCreate, SeasonRead, SeasonUpdate
from app.services import season_service

router = APIRouter(prefix="/api/seasons", tags=["seasons"])


@router.get("", response_model=list[SeasonRead])
def list_seasons(include_inactive: bool = True, db: Session = Depends(get_db)):
    return season_service.list_seasons(db, include_inactive=include_inactive)


@router.post("", response_model=SeasonRead, status_code=201)
def create_season(payload: SeasonCreate, db: Session = Depends(get_db)):
    obj = season_service.create_season(db, payload.model_dump(exclude_none=True))
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{season_id}", response_model=SeasonRead)
def update_season(season_id: int, payload: SeasonUpdate, db: Session = Depends(get_db)):
    obj = season_service.update_season(db, season_id, payload.model_dump(exclude_none=True))
    if not obj:
        raise HTTPException(404, "Season not found")
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{season_id}")
def delete_season(season_id: int, db: Session = Depends(get_db)):
    result = season_service.delete_or_deactivate_season(db, season_id)
    if result == "not_found":
        raise HTTPException(404, "Season not found")
    db.commit()
    return {"result": result}
