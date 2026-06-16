"""Work Order API routes (create, list, update, send). Mobile completion +
submission land in a later increment."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.ops_schemas import (
    WorkOrderCreate,
    WorkOrderDetail,
    WorkOrderItemRead,
    WorkOrderRead,
    WorkOrderUpdate,
)
from app.services import work_order_service

router = APIRouter(prefix="/api/work-orders", tags=["work-orders"])


def _detail(db: Session, wo) -> WorkOrderDetail:
    d = WorkOrderDetail.model_validate(wo)
    d.items = [WorkOrderItemRead.model_validate(i) for i in work_order_service.get_items(db, wo.id)]
    return d


@router.get("", response_model=list[WorkOrderRead])
def list_work_orders(status: Optional[str] = None, limit: int = Query(200, le=500),
                     db: Session = Depends(get_db)):
    return work_order_service.list_work_orders(db, status=status, limit=limit)


@router.get("/{work_order_id}", response_model=WorkOrderDetail)
def get_work_order(work_order_id: int, db: Session = Depends(get_db)):
    wo = work_order_service.get_work_order(db, work_order_id)
    if not wo or wo.deleted_at is not None:
        raise HTTPException(404, "Work order not found")
    return _detail(db, wo)


@router.post("", response_model=WorkOrderDetail, status_code=201)
def create_work_order(payload: WorkOrderCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"items"}, exclude_none=True)
    items = [i.model_dump() for i in payload.items]
    if not items:
        raise HTTPException(400, "A work order needs at least one checklist item")
    wo = work_order_service.create_work_order(db, data, items, actor=payload.created_by)
    db.commit()
    db.refresh(wo)
    return _detail(db, wo)


@router.patch("/{work_order_id}", response_model=WorkOrderRead)
def update_work_order(work_order_id: int, payload: WorkOrderUpdate, db: Session = Depends(get_db)):
    wo = work_order_service.update_work_order(db, work_order_id, payload.model_dump(exclude_none=True))
    if not wo:
        raise HTTPException(404, "Work order not found")
    db.commit()
    db.refresh(wo)
    return wo


@router.post("/{work_order_id}/send")
def send_work_order(work_order_id: int, db: Session = Depends(get_db)):
    from app.config import settings

    result = work_order_service.send_work_order(db, work_order_id)
    if result is None:
        raise HTTPException(404, "Work order not found")
    if result.get("error") == "no_recipient":
        raise HTTPException(400, "Work order has no assignee email")
    db.commit()
    # Only expose the raw link/token in local console (dev) mode — never in prod.
    safe = {k: v for k, v in result.items() if k not in ("token", "link")}
    if settings.email_provider.lower() == "console":
        safe["dev_link"] = result["link"]
    return safe
