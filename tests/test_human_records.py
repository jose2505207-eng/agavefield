"""Human-centered field records (MVP): no AI on upload, manual notes, review."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.database import Task
from app.models.schemas import EventType, FieldNoteReview
from app.services import observation_service, weather_service


@pytest.fixture(autouse=True)
def _no_weather(monkeypatch):
    monkeypatch.setattr(weather_service, "fetch_weather", lambda lat, lon, ts=None: None)


def test_create_evidence_record_invokes_no_ai(db):
    user = observation_service.get_or_create_user(db, telegram_user_id="e1")
    obs = observation_service.create_evidence_record(
        db,
        manual_note="Aplicación de composta en hilera 4",
        event_type="compost",
        responsible_person="Juan",
        image_url="http://x/a.jpg",
        user_id=user.id,
        source_channel="telegram",
    )
    db.commit()
    assert obs.manual_note.startswith("Aplicación")
    assert obs.event_type == "compost"
    assert obs.responsible_person == "Juan"
    assert obs.review_status == "pending_review"
    assert obs.passport_id is not None  # linked to the timeline
    # NO AI fields populated:
    assert obs.diagnosis is None
    assert obs.confidence == 0.0
    assert obs.severity == "unknown"
    assert obs.needs_human_review is False
    assert (obs.visible_symptoms_json in (None, []))


def test_follow_up_creates_task(db):
    user = observation_service.get_or_create_user(db, telegram_user_id="e2")
    due = datetime.utcnow() + timedelta(days=7)
    obs = observation_service.create_evidence_record(
        db, manual_note="Plaga observada", event_type="pest_treatment",
        follow_up_needed=True, follow_up_date=due, user_id=user.id,
    )
    db.commit()
    tasks = db.query(Task).filter_by(observation_id=obs.id).all()
    assert len(tasks) == 1 and tasks[0].source == "follow_up"


def test_review_queue_and_approve(db):
    user = observation_service.get_or_create_user(db, telegram_user_id="e3")
    obs = observation_service.create_evidence_record(
        db, manual_note="riego por goteo", event_type="irrigation", user_id=user.id
    )
    db.commit()
    assert any(o.id == obs.id for o in observation_service.records_pending_review(db))

    observation_service.review_record(
        db, obs.id,
        FieldNoteReview(event_type=EventType.fertilization, process_type="urea",
                        agronomist_notes="Reclasificado", approved=True, reviewed_by="agro"),
    )
    db.commit()
    refreshed = observation_service.get_observation(db, obs.id)
    assert refreshed.review_status == "approved"
    assert refreshed.event_type == "fertilization"
    assert refreshed.process_type == "urea"
    assert refreshed.human_verified is True
    assert not any(o.id == obs.id for o in observation_service.records_pending_review(db))


def test_review_request_followup(db):
    user = observation_service.get_or_create_user(db, telegram_user_id="e4")
    obs = observation_service.create_evidence_record(
        db, manual_note="hoja seca", event_type="observation", user_id=user.id
    )
    db.commit()
    observation_service.review_record(
        db, obs.id,
        FieldNoteReview(request_followup=True,
                        follow_up_date=datetime.utcnow() + timedelta(days=3), reviewed_by="agro"),
    )
    db.commit()
    refreshed = observation_service.get_observation(db, obs.id)
    assert refreshed.review_status == "needs_followup"
    assert refreshed.follow_up_needed is True
    assert db.query(Task).filter_by(observation_id=obs.id, source="follow_up").count() == 1


def test_manual_note_attach_to_latest(db):
    user = observation_service.get_or_create_user(db, telegram_user_id="e5")
    obs = observation_service.create_evidence_record(
        db, manual_note=None, event_type="observation", user_id=user.id, image_url="http://x/n.jpg"
    )
    db.commit()
    pending = observation_service.latest_note_pending_record(db, user.id)
    assert pending.id == obs.id
    pending.manual_note = "nota agregada por el técnico"
    db.flush()
    assert observation_service.latest_note_pending_record(db, user.id) is None


def test_ai_flag_off_by_default():
    from app.config import settings
    assert settings.enable_ai_image_analysis is False
