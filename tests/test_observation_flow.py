"""End-to-end observation flow through the Hermes agent (offline stub)."""
from __future__ import annotations

import pytest

from app.agents import hermes_agent
from app.models.database import Lot, ModelOutput, WeatherSnapshot
from app.models.schemas import CorrectRequest, HermesInput
from app.services import observation_service, weather_service


@pytest.fixture(autouse=True)
def _no_network_weather(monkeypatch):
    """Stub weather so the flow never hits the network."""
    monkeypatch.setattr(
        weather_service,
        "fetch_weather",
        lambda lat, lon, ts=None: {
            "latitude": lat,
            "longitude": lon,
            "temperature_c": 33.0,
            "humidity_percent": 35.0,
            "precipitation_mm": 0.0,
            "wind_speed_kmh": 10.0,
            "recent_rain_mm": 1.0,
            "heat_risk": "medium",
            "drought_risk": "high",
            "weather_source": "test",
            "raw_json": {},
        },
    )


def test_full_observation_flow_persists_evidence(db):
    user = observation_service.get_or_create_user(db, telegram_user_id="555")
    result = hermes_agent.run(
        db,
        HermesInput(
            image_url="http://example/img.jpg",
            caption="hojas amarillas en el lote",
            user_id=user.id,
            source_channel="telegram",
            latitude=20.67,
            longitude=-103.39,
        ),
    )
    obs = result.observation
    assert obs.id is not None
    assert obs.plant_condition == "yellowing"
    assert obs.needs_human_review is True  # stub always needs review

    # Immutable model output recorded.
    mo = db.query(ModelOutput).filter_by(observation_id=obs.id).all()
    assert len(mo) == 1
    assert mo[0].raw_json["plant_condition"] == "yellowing"

    # Weather snapshot linked.
    ws = db.query(WeatherSnapshot).filter_by(observation_id=obs.id).all()
    assert len(ws) == 1
    assert ws[0].drought_risk == "high"

    # Reply text is useful.
    assert "Observation saved" in result.reply_text
    assert "Severity" in result.reply_text


def test_high_severity_creates_escalation_record(db):
    user = observation_service.get_or_create_user(db, telegram_user_id="777")
    result = hermes_agent.run(
        db,
        HermesInput(
            image_url="http://example/img.jpg",
            caption="plaga fuerte, riesgo alto, urgente",  # forces high severity in stub
            user_id=user.id,
            source_channel="telegram",
        ),
    )
    obs = observation_service.get_observation(db, result.observation.id)
    assert obs.severity == "high"
    # An escalation record must exist (delivery may fail without credentials).
    assert len(obs.escalations) >= 1
    assert obs.escalations[0].escalation_reason is not None


def test_correction_preserves_original_model_output(db):
    user = observation_service.get_or_create_user(db, telegram_user_id="888")
    result = hermes_agent.run(
        db,
        HermesInput(image_url="http://x/i.jpg", caption="mancha", user_id=user.id),
    )
    obs_id = result.observation.id
    original = db.query(ModelOutput).filter_by(observation_id=obs_id).first()
    original_condition = original.raw_json["plant_condition"]

    observation_service.correct_observation(
        db,
        obs_id,
        CorrectRequest(human_correction="Actually mechanical damage", corrected_severity="low"),
    )
    db.commit()

    obs = observation_service.get_observation(db, obs_id)
    assert obs.human_verified is True
    assert obs.human_correction == "Actually mechanical damage"
    assert obs.severity == "low"
    # Original model output untouched.
    preserved = db.query(ModelOutput).filter_by(observation_id=obs_id).first()
    assert preserved.raw_json["plant_condition"] == original_condition


def test_lot_matching_by_centroid(db):
    lot = Lot(lot_code="JAL-01", centroid_latitude=20.670, centroid_longitude=-103.390)
    db.add(lot)
    db.flush()
    user = observation_service.get_or_create_user(db, telegram_user_id="999")
    result = hermes_agent.run(
        db,
        HermesInput(
            image_url="http://x/i.jpg",
            caption="planta",
            user_id=user.id,
            latitude=20.6705,
            longitude=-103.3902,
        ),
    )
    assert result.observation.lot_id == lot.id
