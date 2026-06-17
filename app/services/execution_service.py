"""Worker submission → immutable ExecutionRecord(s).

Actual carbon uses the WorkOrderItem's LOCKED factor snapshot applied to the
worker's actual quantities (catalog changes never affect it). A weather snapshot
is captured once per submission and linked to records + photos. Missing required
evidence/GPS/note marks the record needs_correction rather than discarding the
field work. Submissions are never overwritten.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operations import (
    ExecutionRecord,
    PhotoEvidence,
    TimelineEvent,
    WorkOrder,
    WorkOrderItem,
)
from app.services import audit_service, carbon_service, ops_weather_service

logger = logging.getLogger("agave.execution")


def override_carbon(db: Session, execution_id: int, *, value: float, reason: str,
                    user: str = None) -> dict | None:
    """Manual carbon override with reason + user + timestamp (audit-logged).
    Preserves the originally calculated value; only the override fields change."""
    er = db.get(ExecutionRecord, execution_id)
    if not er:
        return None
    old = er.carbon_override_value
    er.carbon_override_value = value
    er.carbon_override_reason = reason
    er.carbon_override_user = user
    er.carbon_override_at = datetime.utcnow()
    db.flush()
    audit_service.log(db, entity_type="execution_record", entity_id=er.id, action="override_carbon",
                      old_values={"carbon_override_value": old},
                      new_values={"carbon_override_value": value, "calculated": er.actual_carbon_kgco2e},
                      changed_by=user, reason=reason)
    return {"execution_record_id": er.id, "override_value": value,
            "calculated_value": er.actual_carbon_kgco2e}


def submit_execution(db: Session, wo: WorkOrder, payload) -> dict:
    # Capture one weather snapshot for the submission location (rain-first).
    weather_snap, weather_status = ops_weather_service.capture_snapshot(
        db, latitude=payload.gps_latitude, longitude=payload.gps_longitude,
        field_id=wo.field_id, lot_id=wo.lot_id, zone_id=wo.zone_id,
    )
    weather_id = weather_snap.id if weather_snap else None

    results = []
    for s in payload.items:
        item = db.get(WorkOrderItem, s.work_order_item_id)
        if not item or item.work_order_id != wo.id:
            results.append({"work_order_item_id": s.work_order_item_id, "error": "invalid_item"})
            continue

        # Actual carbon from the locked snapshot factor × actual quantities.
        snap = item.carbon_factor_snapshot or {}
        total, carbon_status, carbon_snap = carbon_service.compute_carbon(
            activity_factor_value=snap.get("activity_factor_value"),
            activity_factor_unit=snap.get("activity_factor_unit"),
            product_factor_value=snap.get("product_factor_value"),
            product_factor_unit=snap.get("product_factor_unit"),
            surface_value=s.actual_surface_area_value, surface_unit=s.actual_surface_area_unit,
            total_product_value=s.actual_total_product_value, total_product_unit=s.actual_total_product_unit,
        )

        # Completeness vs per-item requirements.
        photos = [p for p in (db.get(PhotoEvidence, pid) for pid in s.evidence_photo_ids) if p]
        warnings = []
        if item.requires_geolocation and payload.gps_latitude is None:
            warnings.append("missing_gps")
        if item.requires_manual_note and not (s.manual_note and s.manual_note.strip()):
            warnings.append("missing_manual_note")
        if item.required_photo_count and len(photos) < item.required_photo_count:
            warnings.append("missing_photos")
        compliance = "needs_correction" if warnings else "pending_review"

        # A re-submission for the same item forms a revision chain (never an
        # overwrite) — preserves the original submitted record.
        prior_id = db.execute(
            select(ExecutionRecord.id)
            .where(ExecutionRecord.work_order_item_id == item.id)
            .order_by(ExecutionRecord.id.desc())
            .limit(1)
        ).scalar_one_or_none()

        er = ExecutionRecord(
            work_order_id=wo.id, work_order_item_id=item.id,
            is_revision_of_id=prior_id,
            activity_id=item.activity_id, product_id=item.product_id,
            actual_surface_area_value=s.actual_surface_area_value,
            actual_surface_area_unit=s.actual_surface_area_unit,
            actual_dose_value=s.actual_dose_value, actual_dose_unit=s.actual_dose_unit,
            actual_total_product_value=s.actual_total_product_value,
            actual_total_product_unit=s.actual_total_product_unit,
            execution_started_at=payload.execution_started_at,
            execution_completed_at=payload.execution_completed_at,
            responsible_person=payload.responsible_person,
            submitted_by_name=payload.submitted_by_name,
            submitted_by_email=payload.submitted_by_email,
            manual_note=s.manual_note,
            gps_latitude=payload.gps_latitude, gps_longitude=payload.gps_longitude,
            gps_accuracy=payload.gps_accuracy, gps_captured_at=payload.gps_captured_at,
            weather_snapshot_id=weather_id, weather_snapshot_status=weather_status,
            actual_carbon_kgco2e=total, carbon_factor_snapshot=carbon_snap,
            carbon_calculation_status=carbon_status,
            compliance_status=compliance, submitted_at=datetime.utcnow(),
        )
        db.add(er)
        db.flush()

        for p in photos:
            p.execution_record_id = er.id
            if weather_id and not p.weather_snapshot_id:
                p.weather_snapshot_id = weather_id
        item.status = "submitted"

        audit_service.log(db, entity_type="execution_record", entity_id=er.id, action="submit",
                          new_values={"work_order_item_id": item.id, "carbon": total,
                                      "compliance": compliance, "warnings": warnings},
                          changed_by=payload.submitted_by_name)
        if wo.lot_id or wo.field_id:
            db.add(TimelineEvent(
                entity_type="lot" if wo.lot_id else "field",
                entity_id=wo.lot_id or wo.field_id,
                event_type="activity_submitted",
                title=f"Activity submitted ({wo.work_order_code})",
                description=s.manual_note, event_datetime=datetime.utcnow(),
                related_work_order_id=wo.id, related_execution_record_id=er.id,
                related_activity_id=item.activity_id, related_product_id=item.product_id,
                carbon_kgco2e=total, weather_snapshot_id=weather_id,
                created_by=payload.submitted_by_name,
            ))
        results.append({
            "work_order_item_id": item.id, "execution_record_id": er.id,
            "actual_carbon_kgco2e": total, "carbon_status": carbon_status,
            "compliance_status": compliance, "warnings": warnings, "photos": len(photos),
        })

    wo.status = "submitted"
    wo.submitted_at = datetime.utcnow()
    db.flush()
    audit_service.log(db, entity_type="work_order", entity_id=wo.id, action="submit",
                      new_values={"executions": len(results)})
    logger.info("Work order %s submitted (%d executions, weather=%s)",
                wo.work_order_code, len(results), weather_status)
    return {
        "work_order_id": wo.id, "status": wo.status, "weather_status": weather_status,
        "executions": results,
    }
