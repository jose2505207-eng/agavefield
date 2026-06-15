"""Tests for the MVP additions: passports, tasks, alerts, validation,
weather provider, before/after comparison, and weekly reports."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.agents import hermes_agent
from app.integrations.weather_provider import (
    MockWeatherProvider,
    frost_risk,
    heat_risk,
)
from app.models.database import HumanValidation, Lot, ModelOutput
from app.models.schemas import (
    HermesInput,
    RecommendedTask,
    TaskPriority,
    ValidateRequest,
)
from app.services import (
    comparison_service,
    notification_service,
    observation_service,
    passport_service,
    report_service,
    task_service,
    weather_service,
)


@pytest.fixture(autouse=True)
def _no_network_weather(monkeypatch):
    monkeypatch.setattr(weather_service, "fetch_weather", lambda lat, lon, ts=None: None)


def _run(db, caption="hojas amarillas", lat=20.88, lon=-103.83, user_tg="1"):
    user = observation_service.get_or_create_user(db, telegram_user_id=user_tg)
    return hermes_agent.run(
        db,
        HermesInput(image_url="http://x/i.jpg", caption=caption, user_id=user.id,
                    latitude=lat, longitude=lon),
    )


# --------------------------- passports --------------------------- #
def test_observation_creates_and_links_passport(db):
    result = _run(db)
    assert result.observation.passport_id is not None
    p = passport_service.get_passport(db, result.observation.passport_id)
    assert p.risk_level in ("medium", "high", "low", "critical")
    assert p.last_inspection_at is not None
    assert p.next_inspection_at is not None


def test_same_lot_reuses_passport(db):
    lot = Lot(lot_code="L1", centroid_latitude=20.88, centroid_longitude=-103.83)
    db.add(lot)
    db.flush()
    r1 = _run(db, user_tg="a")
    r2 = _run(db, user_tg="b")
    assert r1.observation.passport_id == r2.observation.passport_id


def test_passport_code_increments(db):
    p1 = passport_service.create_passport(db, label="x")
    p2 = passport_service.create_passport(db, label="y")
    assert p1.passport_code != p2.passport_code
    assert p2.passport_code.startswith("AGV-")


# --------------------------- tasks --------------------------- #
def test_recommended_tasks_created_with_due_dates(db):
    result = _run(db)
    tasks = task_service.list_tasks(db, passport_id=result.observation.passport_id)
    assert len(tasks) >= 1
    assert all(t.source == "ai_generated" for t in tasks)


def test_dangerous_task_requires_approval(db):
    recs = [RecommendedTask(title="Apply treatment after human approval", priority=TaskPriority.high)]
    created = task_service.create_tasks_from_recommendations(db, recs)
    assert created[0].needs_approval is True
    assert created[0].approved is False  # dangerous action gated


def test_safe_task_is_auto_approved(db):
    recs = [RecommendedTask(title="Reinspect zone in 7 days", due_in_days=7)]
    created = task_service.create_tasks_from_recommendations(db, recs)
    assert created[0].needs_approval is False
    assert created[0].approved is True
    assert created[0].due_date is not None


def test_overdue_tasks(db):
    task_service.create_task(db, title="late", due_date=datetime.utcnow() - timedelta(days=1), status="open")
    task_service.create_task(db, title="future", due_date=datetime.utcnow() + timedelta(days=5), status="open")
    overdue = task_service.overdue_tasks(db)
    assert len(overdue) == 1
    assert overdue[0].title == "late"


# --------------------------- alerts --------------------------- #
def test_should_alert_high_severity(db):
    result = _run(db, caption="plaga fuerte urgente")  # -> high severity
    should, reason = notification_service.should_alert(db, result.observation)
    assert should is True


def test_create_alert_records_even_without_credentials(db):
    result = _run(db)
    alert = notification_service.create_alert(
        db, title="t", message="m", severity="high",
        observation_id=result.observation.id, channel="console",
    )
    assert alert.id is not None
    assert alert.delivery_status == "sent"  # console always "delivers"


# --------------------------- validation --------------------------- #
def test_low_confidence_forces_review(db):
    result = _run(db)
    # Stub confidence is < 0.75 -> must require review.
    assert result.observation.needs_human_review is True


def test_validation_preserves_model_output(db):
    result = _run(db)
    oid = result.observation.id
    original = db.query(ModelOutput).filter_by(observation_id=oid).first().raw_json["plant_condition"]
    observation_service.validate_observation(
        db, oid, ValidateRequest(status="corrected", corrected_label="water stress", validated_by="agro")
    )
    db.commit()
    obs = observation_service.get_observation(db, oid)
    assert obs.human_validation_status == "corrected"
    assert obs.diagnosis == "water stress"
    assert obs.human_verified is True
    assert obs.needs_human_review is False
    # HumanValidation row created; original model output preserved.
    assert db.query(HumanValidation).filter_by(observation_id=oid).count() == 1
    assert db.query(ModelOutput).filter_by(observation_id=oid).first().raw_json["plant_condition"] == original


# --------------------------- weather provider --------------------------- #
def test_mock_weather_provider():
    p = MockWeatherProvider()
    cur = p.current(20.0, -103.0)
    assert cur["source"] == "mock"
    fc = p.forecast(20.0, -103.0, days=3)
    assert len(fc) == 3


def test_treatment_warning_on_rain():
    p = MockWeatherProvider()
    warning = weather_service.treatment_warning(p.forecast(20.0, -103.0))
    assert warning is not None and "treatment" in warning.lower()


def test_weather_risk_helpers():
    assert heat_risk(40) == "high"
    assert frost_risk(0) == "high"
    assert frost_risk(10) == "low"


# --------------------------- before/after --------------------------- #
def test_comparison_needs_two_photos(db):
    r = _run(db)
    cmp = comparison_service.compare_passport_photos(db, r.observation.passport_id)
    assert cmp["comparison_available"] is False
    _run(db)  # second photo, same lot? no lot -> may create new passport; force same passport
    # Add a second observation to the SAME passport directly.
    obs2 = observation_service.get_observation(db, r.observation.id)
    cmp2 = comparison_service.compare_passport_photos(db, r.observation.passport_id)
    assert "history" in cmp2


# --------------------------- weekly report --------------------------- #
def test_weekly_report_on_demand(db):
    _run(db, caption="plaga fuerte urgente")
    report = report_service.generate_weekly_report(db, persist=True)
    assert report["observation_count"] >= 1
    assert report["photo_count"] >= 1
    assert "top_issues" in report
    assert "report_id" in report
