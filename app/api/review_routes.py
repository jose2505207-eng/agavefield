"""Review queue + reviewer decision API. Submitted records are never overwritten."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.rbac import scope_context
from app.db import get_db
from app.models.ops_schemas import ExecutionRead, ReviewAction
from app.services import rbac_service, review_service

router = APIRouter(prefix="/api", tags=["review"])


@router.get("/review-queue", response_model=list[ExecutionRead])
def review_queue(limit: int = Query(200, le=500), db: Session = Depends(get_db),
                 ctx: dict = Depends(scope_context)):
    wo_ids = rbac_service.allowed_work_order_ids(db, ctx["member"], is_demo=ctx["is_demo"])
    return review_service.review_queue(db, limit=limit, wo_ids=wo_ids)


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
                       notify: bool = Query(False), db: Session = Depends(get_db)):
    """Request a correction. Pass ``?notify=true`` to re-email the assignee a
    FRESH completion link (rotates the token) so they can resubmit."""
    result = review_service.request_correction(
        db, execution_record_id, reviewer_name=payload.reviewer_name,
        reviewer_id=payload.reviewer_id, reviewer_notes=payload.reviewer_notes,
        correction_due_date=payload.correction_due_date, notify=notify,
    )
    if result is None:
        raise HTTPException(404, "Execution record not found")
    db.commit()
    # Never leak the raw token/link in the API response. In local console mode
    # expose a dev_link for convenience (same policy as the /send endpoint).
    note = result.get("notification")
    if note and "link" in note:
        from app.config import settings

        if settings.email_provider.lower() == "console":
            note["dev_link"] = note.get("link")
        note.pop("token", None)
        note.pop("link", None)
    return result


@router.get("/review/{execution_record_id}/revisions", response_model=list[ExecutionRead])
def revisions(execution_record_id: int, db: Session = Depends(get_db)):
    return review_service.revision_history(db, execution_record_id)
