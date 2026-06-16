"""Map / zone overview API routes.

Returns API-ready markers (one per passport/zone with its latest observation).
A simple structure now; a richer GIS layer can replace it later without
changing the response contract.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.database import AgavePassport, FieldObservation
from app.models.schemas import ZoneMapPoint

router = APIRouter(prefix="/api/map", tags=["map"])


@router.get("/zones", response_model=list[ZoneMapPoint])
def zone_markers(db: Session = Depends(get_db)):
    passports = list(
        db.execute(
            select(AgavePassport).where(
                AgavePassport.latitude.is_not(None), AgavePassport.longitude.is_not(None)
            )
        )
        .scalars()
        .all()
    )
    points: list[ZoneMapPoint] = []
    for p in passports:
        latest = db.execute(
            select(FieldObservation)
            .where(FieldObservation.passport_id == p.id)
            .order_by(FieldObservation.observed_at.desc())
            .limit(1)
        ).scalars().first()
        points.append(
            ZoneMapPoint(
                field_name=p.field_name,
                lot_name=p.lot_name,
                zone_name=p.zone_name,
                latitude=p.latitude,
                longitude=p.longitude,
                severity=(latest.event_type if latest else "observation"),
                status=p.health_status,
                latest_photo=(latest.thumbnail_url or latest.image_url) if latest else None,
                latest_observation=(latest.manual_note or latest.original_caption) if latest else None,
                inspection_date=p.last_inspection_at,
                passport_id=p.id,
            )
        )
    return points
