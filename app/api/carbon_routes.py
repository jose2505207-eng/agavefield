"""Carbon reporting API — reads stored snapshots only (no recompute)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.rbac import scope_context
from app.db import get_db
from app.services import carbon_report_service as carbon
from app.services import rbac_service

router = APIRouter(prefix="/api/carbon", tags=["carbon"])


def _scope_ids(db: Session, ctx: dict):
    """Work-order ids the caller may see, or None (no session/membership → the
    aggregate spans everything, preserving pre-RBAC behaviour)."""
    return rbac_service.allowed_work_order_ids(db, ctx["member"], is_demo=ctx["is_demo"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), ctx: dict = Depends(scope_context)):
    return carbon.summary(db, _scope_ids(db, ctx))


@router.get("/by-season")
def by_season(db: Session = Depends(get_db), ctx: dict = Depends(scope_context)):
    return carbon.by_season(db, _scope_ids(db, ctx))


@router.get("/by-activity")
def by_activity(db: Session = Depends(get_db), ctx: dict = Depends(scope_context)):
    return carbon.by_activity(db, _scope_ids(db, ctx))


@router.get("/by-product")
def by_product(db: Session = Depends(get_db), ctx: dict = Depends(scope_context)):
    return carbon.by_product(db, _scope_ids(db, ctx))


@router.get("/by-lot")
def by_lot(db: Session = Depends(get_db), ctx: dict = Depends(scope_context)):
    return carbon.by_lot(db, _scope_ids(db, ctx))


@router.get("/by-field")
def by_field(db: Session = Depends(get_db), ctx: dict = Depends(scope_context)):
    return carbon.by_field(db, _scope_ids(db, ctx))


@router.get("/missing-data")
def missing_data(db: Session = Depends(get_db), ctx: dict = Depends(scope_context)):
    return carbon.missing_data_report(db, wo_ids=_scope_ids(db, ctx))


@router.get("/overrides")
def overrides(db: Session = Depends(get_db), ctx: dict = Depends(scope_context)):
    return carbon.override_report(db, wo_ids=_scope_ids(db, ctx))
