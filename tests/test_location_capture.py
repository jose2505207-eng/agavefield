"""One-tap location capture: attaching a shared location to an observation."""
from __future__ import annotations

import pytest

from app.agents import hermes_agent
from app.models.database import Lot, WeatherSnapshot
from app.models.schemas import HermesInput
from app.services import observation_service, weather_service


@pytest.fixture(autouse=True)
def _fake_weather(monkeypatch):
    monkeypatch.setattr(
        weather_service,
        "fetch_weather",
        lambda lat, lon, ts=None: {
            "latitude": lat, "longitude": lon, "temperature_c": 30.0,
            "humidity_percent": 40.0, "precipitation_mm": 0.0, "wind_speed_kmh": 8.0,
            "recent_rain_mm": 3.0, "heat_risk": "low", "drought_risk": "medium",
            "weather_source": "test", "raw_json": {},
        },
    )


def _photo_without_location(db, user, caption="hojas amarillas"):
    return hermes_agent.run(
        db,
        HermesInput(image_url="http://x/i.jpg", caption=caption, user_id=user.id),
    ).observation


def test_latest_unlocated_observation_selects_newest_without_coords(db):
    user = observation_service.get_or_create_user(db, telegram_user_id="100")
    o1 = _photo_without_location(db, user)
    o2 = _photo_without_location(db, user)
    latest = observation_service.latest_unlocated_observation(db, user.id)
    assert latest.id == o2.id  # newest first
    # Once located, it is no longer a candidate.
    observation_service.set_observation_location(db, o2, 20.88, -103.83)
    assert observation_service.latest_unlocated_observation(db, user.id).id == o1.id


def test_set_observation_location_enriches(db):
    lot = Lot(lot_code="LOC-1", centroid_latitude=20.8806, centroid_longitude=-103.8366)
    db.add(lot)
    db.flush()
    user = observation_service.get_or_create_user(db, telegram_user_id="200")
    obs = _photo_without_location(db, user)
    assert obs.latitude is None and obs.lot_id is None

    observation_service.set_observation_location(db, obs, 20.8806, -103.8366)
    db.commit()

    refreshed = observation_service.get_observation(db, obs.id)
    assert refreshed.latitude == 20.8806
    assert refreshed.lot_id == lot.id            # matched the lot by centroid
    assert refreshed.passport_id is not None     # passport linked
    assert db.query(WeatherSnapshot).filter_by(observation_id=obs.id).count() == 1


def test_location_webhook_attaches_to_latest(db, monkeypatch):
    """End-to-end via the webhook (telegram send mocked).

    The webhook offloads to a BackgroundTask; Starlette's TestClient runs it
    before returning, so location attachment happens within the request.
    """
    import app.api.telegram_routes as tr
    monkeypatch.setattr(tr.telegram_client, "send_message", lambda *a, **k: None)

    user = observation_service.get_or_create_user(db, telegram_user_id="300")
    obs = _photo_without_location(db, user)
    obs_id = obs.id
    db.commit()

    from fastapi.testclient import TestClient
    from app.db import SessionLocal
    from app.main import app
    with TestClient(app) as c:
        update = {"message": {"message_id": 5, "date": 1718000000,
                  "chat": {"id": 300}, "from": {"id": 300, "first_name": "F"},
                  "location": {"latitude": 20.5, "longitude": -103.5}}}
        r = c.post("/webhooks/telegram", json=update)
        assert r.status_code == 200

    # Read in a fresh session to see the webhook's committed write.
    fresh = SessionLocal()
    try:
        refreshed = observation_service.get_observation(fresh, obs_id)
        assert refreshed.latitude == 20.5 and refreshed.longitude == -103.5
    finally:
        fresh.close()
