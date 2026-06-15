"""Weather providers behind a common interface.

Providers:
* MockWeatherProvider  — deterministic, offline, always available (local dev).
* OpenMeteoProvider    — real data, no API key required.
* OpenWeatherProvider  — used only when WEATHER_API_KEY is set.

Selection (WEATHER_PROVIDER): ``auto`` tries Open-Meteo and falls back to mock
on any failure, so the app NEVER breaks when no provider/key is configured.

All providers return the same normalized shape:
  current  -> dict(temperature_c, humidity_percent, precipitation_mm,
                    wind_speed_kmh, recent_rain_mm, heat_risk, drought_risk,
                    frost_risk, source)
  forecast -> list[dict(date, temp_max_c, temp_min_c, precip_prob, precip_mm)]
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("agave.weather.provider")


def heat_risk(temp_c: Optional[float]) -> str:
    if temp_c is None:
        return "unknown"
    return "high" if temp_c >= 38 else "medium" if temp_c >= 32 else "low"


def drought_risk(recent_rain_mm: Optional[float], humidity: Optional[float]) -> str:
    if recent_rain_mm is None:
        return "unknown"
    if recent_rain_mm < 2 and (humidity is None or humidity < 40):
        return "high"
    return "medium" if recent_rain_mm < 10 else "low"


def frost_risk(temp_min_c: Optional[float]) -> str:
    if temp_min_c is None:
        return "unknown"
    return "high" if temp_min_c <= 2 else "medium" if temp_min_c <= 6 else "low"


class WeatherProvider(ABC):
    name = "base"

    @abstractmethod
    def current(self, lat: float, lon: float) -> Optional[dict]:
        ...

    @abstractmethod
    def forecast(self, lat: float, lon: float, days: int = 3) -> list[dict]:
        ...


class MockWeatherProvider(WeatherProvider):
    name = "mock"

    def current(self, lat, lon) -> dict:
        return {
            "temperature_c": 31.0,
            "humidity_percent": 45.0,
            "precipitation_mm": 0.0,
            "wind_speed_kmh": 12.0,
            "recent_rain_mm": 6.0,
            "heat_risk": "medium",
            "drought_risk": "medium",
            "frost_risk": "low",
            "source": "mock",
        }

    def forecast(self, lat, lon, days=3) -> list[dict]:
        today = date.today()
        # Day 1 has rain so treatment warnings can be demonstrated locally.
        rain = [80, 10, 5]
        temps = [(34, 18), (33, 17), (35, 19)]
        out = []
        for i in range(min(days, 3)):
            out.append(
                {
                    "date": (today + timedelta(days=i + 1)).isoformat(),
                    "temp_max_c": temps[i][0],
                    "temp_min_c": temps[i][1],
                    "precip_prob": rain[i],
                    "precip_mm": rain[i] / 10.0,
                }
            )
        return out


class OpenMeteoProvider(WeatherProvider):
    name = "openmeteo"
    URL = "https://api.open-meteo.com/v1/forecast"

    def current(self, lat, lon) -> Optional[dict]:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "daily": "precipitation_sum,temperature_2m_min",
            "past_days": 7,
            "forecast_days": 1,
            "timezone": "auto",
            "wind_speed_unit": "kmh",
        }
        try:
            with httpx.Client(timeout=15.0) as c:
                resp = c.get(self.URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Open-Meteo current failed: %s", exc)
            return None
        cur = data.get("current", {})
        daily = data.get("daily", {})
        sums = daily.get("precipitation_sum") or []
        recent = round(sum(v for v in sums if v is not None), 2) if sums else None
        mins = daily.get("temperature_2m_min") or []
        temp = cur.get("temperature_2m")
        hum = cur.get("relative_humidity_2m")
        return {
            "temperature_c": temp,
            "humidity_percent": hum,
            "precipitation_mm": cur.get("precipitation"),
            "wind_speed_kmh": cur.get("wind_speed_10m"),
            "recent_rain_mm": recent,
            "heat_risk": heat_risk(temp),
            "drought_risk": drought_risk(recent, hum),
            "frost_risk": frost_risk(mins[-1] if mins else None),
            "source": "open-meteo",
        }

    def forecast(self, lat, lon, days=3) -> list[dict]:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
            "forecast_days": min(days + 1, 7),
            "timezone": "auto",
        }
        try:
            with httpx.Client(timeout=15.0) as c:
                resp = c.get(self.URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Open-Meteo forecast failed: %s", exc)
            return []
        d = data.get("daily", {})
        dates = d.get("time", [])
        out = []
        for i, day in enumerate(dates[1 : days + 1], start=1):  # skip today
            out.append(
                {
                    "date": day,
                    "temp_max_c": _idx(d.get("temperature_2m_max"), i),
                    "temp_min_c": _idx(d.get("temperature_2m_min"), i),
                    "precip_prob": _idx(d.get("precipitation_probability_max"), i),
                    "precip_mm": _idx(d.get("precipitation_sum"), i),
                }
            )
        return out


class OpenWeatherProvider(WeatherProvider):
    name = "openweather"
    URL = "https://api.openweathermap.org/data/2.5"

    def current(self, lat, lon) -> Optional[dict]:
        try:
            with httpx.Client(timeout=15.0) as c:
                resp = c.get(
                    f"{self.URL}/weather",
                    params={"lat": lat, "lon": lon, "appid": settings.weather_api_key, "units": "metric"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("OpenWeather current failed: %s", exc)
            return None
        main = data.get("main", {})
        temp = main.get("temp")
        hum = main.get("humidity")
        return {
            "temperature_c": temp,
            "humidity_percent": hum,
            "precipitation_mm": (data.get("rain") or {}).get("1h", 0.0),
            "wind_speed_kmh": (data.get("wind") or {}).get("speed", 0.0) * 3.6,
            "recent_rain_mm": None,
            "heat_risk": heat_risk(temp),
            "drought_risk": drought_risk(None, hum),
            "frost_risk": frost_risk(main.get("temp_min")),
            "source": "openweather",
        }

    def forecast(self, lat, lon, days=3) -> list[dict]:
        # Minimal: OpenWeather free tier is 3-hourly; left for later refinement.
        logger.info("OpenWeather forecast not implemented; returning empty")
        return []


def _idx(seq, i):
    try:
        return seq[i]
    except (TypeError, IndexError):
        return None


def get_weather_provider() -> WeatherProvider:
    choice = settings.weather_provider.lower()
    if choice == "mock":
        return MockWeatherProvider()
    if choice == "openweather" and settings.weather_api_key:
        return OpenWeatherProvider()
    if choice in ("openmeteo", "auto"):
        return OpenMeteoProvider()
    return MockWeatherProvider()
