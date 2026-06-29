"""CSV catalog import: service-level coercion + upload endpoint."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.services import catalog_service


def _client():
    from app.main import app
    return TestClient(app)


PRODUCTS_CSV = (
    "product_name,product_type,carbon_factor_value,carbon_factor_unit,allowed\n"
    "Urea,fertilizer,2.0,kgCO2e_per_kg_product,true\n"
    "Compost,fertilizer,,kgCO2e_per_kg_product,true\n"  # blank factor → still imported
    ",,,,\n"  # all-blank row → skipped
)

ACTIVITIES_CSV = (
    "activity_name,carbon_factor_value,carbon_factor_unit,requires_photo_evidence\n"
    "Fertilization,100.0,kgCO2e_per_ha,yes\n"
)


def test_import_products_service(db):
    summary = catalog_service.import_csv(db, "products", PRODUCTS_CSV)
    db.commit()
    assert summary["imported"] == 2
    assert summary["skipped"] == 1
    assert summary["errors"] == []
    names = {p.product_name for p in catalog_service.list_products(db)}
    assert {"Urea", "Compost"} <= names


def test_import_rejects_unknown_kind(db):
    try:
        catalog_service.import_csv(db, "widgets", PRODUCTS_CSV)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_import_endpoint_activities(db):
    c = _client()
    files = {"file": ("activities.csv", io.BytesIO(ACTIVITIES_CSV.encode()), "text/csv")}
    r = c.post("/api/catalog/import?kind=activities", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    acts = c.get("/api/activities").json()
    assert any(a["activity_name"] == "Fertilization" for a in acts)


def test_import_endpoint_rejects_empty(db):
    c = _client()
    files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    r = c.post("/api/catalog/import?kind=products", files=files)
    assert r.status_code == 400
