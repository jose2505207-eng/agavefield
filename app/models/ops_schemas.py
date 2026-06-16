"""Pydantic schemas for the operations / traceability layer."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enums (controlled vocabularies)
# --------------------------------------------------------------------------- #
class AssigneeRole(str, Enum):
    field_worker = "field_worker"
    agronomist = "agronomist"
    supervisor = "supervisor"
    admin = "admin"
    other = "other"


class CarbonFactorUnit(str, Enum):
    per_ha = "kgCO2e_per_ha"
    per_m2 = "kgCO2e_per_m2"
    per_kg_product = "kgCO2e_per_kg_product"
    per_liter = "kgCO2e_per_liter"
    per_event = "kgCO2e_per_event"


# --------------------------------------------------------------------------- #
# Assignee
# --------------------------------------------------------------------------- #
class AssigneeCreate(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    role: AssigneeRole = AssigneeRole.field_worker
    preferred_language: Optional[str] = None
    notes: Optional[str] = None


class AssigneeUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[AssigneeRole] = None
    active: Optional[bool] = None
    preferred_language: Optional[str] = None
    notes: Optional[str] = None


class AssigneeRead(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    role: str
    active: bool
    preferred_language: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Product
# --------------------------------------------------------------------------- #
class ProductCreate(BaseModel):
    product_name: str
    product_type: str = "other"
    active_ingredient: Optional[str] = None
    allowed: bool = True
    restricted: bool = False
    prohibited: bool = False
    default_dose_value: Optional[float] = None
    default_dose_unit: Optional[str] = None
    min_dose_value: Optional[float] = None
    max_dose_value: Optional[float] = None
    application_method: Optional[str] = None
    safety_notes: Optional[str] = None
    regenerative_notes: Optional[str] = None
    carbon_factor_value: Optional[float] = None
    carbon_factor_unit: Optional[CarbonFactorUnit] = None
    carbon_factor_source: Optional[str] = None
    carbon_factor_version: Optional[str] = None
    carbon_notes: Optional[str] = None
    created_by: Optional[str] = None


class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    product_type: Optional[str] = None
    active_ingredient: Optional[str] = None
    allowed: Optional[bool] = None
    restricted: Optional[bool] = None
    prohibited: Optional[bool] = None
    default_dose_value: Optional[float] = None
    default_dose_unit: Optional[str] = None
    min_dose_value: Optional[float] = None
    max_dose_value: Optional[float] = None
    application_method: Optional[str] = None
    safety_notes: Optional[str] = None
    regenerative_notes: Optional[str] = None
    carbon_factor_value: Optional[float] = None
    carbon_factor_unit: Optional[CarbonFactorUnit] = None
    carbon_factor_source: Optional[str] = None
    carbon_factor_version: Optional[str] = None
    carbon_notes: Optional[str] = None
    active: Optional[bool] = None


class ProductRead(BaseModel):
    id: int
    product_name: str
    product_type: str
    active_ingredient: Optional[str] = None
    allowed: bool
    restricted: bool
    prohibited: bool
    default_dose_value: Optional[float] = None
    default_dose_unit: Optional[str] = None
    min_dose_value: Optional[float] = None
    max_dose_value: Optional[float] = None
    application_method: Optional[str] = None
    safety_notes: Optional[str] = None
    regenerative_notes: Optional[str] = None
    carbon_factor_value: Optional[float] = None
    carbon_factor_unit: Optional[str] = None
    carbon_factor_source: Optional[str] = None
    carbon_factor_version: Optional[str] = None
    carbon_notes: Optional[str] = None
    active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Activity
# --------------------------------------------------------------------------- #
class ActivityCreate(BaseModel):
    activity_name: str
    activity_category: str = "other"
    description: Optional[str] = None
    allowed: bool = True
    requires_product: bool = False
    requires_photo_evidence: bool = True
    default_required_photo_count: int = 1
    requires_geolocation: bool = True
    requires_surface_area: bool = False
    requires_dose: bool = False
    requires_weather_snapshot: bool = True
    default_follow_up_days: Optional[int] = None
    recommended_frequency: Optional[str] = None
    carbon_factor_value: Optional[float] = None
    carbon_factor_unit: Optional[CarbonFactorUnit] = None
    carbon_category: Optional[str] = None
    carbon_methodology_note: Optional[str] = None
    carbon_factor_source: Optional[str] = None
    carbon_factor_version: Optional[str] = None
    created_by: Optional[str] = None


class ActivityUpdate(BaseModel):
    activity_name: Optional[str] = None
    activity_category: Optional[str] = None
    description: Optional[str] = None
    allowed: Optional[bool] = None
    requires_product: Optional[bool] = None
    requires_photo_evidence: Optional[bool] = None
    default_required_photo_count: Optional[int] = None
    requires_geolocation: Optional[bool] = None
    requires_surface_area: Optional[bool] = None
    requires_dose: Optional[bool] = None
    requires_weather_snapshot: Optional[bool] = None
    default_follow_up_days: Optional[int] = None
    recommended_frequency: Optional[str] = None
    carbon_factor_value: Optional[float] = None
    carbon_factor_unit: Optional[CarbonFactorUnit] = None
    carbon_category: Optional[str] = None
    carbon_methodology_note: Optional[str] = None
    carbon_factor_source: Optional[str] = None
    carbon_factor_version: Optional[str] = None
    active: Optional[bool] = None


class WorkOrderItemCreate(BaseModel):
    activity_id: int
    product_id: Optional[int] = None
    instructions: Optional[str] = None
    planned_surface_area_value: Optional[float] = None
    planned_surface_area_unit: Optional[str] = None  # ha | m2
    planned_dose_value: Optional[float] = None
    planned_dose_unit: Optional[str] = None
    planned_total_product_value: Optional[float] = None
    planned_total_product_unit: Optional[str] = None  # kg | l
    required_photo_count: int = 1
    requires_geolocation: bool = True
    requires_weather_snapshot: bool = True
    requires_manual_note: bool = True


class WorkOrderItemRead(BaseModel):
    id: int
    work_order_id: int
    activity_id: int
    product_id: Optional[int] = None
    instructions: Optional[str] = None
    planned_surface_area_value: Optional[float] = None
    planned_surface_area_unit: Optional[str] = None
    planned_dose_value: Optional[float] = None
    planned_dose_unit: Optional[str] = None
    planned_total_product_value: Optional[float] = None
    planned_total_product_unit: Optional[str] = None
    required_photo_count: int
    requires_geolocation: bool
    requires_weather_snapshot: bool
    requires_manual_note: bool
    planned_carbon_factor_value: Optional[float] = None
    planned_carbon_factor_unit: Optional[str] = None
    planned_carbon_kgco2e: Optional[float] = None
    carbon_factor_snapshot: Optional[dict] = None
    status: str

    model_config = {"from_attributes": True}


class WorkOrderCreate(BaseModel):
    title: str
    description: Optional[str] = None
    field_id: Optional[int] = None
    lot_id: Optional[int] = None
    zone_id: Optional[int] = None
    agave_passport_id: Optional[int] = None
    season_id: Optional[int] = None
    planned_start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    assigned_to_id: Optional[int] = None
    assigned_to_email: Optional[str] = None
    created_by: Optional[str] = None
    required_photo_evidence_count: int = 1
    geolocation_required: bool = True
    manual_note_required: bool = True
    weather_capture_required: bool = True
    review_required: bool = True
    items: list[WorkOrderItemCreate] = Field(default_factory=list)


class WorkOrderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    planned_start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    assigned_to_id: Optional[int] = None
    assigned_to_email: Optional[str] = None
    status: Optional[str] = None


class WorkOrderRead(BaseModel):
    id: int
    work_order_code: str
    title: str
    description: Optional[str] = None
    field_id: Optional[int] = None
    lot_id: Optional[int] = None
    zone_id: Optional[int] = None
    agave_passport_id: Optional[int] = None
    season_id: Optional[int] = None
    planned_start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    assigned_to_id: Optional[int] = None
    assigned_to_email: Optional[str] = None
    created_by: Optional[str] = None
    status: str
    sent_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    secure_link_expires_at: Optional[datetime] = None
    required_photo_evidence_count: int
    geolocation_required: bool
    manual_note_required: bool
    weather_capture_required: bool
    review_required: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkOrderDetail(WorkOrderRead):
    items: list[WorkOrderItemRead] = Field(default_factory=list)


class ActivityRead(BaseModel):
    id: int
    activity_name: str
    activity_category: str
    description: Optional[str] = None
    allowed: bool
    requires_product: bool
    requires_photo_evidence: bool
    default_required_photo_count: int
    requires_geolocation: bool
    requires_surface_area: bool
    requires_dose: bool
    requires_weather_snapshot: bool
    default_follow_up_days: Optional[int] = None
    recommended_frequency: Optional[str] = None
    carbon_factor_value: Optional[float] = None
    carbon_factor_unit: Optional[str] = None
    carbon_category: Optional[str] = None
    carbon_methodology_note: Optional[str] = None
    carbon_factor_source: Optional[str] = None
    carbon_factor_version: Optional[str] = None
    active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
