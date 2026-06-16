"""Assignee directory API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.ops_schemas import AssigneeCreate, AssigneeRead, AssigneeUpdate
from app.services import catalog_service

router = APIRouter(prefix="/api/assignees", tags=["assignees"])


@router.get("", response_model=list[AssigneeRead])
def list_assignees(include_inactive: bool = True, db: Session = Depends(get_db)):
    return catalog_service.list_assignees(db, include_inactive=include_inactive)


@router.post("", response_model=AssigneeRead, status_code=201)
def create_assignee(payload: AssigneeCreate, db: Session = Depends(get_db)):
    obj = catalog_service.create_assignee(db, payload.model_dump(exclude_none=True))
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{assignee_id}", response_model=AssigneeRead)
def update_assignee(assignee_id: int, payload: AssigneeUpdate, db: Session = Depends(get_db)):
    obj = catalog_service.update_assignee(db, assignee_id, payload.model_dump(exclude_none=True))
    if not obj:
        raise HTTPException(404, "Assignee not found")
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{assignee_id}")
def delete_assignee(assignee_id: int, db: Session = Depends(get_db)):
    result = catalog_service.delete_or_deactivate_assignee(db, assignee_id)
    if result == "not_found":
        raise HTTPException(404, "Assignee not found")
    db.commit()
    return {"result": result}
