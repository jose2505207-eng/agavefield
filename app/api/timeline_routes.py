"""Timeline read API for field/lot/zone/passport + global feed."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.ops_schemas import TimelineEventRead
from app.services import timeline_service

router = APIRouter(prefix="/api", tags=["timeline"])


@router.get("/timeline", response_model=list[TimelineEventRead])
def global_timeline(entity_type: Optional[str] = None, limit: int = Query(200, le=500),
                    db: Session = Depends(get_db)):
    return timeline_service.recent(db, entity_type=entity_type, limit=limit)


@router.get("/fields/{field_id}/timeline", response_model=list[TimelineEventRead])
def field_timeline(field_id: int, db: Session = Depends(get_db)):
    return timeline_service.for_entity(db, "field", field_id)


@router.get("/lots/{lot_id}/timeline", response_model=list[TimelineEventRead])
def lot_timeline(lot_id: int, db: Session = Depends(get_db)):
    return timeline_service.for_entity(db, "lot", lot_id)


@router.get("/zones/{zone_id}/timeline", response_model=list[TimelineEventRead])
def zone_timeline(zone_id: int, db: Session = Depends(get_db)):
    return timeline_service.for_entity(db, "zone", zone_id)

# Note: /api/passports/{id}/timeline is served by passport_routes (observation
# history). Work-order timeline events are keyed to lot/field, so use those.