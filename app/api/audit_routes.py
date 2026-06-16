"""Audit trail read API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import audit_service

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/{entity_type}/{entity_id}")
def audit_history(entity_type: str, entity_id: int, db: Session = Depends(get_db)):
    rows = audit_service.history(db, entity_type, entity_id)
    return [
        {
            "id": r.id,
            "action": r.action,
            "changed_by": r.changed_by,
            "timestamp": r.timestamp,
            "old_values": r.old_values_json,
            "new_values": r.new_values_json,
            "reason": r.reason,
        }
        for r in rows
    ]
