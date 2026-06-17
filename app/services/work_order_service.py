"""Work-order lifecycle: create (with locked carbon snapshots) and secure send.

Carbon factors are copied onto each WorkOrderItem at creation time as an
immutable snapshot — later catalog changes never mutate existing work orders.
Sending generates a random token, stores only its SHA-256 hash, and emails the
assignee a tokenized completion link. Every action is audit-logged.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations import email_client
from app.models.operations import (
    Activity,
    Assignee,
    Product,
    TimelineEvent,
    WorkOrder,
    WorkOrderItem,
)
from app.services import audit_service, carbon_service

logger = logging.getLogger("agave.workorder")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_work_order_code(db: Session) -> str:
    year = datetime.utcnow().year
    count = db.scalar(
        select(func.count(WorkOrder.id)).where(WorkOrder.work_order_code.like(f"WO-{year}-%"))
    ) or 0
    return f"WO-{year}-{count + 1:04d}"


def _snapshot_item_carbon(db: Session, item_data: dict) -> dict:
    """Compute planned carbon + factor snapshot for one work-order item."""
    activity = db.get(Activity, item_data["activity_id"])
    product = db.get(Product, item_data["product_id"]) if item_data.get("product_id") else None

    total, status, snapshot = carbon_service.compute_carbon(
        activity_factor_value=activity.carbon_factor_value if activity else None,
        activity_factor_unit=activity.carbon_factor_unit if activity else None,
        product_factor_value=product.carbon_factor_value if product else None,
        product_factor_unit=product.carbon_factor_unit if product else None,
        surface_value=item_data.get("planned_surface_area_value"),
        surface_unit=item_data.get("planned_surface_area_unit"),
        total_product_value=item_data.get("planned_total_product_value"),
        total_product_unit=item_data.get("planned_total_product_unit"),
    )
    snapshot["carbon_status"] = status
    snapshot["activity_id"] = activity.id if activity else None
    snapshot["product_id"] = product.id if product else None
    return {
        "planned_carbon_factor_value": activity.carbon_factor_value if activity else None,
        "planned_carbon_factor_unit": activity.carbon_factor_unit if activity else None,
        "planned_carbon_kgco2e": total,
        "carbon_factor_snapshot": snapshot,
    }


def create_work_order(
    db: Session, data: dict, items: list[dict], actor: Optional[str] = None
) -> WorkOrder:
    wo = WorkOrder(
        work_order_code=generate_work_order_code(db),
        status="draft",
        created_by=actor or data.get("created_by"),
        **{k: v for k, v in data.items() if v is not None and k != "created_by"},
    )
    db.add(wo)
    db.flush()

    for item_data in items:
        carbon = _snapshot_item_carbon(db, item_data)
        item = WorkOrderItem(
            work_order_id=wo.id,
            **{k: v for k, v in item_data.items() if v is not None},
            **carbon,
        )
        db.add(item)
    db.flush()

    audit_service.log(db, entity_type="work_order", entity_id=wo.id, action="create",
                      new_values={"code": wo.work_order_code, "title": wo.title,
                                  "items": len(items)}, changed_by=actor)
    if wo.field_id or wo.lot_id:
        _timeline(db, wo, "work_order_created", f"Work order {wo.work_order_code} created", actor)
    db.flush()
    logger.info("Created work order %s with %d item(s)", wo.work_order_code, len(items))
    return wo


def duplicate_work_order(db: Session, source_id: int, actor: Optional[str] = None) -> Optional[WorkOrder]:
    """Clone a work order into a fresh draft. Carbon factors are RE-SNAPSHOT from
    the current catalog (a new plan), not copied from the source's locked values."""
    src = db.get(WorkOrder, source_id)
    if not src:
        return None
    data = {
        "title": f"{src.title} (copy)", "description": src.description,
        "field_id": src.field_id, "lot_id": src.lot_id, "zone_id": src.zone_id,
        "agave_passport_id": src.agave_passport_id, "season_id": src.season_id,
        "assigned_to_id": src.assigned_to_id, "assigned_to_email": src.assigned_to_email,
        "required_photo_evidence_count": src.required_photo_evidence_count,
        "geolocation_required": src.geolocation_required,
        "manual_note_required": src.manual_note_required,
        "weather_capture_required": src.weather_capture_required,
        "review_required": src.review_required,
    }
    items = [{
        "activity_id": it.activity_id, "product_id": it.product_id, "instructions": it.instructions,
        "planned_surface_area_value": it.planned_surface_area_value,
        "planned_surface_area_unit": it.planned_surface_area_unit,
        "planned_dose_value": it.planned_dose_value, "planned_dose_unit": it.planned_dose_unit,
        "planned_total_product_value": it.planned_total_product_value,
        "planned_total_product_unit": it.planned_total_product_unit,
        "required_photo_count": it.required_photo_count,
        "requires_geolocation": it.requires_geolocation,
        "requires_weather_snapshot": it.requires_weather_snapshot,
        "requires_manual_note": it.requires_manual_note,
    } for it in get_items(db, source_id)]
    return create_work_order(db, data, items, actor=actor)


def list_work_orders(db: Session, status: Optional[str] = None, limit: int = 200) -> list[WorkOrder]:
    stmt = select(WorkOrder).where(WorkOrder.deleted_at.is_(None))
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    return list(db.execute(stmt.order_by(WorkOrder.created_at.desc()).limit(limit)).scalars().all())


def get_work_order(db: Session, work_order_id: int) -> Optional[WorkOrder]:
    return db.get(WorkOrder, work_order_id)


def get_items(db: Session, work_order_id: int) -> list[WorkOrderItem]:
    return list(
        db.execute(select(WorkOrderItem).where(WorkOrderItem.work_order_id == work_order_id))
        .scalars()
        .all()
    )


def update_work_order(db: Session, work_order_id: int, data: dict, actor: Optional[str] = None) -> Optional[WorkOrder]:
    wo = db.get(WorkOrder, work_order_id)
    if not wo:
        return None
    old = {k: getattr(wo, k) for k in data if hasattr(wo, k)}
    for k, v in data.items():
        if v is not None and hasattr(wo, k):
            setattr(wo, k, v)
    db.flush()
    audit_service.log(db, entity_type="work_order", entity_id=wo.id, action="update",
                      old_values=old, new_values=data, changed_by=actor)
    return wo


def send_work_order(db: Session, work_order_id: int, actor: Optional[str] = None) -> Optional[dict]:
    """Generate token, email the assignee, mark sent. Returns a result dict or None."""
    wo = db.get(WorkOrder, work_order_id)
    if not wo:
        return None

    recipient = wo.assigned_to_email
    if not recipient and wo.assigned_to_id:
        assignee = db.get(Assignee, wo.assigned_to_id)
        recipient = assignee.email if assignee else None
    if not recipient:
        return {"error": "no_recipient"}

    raw_token = secrets.token_urlsafe(32)
    wo.secure_access_token_hash = hash_token(raw_token)
    wo.secure_link_expires_at = datetime.utcnow() + timedelta(days=settings.work_order_link_expiry_days)
    link = f"{settings.app_base_url.rstrip('/')}/work-orders/complete/{raw_token}"

    location = " / ".join(str(x) for x in (wo.field_id, wo.lot_id, wo.zone_id) if x) or "n/a"
    subject = "New Agave Field Work Order Assigned"
    body = (
        "You have been assigned a new Agave Field work order.\n\n"
        f"Title: {wo.title}\n"
        f"Field / Lot / Zone: {location}\n"
        f"Due date: {wo.due_date or 'n/a'}\n\n"
        f"Open checklist:\n{link}\n"
    )
    delivered, provider = email_client.send_email(recipient, subject, body)

    wo.sent_at = datetime.utcnow()
    wo.status = "sent"
    db.flush()
    audit_service.log(db, entity_type="work_order", entity_id=wo.id, action="send_email",
                      new_values={"recipient": recipient, "provider": provider,
                                  "delivered": delivered}, changed_by=actor)
    _timeline(db, wo, "work_order_sent", f"Work order {wo.work_order_code} sent to {recipient}", actor)
    db.flush()
    return {
        "work_order_id": wo.id,
        "recipient": recipient,
        "provider": provider,
        "delivered": delivered,
        "link": link,            # returned for dev/console; not stored in plaintext
        "token": raw_token,      # caller decides exposure; only the hash is persisted
        "expires_at": wo.secure_link_expires_at,
    }


def find_by_token(db: Session, raw_token: str) -> Optional[WorkOrder]:
    """Resolve a (still-valid) work order from a raw completion token."""
    th = hash_token(raw_token)
    wo = db.execute(
        select(WorkOrder).where(WorkOrder.secure_access_token_hash == th)
    ).scalars().first()
    if not wo:
        return None
    if wo.secure_link_expires_at and wo.secure_link_expires_at < datetime.utcnow():
        return None
    return wo


def _timeline(db: Session, wo: WorkOrder, event_type: str, title: str, actor: Optional[str]) -> None:
    entity_type = "lot" if wo.lot_id else "field"
    entity_id = wo.lot_id or wo.field_id
    if not entity_id:
        return
    db.add(TimelineEvent(
        entity_type=entity_type, entity_id=entity_id, event_type=event_type,
        title=title, event_datetime=datetime.utcnow(), related_work_order_id=wo.id,
        created_by=actor,
    ))
