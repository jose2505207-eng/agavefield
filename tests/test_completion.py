"""Increment ③: mobile completion — page render, photo upload, submission,
actual carbon from locked snapshot, weather link, needs_correction handling."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.models.operations import ExecutionRecord, PhotoEvidence, WorkOrder
from app.services import image_service, weather_service


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    # Stub storage (no real S3) and weather (no real HTTP) for offline tests.
    monkeypatch.setattr(
        image_service, "store_image_bytes",
        lambda data, ext="jpg": image_service.StoredImage(
            image_url="http://stub/p.jpg", thumbnail_url="http://stub/t.jpg"),
    )
    monkeypatch.setattr(
        weather_service, "get_current_weather",
        lambda lat, lon: {"temperature_c": 30.0, "humidity_percent": 40.0,
                          "precipitation_mm": 0.0, "wind_speed_kmh": 10.0,
                          "recent_rain_mm": 2.0, "source": "test"},
    )
    monkeypatch.setattr(
        weather_service, "get_forecast",
        lambda lat, lon, days=1: [{"date": "2026-06-17", "temp_max_c": 33.0,
                                   "temp_min_c": 18.0, "precip_prob": 20, "precip_mm": 1.0}],
    )


def _client():
    from app.main import app
    return TestClient(app)


def _make_sent_work_order(c):
    a = c.post("/api/activities", json={"activity_name": "Fertilization",
               "carbon_factor_value": 100.0, "carbon_factor_unit": "kgCO2e_per_ha"}).json()
    wo = c.post("/api/work-orders", json={
        "title": "Lot 1 fertilize", "lot_id": 1, "assigned_to_email": "w@x.com",
        "items": [{"activity_id": a["id"], "planned_surface_area_value": 2.0,
                   "planned_surface_area_unit": "ha", "required_photo_count": 1}],
    }).json()
    send = c.post(f"/api/work-orders/{wo['id']}/send").json()
    token = send["dev_link"].rsplit("/", 1)[-1]
    return wo, token


def test_completion_page_renders(db):
    c = _client()
    wo, token = _make_sent_work_order(c)
    r = c.get(f"/work-orders/complete/{token}")
    assert r.status_code == 200
    assert "Fertilization" in r.text and wo["work_order_code"] in r.text
    # invalid token → 404 page, not a crash
    assert c.get("/work-orders/complete/not-a-real-token").status_code == 404


def test_full_submission_creates_execution_with_carbon_and_weather(db):
    c = _client()
    wo, token = _make_sent_work_order(c)
    item_id = wo["items"][0]["id"]

    up = c.post("/api/photos/upload",
                data={"token": token, "work_order_item_id": str(item_id),
                      "gps_latitude": "20.88", "gps_longitude": "-103.83"},
                files={"file": ("p.jpg", b"fakebytes", "image/jpeg")})
    assert up.status_code == 201
    photo_id = up.json()["id"]

    res = c.post(f"/api/work-orders/complete/{token}/submit", json={
        "submitted_by_name": "Juan", "gps_latitude": 20.88, "gps_longitude": -103.83,
        "items": [{"work_order_item_id": item_id, "actual_surface_area_value": 3.0,
                   "actual_surface_area_unit": "ha", "manual_note": "Done",
                   "evidence_photo_ids": [photo_id]}],
    })
    assert res.status_code == 200
    body = res.json()
    ex = body["executions"][0]
    assert ex["actual_carbon_kgco2e"] == 300.0  # locked 100/ha * actual 3ha
    assert ex["carbon_status"] == "calculated"
    assert ex["compliance_status"] == "pending_review"  # photo + note + gps all present
    assert body["weather_status"] == "captured"

    # Verify persistence in a fresh session.
    s = SessionLocal()
    try:
        er = s.get(ExecutionRecord, ex["execution_record_id"])
        assert er.actual_carbon_kgco2e == 300.0 and er.weather_snapshot_id is not None
        photo = s.get(PhotoEvidence, photo_id)
        assert photo.execution_record_id == er.id  # evidence linked
        assert s.get(WorkOrder, wo["id"]).status == "submitted"
    finally:
        s.close()


def test_missing_evidence_marks_needs_correction(db):
    c = _client()
    wo, token = _make_sent_work_order(c)
    item_id = wo["items"][0]["id"]
    # No photo, no note, no GPS → required → needs_correction, but still saved.
    res = c.post(f"/api/work-orders/complete/{token}/submit", json={
        "items": [{"work_order_item_id": item_id, "actual_surface_area_value": 1.0,
                   "actual_surface_area_unit": "ha"}],
    })
    assert res.status_code == 200
    ex = res.json()["executions"][0]
    assert ex["compliance_status"] == "needs_correction"
    assert set(ex["warnings"]) >= {"missing_gps", "missing_manual_note", "missing_photos"}
    assert ex["execution_record_id"]  # field work preserved, not discarded
