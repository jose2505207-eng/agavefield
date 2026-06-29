"""Increment ④: review queue, immutable approve/reject, correction → revision
chain, and timeline reads."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.models.operations import ExecutionRecord
from app.services import weather_service


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(weather_service, "get_current_weather",
                        lambda lat, lon: {"temperature_c": 28.0, "source": "test"})
    monkeypatch.setattr(weather_service, "get_forecast", lambda lat, lon, days=1: [])


def _client():
    from app.main import app
    return TestClient(app)


def _submit_one(c, *, with_note=True, with_gps=True):
    a = c.post("/api/activities", json={"activity_name": "Fertilization",
               "carbon_factor_value": 100.0, "carbon_factor_unit": "kgCO2e_per_ha"}).json()
    wo = c.post("/api/work-orders", json={
        "title": "Lot 1", "lot_id": 1, "assigned_to_email": "w@x.com",
        "items": [{"activity_id": a["id"], "required_photo_count": 0}],
    }).json()
    token = c.post(f"/api/work-orders/{wo['id']}/send").json()["dev_link"].rsplit("/", 1)[-1]
    item_id = wo["items"][0]["id"]
    body = {"items": [{"work_order_item_id": item_id,
                       "actual_surface_area_value": 2.0, "actual_surface_area_unit": "ha",
                       "manual_note": "Done" if with_note else None}]}
    if with_gps:
        body["gps_latitude"] = 20.88
        body["gps_longitude"] = -103.83
    res = c.post(f"/api/work-orders/complete/{token}/submit", json=body).json()
    return wo, token, item_id, res["executions"][0]["execution_record_id"]


def test_review_queue_and_approve_is_immutable(db):
    c = _client()
    wo, token, item_id, er_id = _submit_one(c)
    queue = c.get("/api/review-queue").json()
    assert any(e["id"] == er_id for e in queue)

    r = c.post(f"/api/review/{er_id}/approve",
               json={"reviewer_name": "Ana", "reviewer_notes": "ok"}).json()
    assert r["compliance_status"] == "compliant"
    # No longer in the queue
    assert not any(e["id"] == er_id for e in c.get("/api/review-queue").json())
    # Submitted data preserved (not overwritten by review)
    s = SessionLocal()
    try:
        er = s.get(ExecutionRecord, er_id)
        assert er.manual_note == "Done" and er.actual_surface_area_value == 2.0
        assert er.compliance_status == "compliant"
    finally:
        s.close()
    # audit shows submit + approve
    actions = [x["action"] for x in c.get(f"/api/audit/execution_record/{er_id}").json()]
    assert "submit" in actions and "approve" in actions


def test_request_correction_then_resubmit_creates_revision(db):
    c = _client()
    wo, token, item_id, er1 = _submit_one(c)
    c.post(f"/api/review/{er1}/request-correction", json={"reviewer_notes": "more detail"})
    # Worker re-submits the corrected work for the same item
    res2 = c.post(f"/api/work-orders/complete/{token}/submit", json={
        "gps_latitude": 20.88, "gps_longitude": -103.83,
        "items": [{"work_order_item_id": item_id, "actual_surface_area_value": 2.5,
                   "actual_surface_area_unit": "ha", "manual_note": "Corrected"}],
    }).json()
    er2 = res2["executions"][0]["execution_record_id"]
    assert er2 != er1
    # Revision chain links er2 -> er1 (original preserved)
    chain = c.get(f"/api/review/{er2}/revisions").json()
    assert [e["id"] for e in chain] == [er1, er2]
    s = SessionLocal()
    try:
        assert s.get(ExecutionRecord, er2).is_revision_of_id == er1
        assert s.get(ExecutionRecord, er1).manual_note == "Done"  # original intact
    finally:
        s.close()


def test_request_correction_notify_emails_fresh_link(db):
    c = _client()
    wo, token, item_id, er1 = _submit_one(c)
    r = c.post(f"/api/review/{er1}/request-correction?notify=true",
               json={"reviewer_notes": "add a photo"}).json()
    note = r["notification"]
    assert note["delivered"] is True and note["recipient"] == "w@x.com"
    # Raw token/link are never leaked in the response (console mode → dev_link only).
    assert "token" not in note and "link" not in note and note["dev_link"]
    # The original link was rotated: the old token no longer resolves...
    assert c.get(f"/work-orders/complete/{token}").status_code == 404
    # ...and the fresh link opens the mobile completion page.
    new_token = note["dev_link"].rsplit("/", 1)[-1]
    assert c.get(f"/work-orders/complete/{new_token}").status_code == 200
    # Audit trail records the correction notification.
    actions = [x["action"] for x in c.get(f"/api/audit/work_order/{wo['id']}").json()]
    assert "notify_correction" in actions


def test_request_correction_without_notify_keeps_original_token(db):
    c = _client()
    wo, token, item_id, er1 = _submit_one(c)
    r = c.post(f"/api/review/{er1}/request-correction",
               json={"reviewer_notes": "more detail"}).json()
    # Default path does NOT notify or rotate — original token still works.
    assert r.get("notification") is None
    assert c.get(f"/work-orders/complete/{token}").status_code == 200


def test_timeline_records_lifecycle(db):
    c = _client()
    wo, token, item_id, er_id = _submit_one(c)
    c.post(f"/api/review/{er_id}/approve", json={"reviewer_name": "Ana"})
    events = [e["event_type"] for e in c.get("/api/lots/1/timeline").json()]
    assert "work_order_created" in events
    assert "work_order_sent" in events
    assert "activity_submitted" in events
    assert "activity_approved" in events
    # global feed works too
    assert len(c.get("/api/timeline").json()) >= 4
