"""Execution record reads + manual carbon override (staff only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.operations import ExecutionRecord
from app.models.ops_schemas import CarbonOverrideRequest, ExecutionRead
from app.services import execution_service

router = APIRouter(prefix="/api/executions", tags=["executions"])


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
