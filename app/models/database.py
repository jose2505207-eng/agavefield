"""SQLAlchemy ORM models for Agave Field Copilot.

Coordinates are stored as plain latitude/longitude floats so the schema is
portable (SQLite for tests, PostgreSQL in prod). `polygon_geojson` keeps lot
boundaries as GeoJSON; these can be migrated to PostGIS `geography` columns
later without changing the application contract.
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
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    telegram_user_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, unique=True)
    whatsapp_phone: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    role: Mapped[str] = mapped_column(String(32), default="agronomist")

    observations: Mapped[list["FieldObservation"]] = relationship(back_populates="user")


class Farm(Base, TimestampMixin):
    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    municipality: Mapped[Optional[str]] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(128), default="Jalisco")
    owner_name: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    lots: Mapped[list["Lot"]] = relationship(back_populates="farm")


class Lot(Base, TimestampMixin):
    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[Optional[int]] = mapped_column(ForeignKey("farms.id"), index=True)
    lot_code: Mapped[str] = mapped_column(String(64), index=True)
    crop_type: Mapped[str] = mapped_column(String(64), default="agave_azul")
    planted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    estimated_age_months: Mapped[Optional[int]] = mapped_column(Integer)
    polygon_geojson: Mapped[Optional[dict]] = mapped_column(JSON)
    centroid_latitude: Mapped[Optional[float]] = mapped_column(Float)
    centroid_longitude: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    farm: Mapped[Optional[Farm]] = relationship(back_populates="lots")
    observations: Mapped[list["FieldObservation"]] = relationship(back_populates="lot")


class FieldObservation(Base, TimestampMixin):
    __tablename__ = "field_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    farm_id: Mapped[Optional[int]] = mapped_column(ForeignKey("farms.id"), index=True)
    lot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lots.id"), index=True)
    passport_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agave_passports.id"), index=True
    )

    source_channel: Mapped[str] = mapped_column(String(32), default="telegram")
    image_url: Mapped[Optional[str]] = mapped_column(String(1024))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024))
    original_caption: Mapped[Optional[str]] = mapped_column(Text)

    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # --- AI / Hermes extracted fields ---
    image_type: Mapped[str] = mapped_column(String(32), default="unknown")
    plant_condition: Mapped[str] = mapped_column(String(32), default="unknown")
    suspected_issue: Mapped[Optional[str]] = mapped_column(String(255))
    diagnosis: Mapped[Optional[str]] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(16), default="unknown", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    visible_symptoms_json: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)
    recommended_next_step: Mapped[Optional[str]] = mapped_column(Text)
    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Human-in-the-loop / validation (training-quality feedback) ---
    human_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    human_correction: Mapped[Optional[str]] = mapped_column(Text)
    human_validation_status: Mapped[str] = mapped_column(
        String(16), default="pending", index=True
    )  # pending | confirmed | corrected | rejected
    human_corrected_label: Mapped[Optional[str]] = mapped_column(String(255))
    human_notes: Mapped[Optional[str]] = mapped_column(Text)
    validated_by: Mapped[Optional[str]] = mapped_column(String(128))
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    escalation_status: Mapped[str] = mapped_column(String(32), default="none", index=True)

    user: Mapped[Optional[User]] = relationship(back_populates="observations")
    lot: Mapped[Optional[Lot]] = relationship(back_populates="observations")
    passport: Mapped[Optional["AgavePassport"]] = relationship(back_populates="observations")
    model_outputs: Mapped[list["ModelOutput"]] = relationship(
        back_populates="observation", cascade="all, delete-orphan"
    )
    weather_snapshots: Mapped[list["WeatherSnapshot"]] = relationship(
        back_populates="observation", cascade="all, delete-orphan"
    )
    escalations: Mapped[list["Escalation"]] = relationship(
        back_populates="observation", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(back_populates="observation")
    validations: Mapped[list["HumanValidation"]] = relationship(
        back_populates="observation", cascade="all, delete-orphan"
    )


class ModelOutput(Base):
    """Immutable record of every model inference. Never overwritten."""

    __tablename__ = "model_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("field_observations.id"), index=True
    )
    model_name: Mapped[str] = mapped_column(String(128))
    raw_json: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    observation: Mapped[FieldObservation] = relationship(back_populates="model_outputs")


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("field_observations.id"), index=True
    )
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    temperature_c: Mapped[Optional[float]] = mapped_column(Float)
    humidity_percent: Mapped[Optional[float]] = mapped_column(Float)
    precipitation_mm: Mapped[Optional[float]] = mapped_column(Float)
    wind_speed_kmh: Mapped[Optional[float]] = mapped_column(Float)
    recent_rain_mm: Mapped[Optional[float]] = mapped_column(Float)
    heat_risk: Mapped[Optional[str]] = mapped_column(String(16))
    drought_risk: Mapped[Optional[str]] = mapped_column(String(16))
    weather_source: Mapped[Optional[str]] = mapped_column(String(64))
    raw_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    observation: Mapped[FieldObservation] = relationship(back_populates="weather_snapshots")


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("field_observations.id"), index=True
    )
    channel: Mapped[str] = mapped_column(String(32))
    recipient: Mapped[str] = mapped_column(String(128))
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text)
    message_body: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    observation: Mapped[FieldObservation] = relationship(back_populates="escalations")


# --------------------------------------------------------------------------- #
# MVP additions: passports, zones, tasks, alerts, validations, reports
# --------------------------------------------------------------------------- #
class FieldZone(Base, TimestampMixin):
    """A named zone inside a lot. Kept intentionally light (no GIS yet)."""

    __tablename__ = "field_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lots.id"), index=True)
    zone_name: Mapped[str] = mapped_column(String(64), index=True)
    centroid_latitude: Mapped[Optional[float]] = mapped_column(Float)
    centroid_longitude: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class AgavePassport(Base, TimestampMixin):
    """Persistent memory for a plant / row / zone / lot.

    Aggregates the latest health/risk state plus history (photos, observations,
    tasks) so the dashboard can show a single profile over time.
    """

    __tablename__ = "agave_passports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passport_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    farm_id: Mapped[Optional[int]] = mapped_column(ForeignKey("farms.id"), index=True)
    lot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lots.id"), index=True)
    zone_id: Mapped[Optional[int]] = mapped_column(ForeignKey("field_zones.id"), index=True)

    label: Mapped[Optional[str]] = mapped_column(String(255))  # plant/zone label
    field_name: Mapped[Optional[str]] = mapped_column(String(255))
    lot_name: Mapped[Optional[str]] = mapped_column(String(255))
    zone_name: Mapped[Optional[str]] = mapped_column(String(255))

    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    estimated_age_months: Mapped[Optional[int]] = mapped_column(Integer)

    health_status: Mapped[str] = mapped_column(String(32), default="unknown")
    risk_level: Mapped[str] = mapped_column(String(16), default="unknown", index=True)

    last_inspection_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    next_inspection_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    observations: Mapped[list["FieldObservation"]] = relationship(back_populates="passport")
    tasks: Mapped[list["Task"]] = relationship(back_populates="passport")


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passport_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agave_passports.id"), index=True
    )
    observation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("field_observations.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), default="medium")  # low|medium|high|urgent
    status: Mapped[str] = mapped_column(
        String(16), default="open", index=True
    )  # open|in_progress|completed|cancelled
    assigned_to: Mapped[Optional[str]] = mapped_column(String(128))
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    source: Mapped[str] = mapped_column(
        String(24), default="ai_generated"
    )  # ai_generated|human_created|weather_trigger|follow_up
    # Dangerous/expensive actions must be human-approved before execution.
    needs_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)

    passport: Mapped[Optional[AgavePassport]] = relationship(back_populates="tasks")
    observation: Mapped[Optional[FieldObservation]] = relationship(back_populates="tasks")


class Alert(Base):
    """Unified alert/notification record (dashboard + external channels)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passport_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agave_passports.id"), index=True
    )
    observation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("field_observations.id"), index=True
    )
    recipient: Mapped[Optional[str]] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(32), default="dashboard")
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    delivery_status: Mapped[str] = mapped_column(String(16), default="pending")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class HumanValidation(Base):
    """Immutable record of a human validation/correction (training data)."""

    __tablename__ = "human_validations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("field_observations.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(16))  # confirmed|corrected|rejected
    original_diagnosis: Mapped[Optional[str]] = mapped_column(String(255))
    corrected_label: Mapped[Optional[str]] = mapped_column(String(255))
    original_confidence: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    validated_by: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    observation: Mapped[FieldObservation] = relationship(back_populates="validations")


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(16), default="all")  # all|farm|lot|zone
    scope_id: Mapped[Optional[int]] = mapped_column(Integer)
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
