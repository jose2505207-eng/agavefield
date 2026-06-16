"""Increment ⑤: carbon reporting from stored snapshots (planned vs actual,
breakdowns, per-hectare, missing-data)."""
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


def _submit(c, *, activity_factor=100.0, product_factor=2.0, lot_id=1,
            actual_surface=3.0, actual_product=50.0):
    a = c.post("/api/activities", json={"activity_name": "Fertilization",
               "carbon_factor_value": activity_factor,
               "carbon_factor_unit": "kgCO2e_per_ha"} if activity_factor else
               {"activity_name": "Monitoring"}).json()
    item = {"activity_id": a["id"], "required_photo_count": 0,
            "planned_surface_area_value": 2.0, "planned_surface_area_unit": "ha"}
    if product_factor:
        p = c.post("/api/products", json={"product_name": "Urea",
                   "carbon_factor_value": product_factor,
                   "carbon_factor_unit": "kgCO2e_per_kg_product"}).json()
        item["product_id"] = p["id"]
        item["planned_total_product_value"] = 40.0
        item["planned_total_product_unit"] = "kg"
    wo = c.post("/api/work-orders", json={"title": "WO", "lot_id": lot_id,
                "assigned_to_email": "w@x.com", "items": [item]}).json()
    token = c.post(f"/api/work-orders/{wo['id']}/send").json()["dev_link"].rsplit("/", 1)[-1]
    body = {"gps_latitude": 20.88, "gps_longitude": -103.83, "items": [{
        "work_order_item_id": wo["items"][0]["id"], "manual_note": "done",
        "actual_surface_area_value": actual_surface, "actual_surface_area_unit": "ha"}]}
    if product_factor:
        body["items"][0]["actual_total_product_value"] = actual_product
        body["items"][0]["actual_total_product_unit"] = "kg"
    c.post(f"/api/work-orders/complete/{token}/submit", json=body)
    return wo


def test_carbon_summary_planned_vs_actual(db):
    c = _client()
    _submit(c)  # planned: 100*2 + 2*40 = 280 ; actual: 100*3 + 2*50 = 400
    s = c.get("/api/carbon/summary").json()
    assert s["total_planned_kgco2e"] == 280.0
    assert s["total_actual_kgco2e"] == 400.0
    assert s["planned_vs_actual_kgco2e"] == 120.0
    assert s["kgco2e_per_hectare"] == round(400.0 / 3.0, 4)  # actual 400 over 3 ha
    assert s["records_missing_carbon_data"] == 0


def test_carbon_breakdowns(db):
    c = _client()
    _submit(c, lot_id=1)
    assert c.get("/api/carbon/by-activity").json()[0]["kgco2e"] == 400.0
    assert c.get("/api/carbon/by-product").json()[0]["kgco2e"] == 400.0
    lot = c.get("/api/carbon/by-lot").json()
    assert lot[0]["lot_id"] == 1 and lot[0]["kgco2e"] == 400.0


def test_missing_carbon_data_flagged(db):
    c = _client()
    _submit(c, activity_factor=None, product_factor=None)  # no factors at all
    s = c.get("/api/carbon/summary").json()
    assert s["records_missing_carbon_data"] >= 1
    assert len(c.get("/api/carbon/missing-data").json()) >= 1
