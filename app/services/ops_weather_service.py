"""Capture an operational weather snapshot for an execution location.

Rain-first for agave (current/probability/last-24h/next-24h) plus temperature.
Reuses the existing weather provider. NEVER raises into the submission flow —
on any failure it returns (None, "unavailable") so the work record is still saved.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.operations import OpsWeatherSnapshot
from app.services import weather_service

logger = logging.getLogger("agave.ops_weather")


def capture_snapshot(
    db: Session,
    *,
    latitude: Optional[float],
    longitude: Optional[float],
    field_id: Optional[int] = None,
    lot_id: Optional[int] = None,
    zone_id: Optional[int] = None,
) -> Tuple[Optional[OpsWeatherSnapshot], str]:
    if latitude is None or longitude is None:
        return None, "unavailable"
    try:
        current = weather_service.get_current_weather(latitude, longitude)
        forecast = weather_service.get_forecast(latitude, longitude, days=1)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Weather capture failed: %s", exc)
        return None, "unavailable"
    if not current:
        return None, "unavailable"

    next_day = forecast[0] if forecast else {}
    snap = OpsWeatherSnapshot(
        field_id=field_id, lot_id=lot_id, zone_id=zone_id,
        latitude=latitude, longitude=longitude,
        weather_datetime=datetime.utcnow(),
        provider=current.get("source"),
        rainfall_current=current.get("precipitation_mm"),
        rainfall_probability=next_day.get("precip_prob"),
        rainfall_last_24h=current.get("recent_rain_mm"),
        rainfall_next_24h=next_day.get("precip_mm"),
        temperature_current=current.get("temperature_c"),
        temperature_min=next_day.get("temp_min_c"),
        temperature_max=next_day.get("temp_max_c"),
        humidity=current.get("humidity_percent"),
        wind_speed=current.get("wind_speed_kmh"),
        raw_payload_json={"current": current, "forecast_day1": next_day},
    )
    db.add(snap)
    db.flush()
    return snap, "captured"
