"""CRUD for the Season directory (crop cycles / campaigns).

History-safe: seasons referenced by work orders are never hard deleted — they
are deactivated. Every mutation is written to the audit log. Mirrors the
patterns in app/services/catalog_service.py.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.operations import Season, WorkOrder
from app.services import audit_service

logger = logging.getLogger("agave.season")


def _create(db: Session, data: dict, actor: Optional[str]) -> Season:
    obj = Season(**{k: v for k, v in data.items() if v is not None})
    db.add(obj)
    db.flush()
    audit_service.log(db, entity_type="season", entity_id=obj.id, action="create",
                      new_values=data, changed_by=actor or data.get("created_by"))
    return obj


def _update(db: Session, obj: Season, data: dict, actor: Optional[str]) -> Season:
    old = {k: getattr(obj, k) for k in data if hasattr(obj, k)}
    for k, v in data.items():
        if v is not None and hasattr(obj, k):
            setattr(obj, k, v)
    db.flush()
    audit_service.log(db, entity_type="season", entity_id=obj.id, action="update",
                      old_values=old, new_values=data, changed_by=actor)
    return obj


def list_seasons(db: Session, include_inactive: bool = True) -> list[Season]:
    stmt = select(Season)
    if not include_inactive:
        stmt = stmt.where(Season.active.is_(True))
    return list(db.execute(stmt.order_by(Season.name)).scalars().all())


def get_season(db: Session, season_id: int) -> Optional[Season]:
    return db.get(Season, season_id)


def create_season(db: Session, data: dict, actor: Optional[str] = None) -> Season:
    return _create(db, data, actor)


def update_season(db: Session, season_id: int, data: dict, actor: Optional[str] = None) -> Optional[Season]:
    obj = db.get(Season, season_id)
    if not obj:
        return None
    return _update(db, obj, data, actor)


def delete_or_deactivate_season(db: Session, season_id: int, actor: Optional[str] = None) -> str:
    obj = db.get(Season, season_id)
    if not obj:
        return "not_found"
    # WorkOrder.season_id is a plain Integer that logically references seasons.id.
    refs = db.scalar(select(func.count(WorkOrder.id)).where(WorkOrder.season_id == season_id)) or 0
    if refs > 0:
        obj.active = False
        db.flush()
        audit_service.log(db, entity_type="season", entity_id=season_id, action="deactivate",
                          changed_by=actor, reason="has linked work orders")
        return "deactivated"
    audit_service.log(db, entity_type="season", entity_id=season_id, action="soft_delete", changed_by=actor)
    db.delete(obj)
    db.flush()
    return "deleted"
