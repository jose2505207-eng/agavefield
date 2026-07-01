"""Carbon reporting — aggregates STORED carbon values only (never recomputes).

Planned carbon comes from WorkOrderItem snapshots; actual carbon from
ExecutionRecord (using the manual override value when present). Surfaces
planned-vs-actual, per-hectare, breakdowns, top contributors, missing-data, and
the override report.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.database import Farm, Lot
from app.models.operations import (
    Activity,
    ExecutionRecord,
    Product,
    WorkOrder,
    WorkOrderItem,
)

# Effective actual carbon = manual override if set, else the calculated value.
_EFFECTIVE = func.coalesce(ExecutionRecord.carbon_override_value, ExecutionRecord.actual_carbon_kgco2e)


def _round(v) -> Optional[float]:
    return round(v, 4) if v is not None else None


def _scoped(stmt, col, wo_ids: Optional[list]):
    """Restrict a statement to the given work-order ids when scoping is active.

    ``wo_ids is None`` → no filtering (open / API-key / legacy caller, unchanged
    behaviour). A list (possibly empty) → only rows whose ``col`` is in it, so a
    scoped member's aggregates never include out-of-scope work orders."""
    if wo_ids is None:
        return stmt
    return stmt.where(col.in_(wo_ids))


def _surface_ha(value: Optional[float], unit: Optional[str]) -> float:
    if value is None or not unit:
        return 0.0
    u = unit.lower()
    if u == "ha":
        return value
    if u == "m2":
        return value / 10_000.0
    return 0.0


def summary(db: Session, wo_ids: Optional[list] = None) -> dict:
    total_planned = db.scalar(
        _scoped(select(func.sum(WorkOrderItem.planned_carbon_kgco2e)),
                WorkOrderItem.work_order_id, wo_ids)
    ) or 0.0
    total_actual = db.scalar(
        _scoped(select(func.sum(_EFFECTIVE)).select_from(ExecutionRecord),
                ExecutionRecord.work_order_id, wo_ids)
    ) or 0.0

    # Per-hectare from actual surface across executions (normalize units in Python).
    rows = db.execute(
        _scoped(
            select(ExecutionRecord.actual_surface_area_value,
                   ExecutionRecord.actual_surface_area_unit, _EFFECTIVE),
            ExecutionRecord.work_order_id, wo_ids)
    ).all()
    total_surface_ha = sum(_surface_ha(r[0], r[1]) for r in rows)
    actual_with_carbon = sum((r[2] or 0.0) for r in rows)
    per_ha = _round(actual_with_carbon / total_surface_ha) if total_surface_ha else None

    missing = db.scalar(
        _scoped(
            select(func.count(ExecutionRecord.id)).where(
                (ExecutionRecord.carbon_calculation_status.in_(("missing_data", "pending", "no_factor")))
                | (ExecutionRecord.actual_carbon_kgco2e.is_(None))
            ),
            ExecutionRecord.work_order_id, wo_ids)
    ) or 0
    overrides = db.scalar(
        _scoped(
            select(func.count(ExecutionRecord.id)).where(
                ExecutionRecord.carbon_override_value.is_not(None)),
            ExecutionRecord.work_order_id, wo_ids)
    ) or 0

    return {
        "total_planned_kgco2e": _round(total_planned),
        "total_actual_kgco2e": _round(total_actual),
        "planned_vs_actual_kgco2e": _round((total_actual or 0) - (total_planned or 0)),
        "total_actual_surface_ha": _round(total_surface_ha),
        "kgco2e_per_hectare": per_ha,
        "records_missing_carbon_data": missing,
        "manual_overrides": overrides,
        "top_activities": by_activity(db, wo_ids)[:5],
        "top_products": by_product(db, wo_ids)[:5],
    }


def _grouped(db: Session, label_col, *, join_wo: bool = False,
             wo_ids: Optional[list] = None) -> list[tuple]:
    stmt = select(label_col, func.sum(_EFFECTIVE)).select_from(ExecutionRecord)
    if join_wo:
        stmt = stmt.join(WorkOrder, ExecutionRecord.work_order_id == WorkOrder.id)
    stmt = _scoped(stmt, ExecutionRecord.work_order_id, wo_ids)
    stmt = stmt.where(_EFFECTIVE.is_not(None)).group_by(label_col)
    return db.execute(stmt).all()


def by_activity(db: Session, wo_ids: Optional[list] = None) -> list[dict]:
    rows = _grouped(db, ExecutionRecord.activity_id, wo_ids=wo_ids)
    out = []
    for activity_id, total in rows:
        a = db.get(Activity, activity_id) if activity_id else None
        out.append({"activity_id": activity_id,
                    "activity_name": a.activity_name if a else None,
                    "kgco2e": _round(total)})
    return sorted(out, key=lambda r: r["kgco2e"] or 0, reverse=True)


def by_product(db: Session, wo_ids: Optional[list] = None) -> list[dict]:
    rows = _grouped(db, ExecutionRecord.product_id, wo_ids=wo_ids)
    out = []
    for product_id, total in rows:
        if product_id is None:
            continue
        p = db.get(Product, product_id)
        out.append({"product_id": product_id,
                    "product_name": p.product_name if p else None,
                    "kgco2e": _round(total)})
    return sorted(out, key=lambda r: r["kgco2e"] or 0, reverse=True)


def by_lot(db: Session, wo_ids: Optional[list] = None) -> list[dict]:
    rows = _grouped(db, WorkOrder.lot_id, join_wo=True, wo_ids=wo_ids)
    out = []
    for lot_id, total in rows:
        lot = db.get(Lot, lot_id) if lot_id else None
        out.append({"lot_id": lot_id, "lot_code": lot.lot_code if lot else None,
                    "kgco2e": _round(total)})
    return sorted(out, key=lambda r: r["kgco2e"] or 0, reverse=True)


def by_field(db: Session, wo_ids: Optional[list] = None) -> list[dict]:
    rows = _grouped(db, WorkOrder.field_id, join_wo=True, wo_ids=wo_ids)
    out = []
    for field_id, total in rows:
        f = db.get(Farm, field_id) if field_id else None
        out.append({"field_id": field_id, "field_name": f.name if f else None,
                    "kgco2e": _round(total)})
    return sorted(out, key=lambda r: r["kgco2e"] or 0, reverse=True)


def by_season(db: Session, wo_ids: Optional[list] = None) -> list[dict]:
    rows = _grouped(db, WorkOrder.season_id, join_wo=True, wo_ids=wo_ids)
    return [{"season_id": s, "kgco2e": _round(t)} for s, t in rows]


def missing_data_report(db: Session, limit: int = 200,
                        wo_ids: Optional[list] = None) -> list[dict]:
    rows = db.execute(
        _scoped(
            select(ExecutionRecord).where(
                (ExecutionRecord.carbon_calculation_status.in_(("missing_data", "pending", "no_factor")))
                | (ExecutionRecord.actual_carbon_kgco2e.is_(None))
            ),
            ExecutionRecord.work_order_id, wo_ids).limit(limit)
    ).scalars().all()
    return [{"execution_record_id": e.id, "work_order_id": e.work_order_id,
             "activity_id": e.activity_id, "carbon_status": e.carbon_calculation_status,
             "submitted_at": e.submitted_at} for e in rows]


def override_report(db: Session, limit: int = 200,
                   wo_ids: Optional[list] = None) -> list[dict]:
    rows = db.execute(
        _scoped(
            select(ExecutionRecord).where(
                ExecutionRecord.carbon_override_value.is_not(None)),
            ExecutionRecord.work_order_id, wo_ids).limit(limit)
    ).scalars().all()
    return [{"execution_record_id": e.id, "override_value": e.carbon_override_value,
             "reason": e.carbon_override_reason, "user": e.carbon_override_user,
             "at": e.carbon_override_at} for e in rows]
