"""System readiness / environment status (staff-only; no secrets exposed)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.rbac import scope_context
from app.db import get_db
from app.services import rbac_service, system_status_service

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
def system_status(db: Session = Depends(get_db), ctx: dict = Depends(scope_context)):
    wo_ids = rbac_service.allowed_work_order_ids(db, ctx["member"], is_demo=ctx["is_demo"])
    return system_status_service.status(db, wo_ids=wo_ids)
