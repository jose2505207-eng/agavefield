"""Audit trail (FDA-style). Records every important create/update/review/send
action with before/after values and actor identity. Append-only by design.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operations import AuditLog

logger = logging.getLogger("agave.audit")


def log(
    db: Session,
    *,
    entity_type: str,
    entity_id: Optional[int],
    action: str,
    new_values: Optional[dict] = None,
    old_values: Optional[dict] = None,
    changed_by: Optional[str] = None,
    changed_by_email: Optional[str] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        new_values_json=_jsonable(new_values),
        old_values_json=_jsonable(old_values),
        changed_by=changed_by,
        changed_by_email=changed_by_email,
        reason=reason,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(entry)
    db.flush()
    return entry


def _jsonable(values: Optional[dict]) -> Optional[dict]:
    """Coerce values to JSON-safe primitives (datetimes -> iso)."""
    if not values:
        return values
    out = {}
    for k, v in values.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif isinstance(v, (str, int, float, bool, type(None), list, dict)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


def history(db: Session, entity_type: str, entity_id: int, limit: int = 200) -> list[AuditLog]:
    return list(
        db.execute(
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
