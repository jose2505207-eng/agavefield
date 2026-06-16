"""Review queue + reviewer decisions.

A reviewer approves / rejects / requests correction on a submitted
ExecutionRecord. The submitted record is NEVER overwritten — a `Review` row
captures the decision, reviewer identity, notes, and timestamp. Corrections
flag the record; the worker's re-submission forms a revision chain via
ExecutionRecord.is_revision_of_id (set in execution_service).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operations import (
    ExecutionRecord,
    Review,
    TimelineEvent,
    WorkOrder,
    WorkOrderItem,
)
from app.services import audit_service

logger = logging.getLogger("agave.review")

_OPEN = ("pending_review", "needs_correction")


def review_queue(db: Session, limit: int = 200) -> list[ExecutionRecord]:
    return list(
        db.execute(
            select(ExecutionRecord)
            .where(ExecutionRecord.compliance_status.in_(_OPEN))
            .order_by(ExecutionRecord.submitted_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def _timeline_for_execution(db: Session, er: ExecutionRecord, event_type: str, title: str,
                            reviewer: Optional[str]) -> None:
    wo = db.get(WorkOrder, er.work_order_id)
    entity_id = (wo.lot_id or wo.field_id) if wo else None
    if not entity_id:
        return
    db.add(TimelineEvent(
        entity_type="lot" if (wo and wo.lot_id) else "field", entity_id=entity_id,
        event_type=event_type, title=title, event_datetime=datetime.utcnow(),
        related_work_order_id=er.work_order_id, related_execution_record_id=er.id,
        related_activity_id=er.activity_id, carbon_kgco2e=er.actual_carbon_kgco2e,
        created_by=reviewer,
    ))


def _decide(
    db: Session,
    execution_id: int,
    *,
    review_status: str,
    compliance_status: str,
    item_status: str,
    timeline_event: Optional[str],
    timeline_title: str,
    reviewer_name: Optional[str],
    reviewer_id: Optional[int],
    reviewer_notes: Optional[str],
    correction_requested: bool = False,
    correction_due_date: Optional[datetime] = None,
) -> Optional[dict]:
    er = db.get(ExecutionRecord, execution_id)
    if not er:
        return None

    review = Review(
        execution_record_id=er.id, review_status=review_status,
        reviewer_id=reviewer_id, reviewer_name=reviewer_name, reviewer_notes=reviewer_notes,
        correction_requested=correction_requested, correction_due_date=correction_due_date,
        reviewed_at=datetime.utcnow(),
    )
    db.add(review)

    # Update derived state only — never the submitted execution data itself.
    er.compliance_status = compliance_status
    item = db.get(WorkOrderItem, er.work_order_item_id)
    if item:
        item.status = item_status

    action = {"approve": "approve", "reject": "reject",
              "needs_correction": "request_correction"}[
        "approve" if review_status == "approved" else
        "reject" if review_status == "rejected" else "needs_correction"]
    db.flush()
    audit_service.log(db, entity_type="execution_record", entity_id=er.id, action=action,
                      new_values={"review_status": review_status,
                                  "compliance_status": compliance_status},
                      changed_by=reviewer_name, reason=reviewer_notes)
    if timeline_event:
        _timeline_for_execution(db, er, timeline_event, timeline_title, reviewer_name)
    db.flush()
    return {"execution_record_id": er.id, "review_id": review.id,
            "compliance_status": er.compliance_status, "review_status": review_status}


def approve(db, execution_id, *, reviewer_name=None, reviewer_id=None, reviewer_notes=None):
    return _decide(db, execution_id, review_status="approved", compliance_status="compliant",
                   item_status="approved", timeline_event="activity_approved",
                   timeline_title="Activity approved", reviewer_name=reviewer_name,
                   reviewer_id=reviewer_id, reviewer_notes=reviewer_notes)


def reject(db, execution_id, *, reviewer_name=None, reviewer_id=None, reviewer_notes=None):
    return _decide(db, execution_id, review_status="rejected", compliance_status="non_compliant",
                   item_status="rejected", timeline_event=None, timeline_title="Activity rejected",
                   reviewer_name=reviewer_name, reviewer_id=reviewer_id, reviewer_notes=reviewer_notes)


def request_correction(db, execution_id, *, reviewer_name=None, reviewer_id=None,
                       reviewer_notes=None, correction_due_date=None):
    return _decide(db, execution_id, review_status="needs_correction",
                   compliance_status="needs_correction", item_status="needs_correction",
                   timeline_event="correction_requested", timeline_title="Correction requested",
                   reviewer_name=reviewer_name, reviewer_id=reviewer_id,
                   reviewer_notes=reviewer_notes, correction_requested=True,
                   correction_due_date=correction_due_date)


def revision_history(db: Session, execution_id: int) -> list[ExecutionRecord]:
    """Walk the is_revision_of chain (oldest → newest) for an execution."""
    er = db.get(ExecutionRecord, execution_id)
    if not er:
        return []
    chain = [er]
    cur = er
    while cur.is_revision_of_id:
        prev = db.get(ExecutionRecord, cur.is_revision_of_id)
        if not prev:
            break
        chain.append(prev)
        cur = prev
    return list(reversed(chain))
