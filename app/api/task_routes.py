"""Task API routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.schemas import TaskCreate, TaskRead, TaskUpdateRequest
from app.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    passport_id: Optional[int] = None,
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
):
    return task_service.list_tasks(
        db, status=status, priority=priority, passport_id=passport_id, limit=limit
    )


@router.post("", response_model=TaskRead, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = task_service.create_task(db, **payload.model_dump())
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdateRequest, db: Session = Depends(get_db)):
    task = task_service.update_task(db, task_id, **payload.model_dump())
    if not task:
        raise HTTPException(404, "Task not found")
    db.commit()
    db.refresh(task)
    return task


@router.get("/queue/overdue", response_model=list[TaskRead])
def overdue_tasks(db: Session = Depends(get_db)):
    return task_service.overdue_tasks(db)
