"""Review queue + reviewer decision API. Submitted records are never overwritten."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.ops_schemas import ExecutionRead, ReviewAction
from app.services import review_service

router = APIRouter(prefix="/api", tags=["review"])


@router.get("/review-queue", response_model=list[ExecutionRead])
def review_queue(limit: int = Query(200, le=500), db: Session = Depends(get_db)):
    return review_service.review_queue(db, limit=limit)


def _act(fn, execution_record_id: int, payload: ReviewAction, db: Session):
    result = fn(
        db, execution_record_id,
        reviewer_name=payload.reviewer_name, reviewer_id=payload.reviewer_id,
        reviewer_notes=payload.reviewer_notes,
    )
    if result is None:
        raise HTTPException(404, "Execution record not found")
    db.commit()
    return result


@router.post("/review/{execution_record_id}/approve")
def approve(execution_record_id: int, payload: ReviewAction = Body(default=ReviewAction()),
            db: Session = Depends(get_db)):
    return _act(review_service.approve, execution_record_id, payload, db)


@router.post("/review/{execution_record_id}/reject")
def reject(execution_record_id: int, payload: ReviewAction = Body(default=ReviewAction()),
           db: Session = Depends(get_db)):
    return _act(review_service.reject, execution_record_id, payload, db)


@router.post("/review/{execution_record_id}/request-correction")
def request_correction(execution_record_id: int, payload: ReviewAction = Body(default=ReviewAction()),
                       db: Session = Depends(get_db)):
    result = review_service.request_correction(
        db, execution_record_id, reviewer_name=payload.reviewer_name,
        reviewer_id=payload.reviewer_id, reviewer_notes=payload.reviewer_notes,
        correction_due_date=payload.correction_due_date,
    )
    if result is None:
        raise HTTPException(404, "Execution record not found")
    db.commit()
    return result


@router.get("/review/{execution_record_id}/revisions", response_model=list[ExecutionRead])
def revisions(execution_record_id: int, db: Session = Depends(get_db)):
    return review_service.revision_history(db, execution_record_id)
