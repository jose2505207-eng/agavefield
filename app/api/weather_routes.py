"""Weather API routes (provider-backed, never breaks without a key)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import weather_service

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/current")
def current(lat: float = Query(...), lon: float = Query(...)):
    data = weather_service.get_current_weather(lat, lon)
    return {"available": data is not None, "current": data}


@router.get("/forecast")
def forecast(lat: float = Query(...), lon: float = Query(...), days: int = Query(3, le=7)):
    fc = weather_service.get_forecast(lat, lon, days)
    return {
        "forecast": fc,
        "treatment_warning": weather_service.treatment_warning(fc),
    }


@router.get("/context")
def context(lat: float = Query(...), lon: float = Query(...)):
    return weather_service.weather_context(lat, lon)
