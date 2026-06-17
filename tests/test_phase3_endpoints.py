"""Phase 3 backend support: executions list + JSON completion-by-token."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services import weather_service


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(weather_service, "get_current_weather",
                        lambda lat, lon: {"temperature_c": 28.0, "source": "test"})
    monkeypatch.setattr(weather_service, "get_forecast", lambda lat, lon, days=1: [])


def _client():
    from app.main import app
    return TestClient(app)


def _submit(c):
    a = c.post("/api/activities", json={"activity_name": "Fertilization",
               "carbon_factor_value": 100.0, "carbon_factor_unit": "kgCO2e_per_ha"}).json()
    wo = c.post("/api/work-orders", json={"title": "WO", "lot_id": 1, "assigned_to_email": "w@x.com",
                "items": [{"activity_id": a["id"], "required_photo_count": 0}]}).json()
    token = c.post(f"/api/work-orders/{wo['id']}/send").json()["dev_link"].rsplit("/", 1)[-1]
    er = c.post(f"/api/work-orders/complete/{token}/submit", json={
        "gps_latitude": 20.88, "gps_longitude": -103.83,
        "items": [{"work_order_item_id": wo["items"][0]["id"], "manual_note": "done",
                   "actual_surface_area_value": 2.0, "actual_surface_area_unit": "ha"}]}).json()
    return wo, token, er["executions"][0]["execution_record_id"]


def test_list_executions(db):
    c = _client()
    wo, token, er_id = _submit(c)
    rows = c.get("/api/executions").json()
    assert any(r["id"] == er_id for r in rows)
    # filter by work order
    filtered = c.get(f"/api/executions?work_order_id={wo['id']}").json()
    assert filtered and all(r["work_order_id"] == wo["id"] for r in filtered)


def test_completion_data_by_token(db):
    c = _client()
    wo, token, _ = _submit(c)
    data = c.get(f"/api/work-orders/complete/{token}/data").json()
    assert data["work_order"]["code"] == wo["work_order_code"]
    assert len(data["items"]) == 1 and "activity_name" in data["items"][0]
    # bad token → 404
    assert c.get("/api/work-orders/complete/bad/data").status_code == 404
