"""Operations / traceability models (regulated-style work-order system).

Additive layer on top of the existing agronomy models. Entities reference the
existing tables: field=farms, lot=lots, zone=field_zones, passport=agave_passports.

Design principles (FDA-style traceability, NOT certified compliance):
- controlled records with required fields,
- immutable execution history (corrections create revisions, never overwrite),
- carbon factors copied as locked snapshots onto work-order items / executions,
- soft delete / deactivate for anything tied to history,
- audit log for every important action.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models.database import TimestampMixin


# --------------------------------------------------------------------------- #
# Directories / catalogs
# --------------------------------------------------------------------------- #
class Assignee(Base, TimestampMixin):
    __tablename__ = "assignees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(24), default="field_worker")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    preferred_language: Mapped[Optional[str]] = mapped_column(String(8))
    notes: Mapped[Optional[str]] = mapped_column(Text)


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_name: Mapped[str] = mapped_column(String(255), index=True)
    product_type: Mapped[str] = mapped_column(String(32), default="other")
    active_ingredient: Mapped[Optional[str]] = mapped_column(String(255))
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    prohibited: Mapped[bool] = mapped_column(Boolean, default=False)
    default_dose_value: Mapped[Optional[float]] = mapped_column(Float)
    default_dose_unit: Mapped[Optional[str]] = mapped_column(String(32))
    min_dose_value: Mapped[Optional[float]] = mapped_column(Float)
    max_dose_value: Mapped[Optional[float]] = mapped_column(Float)
    application_method: Mapped[Optional[str]] = mapped_column(String(128))
    safety_notes: Mapped[Optional[str]] = mapped_column(Text)
    regenerative_notes: Mapped[Optional[str]] = mapped_column(Text)
    # Carbon factor (manually defined; never AI-estimated).
    carbon_factor_value: Mapped[Optional[float]] = mapped_column(Float)
    carbon_factor_unit: Mapped[Optional[str]] = mapped_column(String(32))
    carbon_factor_source: Mapped[Optional[str]] = mapped_column(String(255))
    carbon_factor_version: Mapped[Optional[str]] = mapped_column(String(32))
    carbon_notes: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(128))


class Activity(Base, TimestampMixin):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_name: Mapped[str] = mapped_column(String(255), index=True)
    activity_category: Mapped[str] = mapped_column(String(40), default="other")
    description: Mapped[Optional[str]] = mapped_column(Text)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_product: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_photo_evidence: Mapped[bool] = mapped_column(Boolean, default=True)
    default_required_photo_count: Mapped[int] = mapped_column(Integer, default=1)
    requires_geolocation: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_surface_area: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_dose: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_weather_snapshot: Mapped[bool] = mapped_column(Boolean, default=True)
    default_follow_up_days: Mapped[Optional[int]] = mapped_column(Integer)
    recommended_frequency: Mapped[Optional[str]] = mapped_column(String(64))
    # Carbon factor (manually defined; never AI-estimated).
    carbon_factor_value: Mapped[Optional[float]] = mapped_column(Float)
    carbon_factor_unit: Mapped[Optional[str]] = mapped_column(String(32))  # kgCO2e_per_ha|_m2|_kg_product|_liter|_event
    carbon_category: Mapped[Optional[str]] = mapped_column(String(64))
    carbon_methodology_note: Mapped[Optional[str]] = mapped_column(Text)
    carbon_factor_source: Mapped[Optional[str]] = mapped_column(String(255))
    carbon_factor_version: Mapped[Optional[str]] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(128))


# --------------------------------------------------------------------------- #
# Work orders
# --------------------------------------------------------------------------- #
class WorkOrder(Base, TimestampMixin):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    field_id: Mapped[Optional[int]] = mapped_column(ForeignKey("farms.id"), index=True)
    lot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lots.id"), index=True)
    zone_id: Mapped[Optional[int]] = mapped_column(ForeignKey("field_zones.id"))
    agave_passport_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agave_passports.id"))
    season_id: Mapped[Optional[int]] = mapped_column(Integer)  # optional, no Season table in MVP

    planned_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assignees.id"), index=True)
    assigned_to_email: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[str]] = mapped_column(String(128))

    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)

    secure_access_token_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    secure_link_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(128))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Per-order requirement toggles.
    required_photo_evidence_count: Mapped[int] = mapped_column(Integer, default=1)
    geolocation_required: Mapped[bool] = mapped_column(Boolean, default=True)
    manual_note_required: Mapped[bool] = mapped_column(Boolean, default=True)
    weather_capture_required: Mapped[bool] = mapped_column(Boolean, default=True)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)  # soft delete only


class WorkOrderItem(Base, TimestampMixin):
    __tablename__ = "work_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"))
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"))

    planned_surface_area_value: Mapped[Optional[float]] = mapped_column(Float)
    planned_surface_area_unit: Mapped[Optional[str]] = mapped_column(String(16))  # ha|m2
    planned_dose_value: Mapped[Optional[float]] = mapped_column(Float)
    planned_dose_unit: Mapped[Optional[str]] = mapped_column(String(32))
    planned_total_product_value: Mapped[Optional[float]] = mapped_column(Float)
    planned_total_product_unit: Mapped[Optional[str]] = mapped_column(String(16))  # kg|l

    required_photo_count: Mapped[int] = mapped_column(Integer, default=1)
    requires_geolocation: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_weather_snapshot: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_manual_note: Mapped[bool] = mapped_column(Boolean, default=True)
    instructions: Mapped[Optional[str]] = mapped_column(Text)

    # Locked carbon snapshot (copied at item creation; never recomputed later).
    planned_carbon_factor_value: Mapped[Optional[float]] = mapped_column(Float)
    planned_carbon_factor_unit: Mapped[Optional[str]] = mapped_column(String(32))
    planned_carbon_kgco2e: Mapped[Optional[float]] = mapped_column(Float)
    carbon_factor_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)


# --------------------------------------------------------------------------- #
# Execution (immutable submissions)
# --------------------------------------------------------------------------- #
class ExecutionRecord(Base, TimestampMixin):
    __tablename__ = "execution_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    work_order_item_id: Mapped[int] = mapped_column(ForeignKey("work_order_items.id"), index=True)
    activity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("activities.id"))
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"))

    actual_surface_area_value: Mapped[Optional[float]] = mapped_column(Float)
    actual_surface_area_unit: Mapped[Optional[str]] = mapped_column(String(16))
    actual_dose_value: Mapped[Optional[float]] = mapped_column(Float)
    actual_dose_unit: Mapped[Optional[str]] = mapped_column(String(32))
    actual_total_product_value: Mapped[Optional[float]] = mapped_column(Float)
    actual_total_product_unit: Mapped[Optional[str]] = mapped_column(String(16))

    execution_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    execution_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    responsible_person: Mapped[Optional[str]] = mapped_column(String(128))
    submitted_by_name: Mapped[Optional[str]] = mapped_column(String(128))
    submitted_by_email: Mapped[Optional[str]] = mapped_column(String(255))
    manual_note: Mapped[Optional[str]] = mapped_column(Text)

    gps_latitude: Mapped[Optional[float]] = mapped_column(Float)
    gps_longitude: Mapped[Optional[float]] = mapped_column(Float)
    gps_accuracy: Mapped[Optional[float]] = mapped_column(Float)
    gps_captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    weather_snapshot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ops_weather_snapshots.id"))
    weather_snapshot_status: Mapped[str] = mapped_column(String(16), default="pending")

    # Carbon: actual value + locked factor snapshot used at submission time.
    actual_carbon_kgco2e: Mapped[Optional[float]] = mapped_column(Float)
    carbon_factor_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)
    carbon_calculation_status: Mapped[str] = mapped_column(String(20), default="pending")
    carbon_override_value: Mapped[Optional[float]] = mapped_column(Float)
    carbon_override_reason: Mapped[Optional[str]] = mapped_column(Text)
    carbon_override_user: Mapped[Optional[str]] = mapped_column(String(128))
    carbon_override_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    compliance_status: Mapped[str] = mapped_column(String(20), default="pending_review", index=True)
    is_revision_of_id: Mapped[Optional[int]] = mapped_column(ForeignKey("execution_records.id"))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class PhotoEvidence(Base):
    __tablename__ = "photo_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_url: Mapped[str] = mapped_column(String(1024))
    storage_key: Mapped[Optional[str]] = mapped_column(String(512))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024))
    work_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("work_orders.id"), index=True)
    work_order_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("work_order_items.id"))
    execution_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("execution_records.id"), index=True)
    field_id: Mapped[Optional[int]] = mapped_column(ForeignKey("farms.id"))
    lot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lots.id"))
    zone_id: Mapped[Optional[int]] = mapped_column(ForeignKey("field_zones.id"))
    agave_passport_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agave_passports.id"))
    gps_latitude: Mapped[Optional[float]] = mapped_column(Float)
    gps_longitude: Mapped[Optional[float]] = mapped_column(Float)
    gps_accuracy: Mapped[Optional[float]] = mapped_column(Float)
    gps_source: Mapped[str] = mapped_column(String(16), default="unavailable")  # device|exif|manual|unavailable
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(128))
    manual_note: Mapped[Optional[str]] = mapped_column(Text)
    weather_snapshot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ops_weather_snapshots.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OpsWeatherSnapshot(Base):
    __tablename__ = "ops_weather_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    field_id: Mapped[Optional[int]] = mapped_column(ForeignKey("farms.id"))
    lot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lots.id"))
    zone_id: Mapped[Optional[int]] = mapped_column(ForeignKey("field_zones.id"))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    weather_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime)
    provider: Mapped[Optional[str]] = mapped_column(String(32))
    rainfall_current: Mapped[Optional[float]] = mapped_column(Float)
    rainfall_probability: Mapped[Optional[float]] = mapped_column(Float)
    rainfall_last_24h: Mapped[Optional[float]] = mapped_column(Float)
    rainfall_next_24h: Mapped[Optional[float]] = mapped_column(Float)
    temperature_current: Mapped[Optional[float]] = mapped_column(Float)
    temperature_min: Mapped[Optional[float]] = mapped_column(Float)
    temperature_max: Mapped[Optional[float]] = mapped_column(Float)
    humidity: Mapped[Optional[float]] = mapped_column(Float)
    wind_speed: Mapped[Optional[float]] = mapped_column(Float)
    raw_payload_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_record_id: Mapped[int] = mapped_column(ForeignKey("execution_records.id"), index=True)
    review_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assignees.id"))
    reviewer_name: Mapped[Optional[str]] = mapped_column(String(128))
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text)
    correction_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    correction_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), index=True)  # field|lot|zone|agave_passport
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    event_datetime: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    related_work_order_id: Mapped[Optional[int]] = mapped_column(Integer)
    related_execution_record_id: Mapped[Optional[int]] = mapped_column(Integer)
    related_product_id: Mapped[Optional[int]] = mapped_column(Integer)
    related_activity_id: Mapped[Optional[int]] = mapped_column(Integer)
    related_photo_ids: Mapped[Optional[list]] = mapped_column(JSON)
    carbon_kgco2e: Mapped[Optional[float]] = mapped_column(Float)
    weather_snapshot_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_by: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    old_values_json: Mapped[Optional[dict]] = mapped_column(JSON)
    new_values_json: Mapped[Optional[dict]] = mapped_column(JSON)
    changed_by: Mapped[Optional[str]] = mapped_column(String(128))
    changed_by_email: Mapped[Optional[str]] = mapped_column(String(255))
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
