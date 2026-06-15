"""Tasks: AI-recommended follow-ups + human-managed work items.

Hermes can create tasks automatically, but any task flagged ``needs_approval``
(treatments / expensive or irreversible actions) stays gated until a human
approves it — dangerous actions are never auto-executed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import AgavePassport, FieldObservation, Task
from app.models.schemas import RecommendedTask

logger = logging.getLogger("agave.tasks")

# Tasks whose titles imply an expensive/irreversible action need approval even
# if the model forgot to flag them.
_APPROVAL_KEYWORDS = ("apply", "treatment", "spray", "pesticid", "herbicid", "fungicid", "aplica")


def _needs_approval(title: str, flagged: bool) -> bool:
    if flagged:
        return True
    low = (title or "").lower()
    return any(k in low for k in _APPROVAL_KEYWORDS)


def create_tasks_from_recommendations(
    db: Session,
    recommendations: list[RecommendedTask],
    *,
    observation: Optional[FieldObservation] = None,
    passport: Optional[AgavePassport] = None,
) -> list[Task]:
    created: list[Task] = []
    base = (observation.observed_at if observation else None) or datetime.utcnow()
    for rec in recommendations:
        due = base + timedelta(days=rec.due_in_days) if rec.due_in_days is not None else None
        needs_approval = _needs_approval(rec.title, rec.needs_approval)
        task = Task(
            passport_id=passport.id if passport else None,
            observation_id=observation.id if observation else None,
            title=rec.title,
            description=rec.description,
            priority=rec.priority.value,
            status="open",
            due_date=due,
            source="ai_generated",
            needs_approval=needs_approval,
            approved=not needs_approval,  # auto-approved unless it's a dangerous action
        )
        db.add(task)
        created.append(task)
    db.flush()
    if created:
        logger.info("Created %d AI task(s) for observation %s", len(created),
                    observation.id if observation else None)
    return created


def create_task(db: Session, **fields) -> Task:
    if "priority" in fields and hasattr(fields["priority"], "value"):
        fields["priority"] = fields["priority"].value
    needs_approval = fields.get("needs_approval", False)
    fields.setdefault("approved", not needs_approval)
    task = Task(**{k: v for k, v in fields.items() if v is not None})
    db.add(task)
    db.flush()
    return task


def update_task(db: Session, task_id: int, **fields) -> Optional[Task]:
    task = db.get(Task, task_id)
    if not task:
        return None
    for k, v in fields.items():
        if v is None:
            continue
        setattr(task, k, v.value if hasattr(v, "value") else v)
    db.flush()
    return task


def list_tasks(
    db: Session,
    *,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    passport_id: Optional[int] = None,
    limit: int = 200,
) -> list[Task]:
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    if priority:
        stmt = stmt.where(Task.priority == priority)
    if passport_id:
        stmt = stmt.where(Task.passport_id == passport_id)
    stmt = stmt.order_by(Task.due_date.is_(None), Task.due_date.asc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def overdue_tasks(db: Session) -> list[Task]:
    now = datetime.utcnow()
    return list(
        db.execute(
            select(Task).where(
                Task.due_date.is_not(None),
                Task.due_date < now,
                Task.status.in_(("open", "in_progress")),
            )
        )
        .scalars()
        .all()
    )
