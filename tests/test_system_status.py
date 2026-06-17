"""Increment ⑦: system readiness/status endpoint."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client():
    from app.main import app
    return TestClient(app)


def test_status_reports_readiness(db):
    c = _client()
    s = c.get("/api/system/status").json()
    assert s["database"]["connected"] is True
    assert s["rbac_enforced"] is False           # no API keys in tests → open
    assert s["ai_image_analysis_enabled"] is False
    assert "products" in s["counts"] and "pending_review" in s["counts"]
    # Empty catalogs → not go-live ready
    assert s["go_live_ready"] is False


def test_status_go_live_ready_after_catalogs(db):
    c = _client()
    c.post("/api/products", json={"product_name": "Compost"})
    c.post("/api/activities", json={"activity_name": "Compost application"})
    s = c.get("/api/system/status").json()
    assert s["counts"]["products"] >= 1 and s["counts"]["activities"] >= 1
    # local storage + console email are "configured" in dev → ready once catalogs exist
    assert s["go_live_ready"] is True
