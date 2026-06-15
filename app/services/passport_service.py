"""Agave Passport: the persistent memory of a plant / row / zone / lot.

A passport aggregates the latest health & risk state plus history. The Hermes
flow upserts a passport per observation: by explicit id, else by lot (+zone),
else by GPS proximity, else it creates a new one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.database import AgavePassport, FieldObservation, Lot
from app.services.lot_matching_service import _haversine_km

logger = logging.getLogger("agave.passport")

# Days until the next recommended inspection, by severity.
_NEXT_INSPECTION_DAYS = {
    "critical": 2,
    "high": 3,
    "urgent": 2,
    "medium": 7,
    "low": 14,
    "unknown": 7,
}
_RISK_FROM_SEVERITY = {
    "critical": "critical",
    "high": "high",
    "urgent": "high",
    "medium": "medium",
    "low": "low",
    "unknown": "unknown",
}
_GPS_MATCH_KM = 0.05  # ~50 m: same plant/zone cluster


def generate_passport_code(db: Session, prefix: str = "AGV") -> str:
    count = db.scalar(select(func.count(AgavePassport.id))) or 0
    return f"{prefix}-{count + 1:05d}"


def get_passport(db: Session, passport_id: int) -> Optional[AgavePassport]:
    return db.get(AgavePassport, passport_id)


def list_passports(db: Session, limit: int = 200) -> list[AgavePassport]:
    return list(
        db.execute(select(AgavePassport).order_by(AgavePassport.updated_at.desc()).limit(limit))
        .scalars()
        .all()
    )


def create_passport(db: Session, **fields) -> AgavePassport:
    if not fields.get("passport_code"):
        fields["passport_code"] = generate_passport_code(db)
    p = AgavePassport(**{k: v for k, v in fields.items() if v is not None})
    db.add(p)
    db.flush()
    return p


def get_or_create_for_observation(
    db: Session,
    *,
    lot: Optional[Lot],
    latitude: Optional[float],
    longitude: Optional[float],
    field_name: Optional[str] = None,
    zone_name: Optional[str] = None,
) -> AgavePassport:
    # 1) Existing passport for this lot.
    if lot is not None:
        existing = db.execute(
            select(AgavePassport).where(AgavePassport.lot_id == lot.id)
        ).scalars().first()
        if existing:
            return existing

    # 2) Nearest passport within the GPS cluster radius.
    if latitude is not None and longitude is not None:
        for p in db.execute(
            select(AgavePassport).where(
                AgavePassport.latitude.is_not(None), AgavePassport.longitude.is_not(None)
            )
        ).scalars():
            if _haversine_km(latitude, longitude, p.latitude, p.longitude) <= _GPS_MATCH_KM:
                return p

    # 3) Create a new passport.
    return create_passport(
        db,
        lot_id=lot.id if lot else None,
        farm_id=lot.farm_id if lot else None,
        lot_name=lot.lot_code if lot else None,
        field_name=field_name,
        zone_name=zone_name,
        latitude=latitude,
        longitude=longitude,
        estimated_age_months=lot.estimated_age_months if lot else None,
        label=(lot.lot_code if lot else "Field observation"),
    )


def update_from_observation(
    db: Session, passport: AgavePassport, observation: FieldObservation
) -> AgavePassport:
    """Refresh the passport's rolling state after a new observation."""
    passport.health_status = observation.plant_condition or passport.health_status
    passport.risk_level = _RISK_FROM_SEVERITY.get(observation.severity, passport.risk_level)
    observed = observation.observed_at or datetime.utcnow()
    passport.last_inspection_at = observed
    days = _NEXT_INSPECTION_DAYS.get(observation.severity, 7)
    passport.next_inspection_at = observed + timedelta(days=days)
    if passport.latitude is None and observation.latitude is not None:
        passport.latitude = observation.latitude
        passport.longitude = observation.longitude
    db.flush()
    return passport


def update_passport(db: Session, passport_id: int, **fields) -> Optional[AgavePassport]:
    p = db.get(AgavePassport, passport_id)
    if not p:
        return None
    for k, v in fields.items():
        if v is not None:
            setattr(p, k, v)
    db.flush()
    return p


def get_photos(db: Session, passport_id: int) -> list[FieldObservation]:
    """Chronological photo history for a passport (oldest first)."""
    return list(
        db.execute(
            select(FieldObservation)
            .where(
                FieldObservation.passport_id == passport_id,
                FieldObservation.image_url.is_not(None),
            )
            .order_by(FieldObservation.observed_at.asc())
        )
        .scalars()
        .all()
    )
