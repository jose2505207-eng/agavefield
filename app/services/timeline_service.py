"""Timeline reads — the permanent life history of a field/lot/zone/passport."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operations import TimelineEvent


def for_entity(db: Session, entity_type: str, entity_id: int, limit: int = 200) -> list[TimelineEvent]:
    return list(
        db.execute(
            select(TimelineEvent)
            .where(TimelineEvent.entity_type == entity_type, TimelineEvent.entity_id == entity_id)
            .order_by(TimelineEvent.event_datetime.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def recent(db: Session, entity_type: Optional[str] = None, limit: int = 200) -> list[TimelineEvent]:
    stmt = select(TimelineEvent)
    if entity_type:
        stmt = stmt.where(TimelineEvent.entity_type == entity_type)
    return list(db.execute(stmt.order_by(TimelineEvent.event_datetime.desc()).limit(limit)).scalars().all())
