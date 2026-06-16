"""CRUD for the editable catalogs + assignee directory.

History-safe: records referenced by work orders / executions are never hard
deleted — they are deactivated. Every mutation is written to the audit log.
"""
from __future__ import annotations

import logging
from typing import Optional, Type

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.operations import (
    Activity,
    Assignee,
    ExecutionRecord,
    Product,
    Review,
    WorkOrder,
    WorkOrderItem,
)
from app.services import audit_service

logger = logging.getLogger("agave.catalog")


def _create(db: Session, model: Type, data: dict, entity_type: str, actor: Optional[str]):
    obj = model(**{k: v for k, v in data.items() if v is not None})
    db.add(obj)
    db.flush()
    audit_service.log(db, entity_type=entity_type, entity_id=obj.id, action="create",
                      new_values=data, changed_by=actor or data.get("created_by"))
    return obj


def _update(db: Session, obj, data: dict, entity_type: str, actor: Optional[str]):
    old = {k: getattr(obj, k) for k in data if hasattr(obj, k)}
    for k, v in data.items():
        if v is not None and hasattr(obj, k):
            setattr(obj, k, v)
    db.flush()
    audit_service.log(db, entity_type=entity_type, entity_id=obj.id, action="update",
                      old_values=old, new_values=data, changed_by=actor)
    return obj


def _references_exist(db: Session, *conditions_counts: int) -> bool:
    return any(c and c > 0 for c in conditions_counts)


# --------------------------------------------------------------------------- #
# Assignees
# --------------------------------------------------------------------------- #
def list_assignees(db: Session, include_inactive: bool = True) -> list[Assignee]:
    stmt = select(Assignee)
    if not include_inactive:
        stmt = stmt.where(Assignee.active.is_(True))
    return list(db.execute(stmt.order_by(Assignee.full_name)).scalars().all())


def create_assignee(db: Session, data: dict, actor: Optional[str] = None) -> Assignee:
    return _create(db, Assignee, data, "assignee", actor)


def update_assignee(db: Session, assignee_id: int, data: dict, actor: Optional[str] = None) -> Optional[Assignee]:
    obj = db.get(Assignee, assignee_id)
    if not obj:
        return None
    return _update(db, obj, data, "assignee", actor)


def delete_or_deactivate_assignee(db: Session, assignee_id: int, actor: Optional[str] = None) -> str:
    obj = db.get(Assignee, assignee_id)
    if not obj:
        return "not_found"
    refs = db.scalar(select(func.count(WorkOrder.id)).where(WorkOrder.assigned_to_id == assignee_id)) or 0
    refs += db.scalar(select(func.count(Review.id)).where(Review.reviewer_id == assignee_id)) or 0
    if refs > 0:
        obj.active = False
        db.flush()
        audit_service.log(db, entity_type="assignee", entity_id=assignee_id, action="deactivate",
                          changed_by=actor, reason="has linked records")
        return "deactivated"
    audit_service.log(db, entity_type="assignee", entity_id=assignee_id, action="soft_delete", changed_by=actor)
    db.delete(obj)
    db.flush()
    return "deleted"


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #
def list_products(db: Session, include_inactive: bool = True) -> list[Product]:
    stmt = select(Product)
    if not include_inactive:
        stmt = stmt.where(Product.active.is_(True))
    return list(db.execute(stmt.order_by(Product.product_name)).scalars().all())


def create_product(db: Session, data: dict, actor: Optional[str] = None) -> Product:
    return _create(db, Product, data, "product", actor)


def update_product(db: Session, product_id: int, data: dict, actor: Optional[str] = None) -> Optional[Product]:
    obj = db.get(Product, product_id)
    if not obj:
        return None
    return _update(db, obj, data, "product", actor)


def delete_or_deactivate_product(db: Session, product_id: int, actor: Optional[str] = None) -> str:
    obj = db.get(Product, product_id)
    if not obj:
        return "not_found"
    refs = db.scalar(select(func.count(WorkOrderItem.id)).where(WorkOrderItem.product_id == product_id)) or 0
    refs += db.scalar(select(func.count(ExecutionRecord.id)).where(ExecutionRecord.product_id == product_id)) or 0
    if refs > 0:
        obj.active = False
        db.flush()
        audit_service.log(db, entity_type="product", entity_id=product_id, action="deactivate",
                          changed_by=actor, reason="has historical records")
        return "deactivated"
    audit_service.log(db, entity_type="product", entity_id=product_id, action="soft_delete", changed_by=actor)
    db.delete(obj)
    db.flush()
    return "deleted"


# --------------------------------------------------------------------------- #
# Activities
# --------------------------------------------------------------------------- #
def list_activities(db: Session, include_inactive: bool = True) -> list[Activity]:
    stmt = select(Activity)
    if not include_inactive:
        stmt = stmt.where(Activity.active.is_(True))
    return list(db.execute(stmt.order_by(Activity.activity_name)).scalars().all())


def create_activity(db: Session, data: dict, actor: Optional[str] = None) -> Activity:
    return _create(db, Activity, data, "activity", actor)


def update_activity(db: Session, activity_id: int, data: dict, actor: Optional[str] = None) -> Optional[Activity]:
    obj = db.get(Activity, activity_id)
    if not obj:
        return None
    return _update(db, obj, data, "activity", actor)


def delete_or_deactivate_activity(db: Session, activity_id: int, actor: Optional[str] = None) -> str:
    obj = db.get(Activity, activity_id)
    if not obj:
        return "not_found"
    refs = db.scalar(select(func.count(WorkOrderItem.id)).where(WorkOrderItem.activity_id == activity_id)) or 0
    refs += db.scalar(select(func.count(ExecutionRecord.id)).where(ExecutionRecord.activity_id == activity_id)) or 0
    if refs > 0:
        obj.active = False
        db.flush()
        audit_service.log(db, entity_type="activity", entity_id=activity_id, action="deactivate",
                          changed_by=actor, reason="has historical records")
        return "deactivated"
    audit_service.log(db, entity_type="activity", entity_id=activity_id, action="soft_delete", changed_by=actor)
    db.delete(obj)
    db.flush()
    return "deleted"
