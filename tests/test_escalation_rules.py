"""Escalation rule evaluation, urgent-term detection, and cooldown."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models.database import Escalation, FieldObservation, Lot
from app.models.schemas import HermesOutput
from app.services import escalation_service as es


def _obs(db, **kw):
    defaults = dict(severity="low", confidence=0.5, suspected_issue=None, observed_at=datetime.utcnow())
    defaults.update(kw)
    o = FieldObservation(**defaults)
    db.add(o)
    db.flush()
    return o


def test_caption_urgent_terms():
    assert es.caption_has_urgent_terms("esto es URGENTE")
    assert es.caption_has_urgent_terms("la plaga se está extendiendo")
    assert not es.caption_has_urgent_terms("planta sana")
    assert not es.caption_has_urgent_terms(None)


def test_high_severity_triggers(db):
    o = _obs(db, severity="high")
    should, reason = es.evaluate_rules(db, o, HermesOutput(severity="high"))
    assert should is True
    assert "high" in reason


def test_ai_recommended_needs_high_confidence(db):
    o = _obs(db, severity="medium")
    low = HermesOutput(escalation_recommended=True, confidence=0.5)
    high = HermesOutput(escalation_recommended=True, confidence=0.8, escalation_reason="fast spread")
    assert es.evaluate_rules(db, o, low)[0] is False
    assert es.evaluate_rules(db, o, high)[0] is True


def test_force_always_escalates(db):
    o = _obs(db, severity="low")
    should, reason = es.evaluate_rules(db, o, HermesOutput(severity="low"), force=True)
    assert should is True


def test_repeated_medium_in_lot(db):
    lot = Lot(lot_code="A1")
    db.add(lot)
    db.flush()
    for _ in range(3):
        _obs(db, severity="medium", lot_id=lot.id)
    target = _obs(db, severity="low", lot_id=lot.id)
    should, reason = es.evaluate_rules(db, target, HermesOutput(severity="low"))
    assert should is True
    assert "medium" in reason


def test_cooldown_suppresses_duplicate(db):
    lot = Lot(lot_code="B2")
    db.add(lot)
    db.flush()
    o1 = _obs(db, severity="high", lot_id=lot.id, suspected_issue="rot suspected")
    # First escalation goes through (no recipients -> failed delivery, but if we
    # mark a prior 'sent' escalation, cooldown should suppress the next).
    db.add(
        Escalation(
            observation_id=o1.id,
            channel="whatsapp",
            recipient="123",
            status="sent",
            created_at=datetime.utcnow(),
        )
    )
    db.flush()
    o2 = _obs(db, severity="high", lot_id=lot.id, suspected_issue="rot suspected")
    esc = es.maybe_escalate(db, o2, HermesOutput(severity="high"))
    assert esc is None
    assert o2.escalation_status == "suppressed_cooldown"
