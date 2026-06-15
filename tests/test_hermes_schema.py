"""Hermes output contract + stub vision client validation."""
from __future__ import annotations

from app.integrations.vision_client import StubVisionClient
from app.models.schemas import HermesOutput, Severity


def test_hermes_output_defaults_safe():
    out = HermesOutput()
    assert out.needs_human_review is True
    assert out.severity == Severity.unknown
    assert out.confidence == 0.0
    assert out.escalation_recommended is False


def test_confidence_is_clamped():
    assert HermesOutput(confidence=5).confidence == 1.0
    assert HermesOutput(confidence=-2).confidence == 0.0
    assert HermesOutput(confidence="not a number").confidence == 0.0


def test_symptoms_string_coerced_to_list():
    out = HermesOutput(visible_symptoms="single symptom")
    assert out.visible_symptoms == ["single symptom"]


def test_unknown_enum_value_rejected():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        HermesOutput(severity="apocalyptic")


def test_stub_client_returns_valid_schema():
    client = StubVisionClient()
    raw = client.analyze("http://x/img.jpg", caption="hojas amarillas", latitude=None, longitude=None)
    out = HermesOutput.model_validate(raw)  # must not raise
    assert out.needs_human_review is True
    assert out.plant_condition.value == "yellowing"
    # Stub must never claim certainty.
    assert out.confidence < 0.6


def test_stub_flags_missing_location_and_caption():
    client = StubVisionClient()
    raw = client.analyze("http://x/img.jpg", caption=None, latitude=None, longitude=None)
    out = HermesOutput.model_validate(raw)
    assert "location" in out.missing_fields
    assert "caption" in out.missing_fields
