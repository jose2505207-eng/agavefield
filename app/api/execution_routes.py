"""Execution record reads + manual carbon override (staff only)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.rbac import scope_context
from app.db import get_db
from app.models.operations import ExecutionRecord
from app.models.ops_schemas import CarbonOverrideRequest, ExecutionRead
from app.services import execution_service, rbac_service

router = APIRouter(prefix="/api/executions", tags=["executions"])


@router.get("", response_model=list[ExecutionRead])
def list_executions(
    compliance_status: Optional[str] = None,
    work_order_id: Optional[int] = None,
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
    ctx: dict = Depends(scope_context),
):
    """Field-execution board: submitted/approved/etc. records across work orders."""
    stmt = select(ExecutionRecord)
    if compliance_status:
        stmt = stmt.where(ExecutionRecord.compliance_status == compliance_status)
    if work_order_id:
        stmt = stmt.where(ExecutionRecord.work_order_id == work_order_id)
    stmt = stmt.order_by(ExecutionRecord.id.desc()).limit(limit)
    rows = list(db.execute(stmt).scalars().all())
    return rbac_service.filter_executions_by_scope(
        db, ctx["member"], rows, is_demo=ctx["is_demo"]
    )


@router.get("/{execution_id}", response_model=ExecutionRead)
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    er = db.get(ExecutionRecord, execution_id)
    if not er:
        raise HTTPException(404, "Execution record not found")
    return er


@router.post("/{execution_id}/carbon-override")
def carbon_override(execution_id: int, payload: CarbonOverrideRequest, db: Session = Depends(get_db)):
    result = execution_service.override_carbon(
        db, execution_id, value=payload.value, reason=payload.reason, user=payload.user)
    if result is None:
        raise HTTPException(404, "Execution record not found")
    db.commit()
    return result
