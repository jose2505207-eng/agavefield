"""Weather normalization + risk classification (offline)."""
from __future__ import annotations

from app.services import weather_service as ws


def test_normalize_open_meteo():
    sample = {
        "current": {
            "temperature_2m": 35.0,
            "relative_humidity_2m": 30,
            "precipitation": 0.0,
            "wind_speed_10m": 12.0,
        },
        "daily": {"precipitation_sum": [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]},
    }
    out = ws.normalize_open_meteo(sample, 20.6, -103.4)
    assert out["temperature_c"] == 35.0
    assert out["recent_rain_mm"] == 1.0
    assert out["weather_source"] == "open-meteo"
    assert out["heat_risk"] == "medium"  # 32 <= 35 < 38
    assert out["drought_risk"] == "high"  # <2mm rain and humidity < 40


def test_heat_risk_levels():
    assert ws._heat_risk(40) == "high"
    assert ws._heat_risk(34) == "medium"
    assert ws._heat_risk(20) == "low"
    assert ws._heat_risk(None) == "unknown"


def test_drought_risk_levels():
    assert ws._drought_risk(0.5, 20) == "high"
    assert ws._drought_risk(5, 60) == "medium"
    assert ws._drought_risk(50, 80) == "low"
    assert ws._drought_risk(None, 50) == "unknown"


def test_fetch_weather_returns_none_without_coords():
    assert ws.fetch_weather(None, None) is None
