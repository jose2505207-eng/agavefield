"""Weather enrichment via Open-Meteo (no API key required).

Given lat/lon (+ optional timestamp) we fetch current conditions plus recent
precipitation, normalize them, and derive simple heat/drought risk flags that
the escalation engine and dashboard can use. Network/credential failures
return ``None`` so the observation pipeline continues.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, TypedDict

import httpx

logger = logging.getLogger("agave.weather")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherSnapshotData(TypedDict, total=False):
    latitude: float
    longitude: float
    temperature_c: Optional[float]
    humidity_percent: Optional[float]
    precipitation_mm: Optional[float]
    wind_speed_kmh: Optional[float]
    recent_rain_mm: Optional[float]
    heat_risk: str
    drought_risk: str
    weather_source: str
    raw_json: dict


def _heat_risk(temp_c: Optional[float]) -> str:
    if temp_c is None:
        return "unknown"
    if temp_c >= 38:
        return "high"
    if temp_c >= 32:
        return "medium"
    return "low"


def _drought_risk(recent_rain_mm: Optional[float], humidity: Optional[float]) -> str:
    if recent_rain_mm is None:
        return "unknown"
    if recent_rain_mm < 2 and (humidity is None or humidity < 40):
        return "high"
    if recent_rain_mm < 10:
        return "medium"
    return "low"


def fetch_weather(
    latitude: float,
    longitude: float,
    timestamp: Optional[datetime] = None,
    timeout: float = 15.0,
) -> Optional[WeatherSnapshotData]:
    """Fetch and normalize current + recent weather. Returns None on failure."""
    if latitude is None or longitude is None:
        return None

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "daily": "precipitation_sum",
        "past_days": 7,
        "forecast_days": 1,
        "timezone": "auto",
        "wind_speed_unit": "kmh",
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Weather fetch failed for (%s,%s): %s", latitude, longitude, exc)
        return None

    return normalize_open_meteo(data, latitude, longitude)


def normalize_open_meteo(data: dict, latitude: float, longitude: float) -> WeatherSnapshotData:
    current = data.get("current", {}) or {}
    daily = data.get("daily", {}) or {}

    temp = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    precip = current.get("precipitation")
    wind = current.get("wind_speed_10m")

    recent_rain = None
    sums = daily.get("precipitation_sum")
    if isinstance(sums, list) and sums:
        recent_rain = round(sum(v for v in sums if v is not None), 2)

    return WeatherSnapshotData(
        latitude=latitude,
        longitude=longitude,
        temperature_c=temp,
        humidity_percent=humidity,
        precipitation_mm=precip,
        wind_speed_kmh=wind,
        recent_rain_mm=recent_rain,
        heat_risk=_heat_risk(temp),
        drought_risk=_drought_risk(recent_rain, humidity),
        weather_source="open-meteo",
        raw_json=data,
    )


# --------------------------------------------------------------------------- #
# Provider-backed API for dashboard / alerts / tasks
# --------------------------------------------------------------------------- #
def get_current_weather(latitude: float, longitude: float) -> Optional[dict]:
    """Real current weather, or None if unavailable.

    No fabricated fallback: callers surface "data not available" when this is
    None (unless WEATHER_PROVIDER is explicitly set to "mock" for local dev).
    """
    from app.integrations.weather_provider import get_weather_provider

    return get_weather_provider().current(latitude, longitude)


def get_forecast(latitude: float, longitude: float, days: int = 3) -> list[dict]:
    """Real forecast, or [] if unavailable (no fabricated fallback)."""
    from app.integrations.weather_provider import get_weather_provider

    return get_weather_provider().forecast(latitude, longitude, days)


def treatment_warning(forecast: list[dict]) -> Optional[str]:
    """Warn against applying treatments if rain/frost is expected soon."""
    for day in forecast[:2]:
        prob = day.get("precip_prob") or 0
        mm = day.get("precip_mm") or 0
        if prob >= 60 or mm >= 5:
            return (
                f"Avoid applying treatment around {day['date']}: rain expected "
                f"({prob}% / {mm} mm). Treatment may wash off or be ineffective."
            )
        if (day.get("temp_min_c") or 99) <= 2:
            return f"Cold/frost risk on {day['date']}: postpone sensitive operations."
    return None


def weather_context(latitude: Optional[float], longitude: Optional[float]) -> dict:
    """Bundle current + forecast + treatment warning for an observation/dashboard."""
    if latitude is None or longitude is None:
        return {"available": False, "reason": "no coordinates"}
    current = get_current_weather(latitude, longitude)
    forecast = get_forecast(latitude, longitude, days=3)
    warning = treatment_warning(forecast)
    has_risk = bool(
        current
        and (current.get("heat_risk") == "high" or current.get("frost_risk") == "high")
    ) or warning is not None
    return {
        "available": current is not None,
        "current": current,
        "forecast": forecast,
        "treatment_warning": warning,
        "weather_risk": has_risk,
    }
