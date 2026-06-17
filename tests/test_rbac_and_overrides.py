"""Increment ⑥: API-key RBAC, manual carbon override, duplicate work order."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.models.operations import ExecutionRecord, WorkOrder
from app.services import audit_service, weather_service


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(weather_service, "get_current_weather",
                        lambda lat, lon: {"temperature_c": 28.0, "source": "test"})
    monkeypatch.setattr(weather_service, "get_forecast", lambda lat, lon, days=1: [])


def _client():
    from app.main import app
    return TestClient(app)


def _make_execution(c):
    a = c.post("/api/activities", json={"activity_name": "Fertilization",
               "carbon_factor_value": 100.0, "carbon_factor_unit": "kgCO2e_per_ha"}).json()
    wo = c.post("/api/work-orders", json={"title": "WO", "lot_id": 1, "assigned_to_email": "w@x.com",
                "items": [{"activity_id": a["id"], "required_photo_count": 0,
                           "planned_surface_area_value": 2.0, "planned_surface_area_unit": "ha"}]}).json()
    token = c.post(f"/api/work-orders/{wo['id']}/send").json()["dev_link"].rsplit("/", 1)[-1]
    res = c.post(f"/api/work-orders/complete/{token}/submit", json={
        "gps_latitude": 20.88, "gps_longitude": -103.83,
        "items": [{"work_order_item_id": wo["items"][0]["id"], "manual_note": "done",
                   "actual_surface_area_value": 2.0, "actual_surface_area_unit": "ha"}]}).json()
    return wo, res["executions"][0]["execution_record_id"]


def test_open_mode_allows_when_no_keys(db):
    # No API keys configured (default) → endpoints are open.
    assert _client().get("/api/work-orders").status_code == 200


def test_rbac_enforced_when_keys_set(db, monkeypatch):
    monkeypatch.setattr(settings, "admin_api_key", "k-admin")
    monkeypatch.setattr(settings, "reviewer_api_key", "k-rev")
    c = _client()
    # staff endpoint
    assert c.get("/api/work-orders").status_code == 401              # no key
    assert c.get("/api/work-orders", headers={"X-API-Key": "nope"}).status_code == 401
    assert c.get("/api/work-orders", headers={"X-API-Key": "k-admin"}).status_code == 200
    assert c.get("/api/work-orders", headers={"X-API-Key": "k-rev"}).status_code == 403   # reviewer ≠ staff
    # review endpoint allows reviewer
    assert c.get("/api/review-queue", headers={"X-API-Key": "k-rev"}).status_code == 200
    # public worker endpoints stay open even with keys set
    assert c.get("/work-orders/complete/bad-token").status_code == 404  # not 401


def test_carbon_override(db):
    c = _client()
    wo, er_id = _make_execution(c)
    r = c.post(f"/api/executions/{er_id}/carbon-override",
               json={"value": 42.0, "reason": "field correction", "user": "ana"})
    assert r.status_code == 200 and r.json()["override_value"] == 42.0
    s = SessionLocal()
    try:
        er = s.get(ExecutionRecord, er_id)
        assert er.carbon_override_value == 42.0 and er.carbon_override_reason == "field correction"
        assert er.actual_carbon_kgco2e == 200.0  # original calc preserved
        assert "override_carbon" in [l.action for l in audit_service.history(s, "execution_record", er_id)]
    finally:
        s.close()
    # summary now uses the override (42) not the calculated 200
    assert c.get("/api/carbon/summary").json()["total_actual_kgco2e"] == 42.0


def test_duplicate_work_order(db):
    c = _client()
    a = c.post("/api/activities", json={"activity_name": "Irrigation",
               "carbon_factor_value": 10.0, "carbon_factor_unit": "kgCO2e_per_event"}).json()
    wo = c.post("/api/work-orders", json={"title": "Original", "lot_id": 2,
                "items": [{"activity_id": a["id"], "required_photo_count": 2}]}).json()
    dup = c.post(f"/api/work-orders/{wo['id']}/duplicate").json()
    assert dup["work_order_code"] != wo["work_order_code"]
    assert dup["title"].endswith("(copy)") and dup["status"] == "draft"
    assert len(dup["items"]) == 1 and dup["items"][0]["planned_carbon_kgco2e"] == 10.0
