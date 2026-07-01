"""Work Order API routes (create, list, update, send). Mobile completion +
submission land in a later increment."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.rbac import scope_context
from app.db import get_db
from app.models.ops_schemas import (
    WorkOrderCreate,
    WorkOrderDetail,
    WorkOrderItemRead,
    WorkOrderRead,
    WorkOrderUpdate,
)
from app.services import rbac_service, work_order_service

router = APIRouter(prefix="/api/work-orders", tags=["work-orders"])


def _detail(db: Session, wo) -> WorkOrderDetail:
    d = WorkOrderDetail.model_validate(wo)
    d.items = [WorkOrderItemRead.model_validate(i) for i in work_order_service.get_items(db, wo.id)]
    return d


@router.get("", response_model=list[WorkOrderRead])
def list_work_orders(status: Optional[str] = None, limit: int = Query(200, le=500),
                     db: Session = Depends(get_db),
                     ctx: dict = Depends(scope_context)):
    rows = work_order_service.list_work_orders(db, status=status, limit=limit)
    # Authoritative data-visibility filter: a logged-in member only ever receives
    # rows their data_scope allows. No membership (open / API-key mode) → unchanged.
    return rbac_service.filter_work_orders_by_scope(
        ctx["member"], rows, is_demo=ctx["is_demo"]
    )


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


@router.post("/{work_order_id}/duplicate", response_model=WorkOrderDetail, status_code=201)
def duplicate_work_order(work_order_id: int, db: Session = Depends(get_db)):
    wo = work_order_service.duplicate_work_order(db, work_order_id)
    if not wo:
        raise HTTPException(404, "Work order not found")
    db.commit()
    db.refresh(wo)
    return _detail(db, wo)


@router.post("/{work_order_id}/link")
def generate_work_order_link(work_order_id: int, db: Session = Depends(get_db)):
    """Generate (or refresh) a shareable completion link without sending email.

    Use for manual delivery (WhatsApp, QR, printout). The link opens the mobile
    completion page with the work order's checklist tasks and photo-upload fields.
    Rotates the token, so any previously issued link stops working.
    """
    result = work_order_service.generate_link(db, work_order_id)
    if result is None:
        raise HTTPException(404, "Work order not found")
    db.commit()
    return result


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
