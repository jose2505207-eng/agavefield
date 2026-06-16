"""Pydantic v2 schemas: the Hermes AI contract + API request/response models.

`HermesOutput` is the single source of truth for what the vision/agent layer
must return. Every model response is validated against it before anything is
written to the database (requirement 16).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# Controlled vocabularies
# --------------------------------------------------------------------------- #
class ImageType(str, Enum):
    close_up = "close_up"
    whole_plant = "whole_plant"
    field_row = "field_row"
    landscape = "landscape"
    soil = "soil"
    root = "root"
    unknown = "unknown"


class PlantCondition(str, Enum):
    healthy = "healthy"
    yellowing = "yellowing"
    spots = "spots"
    pest_damage = "pest_damage"
    drought_stress = "drought_stress"
    disease_suspected = "disease_suspected"
    weed_pressure = "weed_pressure"
    mechanical_damage = "mechanical_damage"
    unknown = "unknown"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"
    unknown = "unknown"


class EventType(str, Enum):
    observation = "observation"
    fertilization = "fertilization"
    compost = "compost"
    irrigation = "irrigation"
    pest_treatment = "pest_treatment"
    herbicide = "herbicide"
    weed_control = "weed_control"
    maintenance = "maintenance"
    follow_up_inspection = "follow_up_inspection"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class RecommendedTask(BaseModel):
    """A task Hermes suggests. `needs_approval` gates dangerous/expensive work."""

    title: str
    priority: TaskPriority = TaskPriority.medium
    due_in_days: Optional[int] = None
    description: Optional[str] = None
    needs_approval: bool = False


# --------------------------------------------------------------------------- #
# Hermes AI output contract
# --------------------------------------------------------------------------- #
class HermesOutput(BaseModel):
    """Strict schema the vision model MUST return (validated before DB write)."""

    image_type: ImageType = ImageType.unknown
    plant_condition: PlantCondition = PlantCondition.unknown
    suspected_issue: Optional[str] = None
    diagnosis: Optional[str] = None
    severity: Severity = Severity.unknown
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    visible_symptoms: List[str] = Field(default_factory=list)
    agronomic_summary: str = ""
    recommended_next_step: str = ""
    recommended_tasks: List[RecommendedTask] = Field(default_factory=list)
    needs_human_review: bool = True
    escalation_recommended: bool = False
    escalation_reason: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, v))

    @field_validator("visible_symptoms", "missing_fields", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)


# --------------------------------------------------------------------------- #
# Agent input
# --------------------------------------------------------------------------- #
class HermesInput(BaseModel):
    image_url: str
    thumbnail_url: Optional[str] = None
    caption: Optional[str] = None
    user_id: Optional[int] = None
    source_channel: str = "telegram"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: Optional[datetime] = None
    lot_id: Optional[int] = None


# --------------------------------------------------------------------------- #
# API: observations
# --------------------------------------------------------------------------- #
class ObservationCreate(BaseModel):
    user_id: Optional[int] = None
    lot_id: Optional[int] = None
    source_channel: str = "api"
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    original_caption: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observed_at: Optional[datetime] = None


class EvidenceRecordCreate(BaseModel):
    """Manual field record (MVP). A human note is REQUIRED. No AI is invoked."""

    manual_note: str = Field(..., min_length=1)
    event_type: EventType = EventType.observation
    process_type: Optional[str] = None
    responsible_person: Optional[str] = None
    follow_up_needed: bool = False
    follow_up_date: Optional[datetime] = None
    lot_id: Optional[int] = None
    passport_id: Optional[int] = None
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observed_at: Optional[datetime] = None
    source_channel: str = "api"
    user_id: Optional[int] = None


class FieldNoteReview(BaseModel):
    """Supervisor/agronomist review of a submitted field record."""

    event_type: Optional[EventType] = None
    process_type: Optional[str] = None
    agronomist_notes: Optional[str] = None
    responsible_person: Optional[str] = None
    approved: Optional[bool] = None
    request_followup: Optional[bool] = None
    follow_up_date: Optional[datetime] = None
    reviewed_by: Optional[str] = None


class WeatherRead(BaseModel):
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    recent_rain_mm: Optional[float] = None
    heat_risk: Optional[str] = None
    drought_risk: Optional[str] = None
    weather_source: Optional[str] = None

    model_config = {"from_attributes": True}


class EscalationRead(BaseModel):
    id: int
    channel: str
    recipient: str
    escalation_reason: Optional[str] = None
    message_body: Optional[str] = None
    status: str
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ObservationRead(BaseModel):
    id: int
    user_id: Optional[int] = None
    farm_id: Optional[int] = None
    lot_id: Optional[int] = None
    source_channel: str
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    original_caption: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observed_at: Optional[datetime] = None
    passport_id: Optional[int] = None
    image_type: str
    plant_condition: str
    suspected_issue: Optional[str] = None
    diagnosis: Optional[str] = None
    severity: str
    confidence: float
    visible_symptoms_json: Optional[List[str]] = None
    ai_summary: Optional[str] = None
    recommended_next_step: Optional[str] = None
    needs_human_review: bool
    human_verified: bool
    human_correction: Optional[str] = None
    human_validation_status: str = "pending"
    human_corrected_label: Optional[str] = None
    human_notes: Optional[str] = None
    validated_by: Optional[str] = None
    validated_at: Optional[datetime] = None
    # Human-centered record fields (MVP)
    manual_note: Optional[str] = None
    event_type: str = "observation"
    process_type: Optional[str] = None
    responsible_person: Optional[str] = None
    follow_up_needed: bool = False
    follow_up_date: Optional[datetime] = None
    agronomist_notes: Optional[str] = None
    review_status: str = "pending_review"
    status: str
    escalation_status: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ObservationDetail(ObservationRead):
    weather: Optional[WeatherRead] = None
    escalations: List[EscalationRead] = Field(default_factory=list)


class ValidateRequest(BaseModel):
    """Human validation of an AI observation (training-quality feedback)."""

    status: str  # confirmed | corrected | rejected
    corrected_label: Optional[str] = None
    corrected_severity: Optional[Severity] = None
    notes: Optional[str] = None
    validated_by: Optional[str] = None


class VerifyRequest(BaseModel):
    human_verified: bool = True
    lot_id: Optional[int] = None
    status: Optional[str] = None


class CorrectRequest(BaseModel):
    human_correction: str
    corrected_plant_condition: Optional[PlantCondition] = None
    corrected_severity: Optional[Severity] = None
    corrected_suspected_issue: Optional[str] = None


# --------------------------------------------------------------------------- #
# API: lots
# --------------------------------------------------------------------------- #
class LotCreate(BaseModel):
    farm_id: Optional[int] = None
    lot_code: str
    crop_type: str = "agave_azul"
    estimated_age_months: Optional[int] = None
    centroid_latitude: Optional[float] = None
    centroid_longitude: Optional[float] = None
    polygon_geojson: Optional[dict] = None
    notes: Optional[str] = None


class LotRead(BaseModel):
    id: int
    farm_id: Optional[int] = None
    lot_code: str
    crop_type: str
    estimated_age_months: Optional[int] = None
    centroid_latitude: Optional[float] = None
    centroid_longitude: Optional[float] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# API: dashboard
# --------------------------------------------------------------------------- #
class MapPoint(BaseModel):
    observation_id: int
    latitude: float
    longitude: float
    severity: str
    suspected_issue: Optional[str] = None
    thumbnail_url: Optional[str] = None
    ai_summary: Optional[str] = None


# --------------------------------------------------------------------------- #
# API: passports
# --------------------------------------------------------------------------- #
class PassportCreate(BaseModel):
    passport_code: Optional[str] = None
    farm_id: Optional[int] = None
    lot_id: Optional[int] = None
    zone_id: Optional[int] = None
    label: Optional[str] = None
    field_name: Optional[str] = None
    lot_name: Optional[str] = None
    zone_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    estimated_age_months: Optional[int] = None
    notes: Optional[str] = None


class PassportUpdate(BaseModel):
    label: Optional[str] = None
    health_status: Optional[str] = None
    risk_level: Optional[str] = None
    estimated_age_months: Optional[int] = None
    next_inspection_at: Optional[datetime] = None
    notes: Optional[str] = None


class PassportRead(BaseModel):
    id: int
    passport_code: str
    farm_id: Optional[int] = None
    lot_id: Optional[int] = None
    zone_id: Optional[int] = None
    label: Optional[str] = None
    field_name: Optional[str] = None
    lot_name: Optional[str] = None
    zone_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    estimated_age_months: Optional[int] = None
    health_status: str
    risk_level: str
    last_inspection_at: Optional[datetime] = None
    next_inspection_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PassportDetail(PassportRead):
    observations: List[ObservationRead] = Field(default_factory=list)
    tasks: List["TaskRead"] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# API: tasks
# --------------------------------------------------------------------------- #
class TaskCreate(BaseModel):
    passport_id: Optional[int] = None
    observation_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.medium
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    source: str = "human_created"
    needs_approval: bool = False


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    approved: Optional[bool] = None


class TaskRead(BaseModel):
    id: int
    passport_id: Optional[int] = None
    observation_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    source: str
    needs_approval: bool
    approved: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# API: alerts
# --------------------------------------------------------------------------- #
class AlertRead(BaseModel):
    id: int
    passport_id: Optional[int] = None
    observation_id: Optional[int] = None
    recipient: Optional[str] = None
    channel: str
    title: str
    message: Optional[str] = None
    severity: str
    reason: Optional[str] = None
    delivery_status: str
    read: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EscalateRequest(BaseModel):
    observation_id: Optional[int] = None
    passport_id: Optional[int] = None
    title: Optional[str] = None
    message: Optional[str] = None
    severity: str = "high"
    recipient: Optional[str] = None
    channel: Optional[str] = None


# --------------------------------------------------------------------------- #
# API: map / weather / reports
# --------------------------------------------------------------------------- #
class ZoneMapPoint(BaseModel):
    field_name: Optional[str] = None
    lot_name: Optional[str] = None
    zone_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    severity: str = "unknown"
    status: str = "unknown"
    latest_photo: Optional[str] = None
    latest_observation: Optional[str] = None
    inspection_date: Optional[datetime] = None
    passport_id: Optional[int] = None


# Resolve forward reference (PassportDetail -> TaskRead).
PassportDetail.model_rebuild()

