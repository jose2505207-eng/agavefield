"""Work-order creation (carbon snapshot) + secure email send."""
from __future__ import annotations

from app.models.operations import WorkOrder
from app.services import audit_service, catalog_service, work_order_service


def _activity(db, **kw):
    data = {"activity_name": "Fertilize", "carbon_factor_value": 100.0,
            "carbon_factor_unit": "kgCO2e_per_ha"}
    data.update(kw)
    a = catalog_service.create_activity(db, data)
    db.flush()
    return a


def _product(db, **kw):
    data = {"product_name": "Urea", "carbon_factor_value": 2.0,
            "carbon_factor_unit": "kgCO2e_per_kg_product"}
    data.update(kw)
    p = catalog_service.create_product(db, data)
    db.flush()
    return p


def test_create_work_order_snapshots_and_computes_carbon(db):
    a = _activity(db)
    p = _product(db)
    wo = work_order_service.create_work_order(
        db,
        {"title": "Fertilize Lot A", "field_id": 1, "lot_id": 1},
        [{"activity_id": a.id, "product_id": p.id,
          "planned_surface_area_value": 2.0, "planned_surface_area_unit": "ha",
          "planned_total_product_value": 50.0, "planned_total_product_unit": "kg"}],
        actor="agronomist",
    )
    db.commit()
    items = work_order_service.get_items(db, wo.id)
    assert len(items) == 1
    # activity 100*2ha = 200; product 2*50kg = 100; total 300
    assert items[0].planned_carbon_kgco2e == 300.0
    assert items[0].carbon_factor_snapshot["carbon_status"] == "calculated"
    assert wo.work_order_code.startswith("WO-")
    assert [l.action for l in audit_service.history(db, "work_order", wo.id)] == ["create"]


def test_work_order_code_is_unique(db):
    a = _activity(db)
    w1 = work_order_service.create_work_order(db, {"title": "A"}, [{"activity_id": a.id}])
    w2 = work_order_service.create_work_order(db, {"title": "B"}, [{"activity_id": a.id}])
    db.commit()
    assert w1.work_order_code != w2.work_order_code


def test_carbon_snapshot_immutable_when_catalog_changes(db):
    a = _activity(db)
    wo = work_order_service.create_work_order(
        db, {"title": "X"},
        [{"activity_id": a.id, "planned_surface_area_value": 1.0, "planned_surface_area_unit": "ha"}],
    )
    db.commit()
    original = work_order_service.get_items(db, wo.id)[0].planned_carbon_kgco2e
    assert original == 100.0
    # Change the catalog factor afterwards.
    catalog_service.update_activity(db, a.id, {"carbon_factor_value": 999.0})
    db.commit()
    # Existing work-order item carbon is unchanged (locked snapshot).
    assert work_order_service.get_items(db, wo.id)[0].planned_carbon_kgco2e == 100.0


def test_send_work_order_hashes_token_and_marks_sent(db):
    a = _activity(db)
    wo = work_order_service.create_work_order(
        db, {"title": "Send me", "assigned_to_email": "worker@example.com"},
        [{"activity_id": a.id}],
    )
    db.commit()
    result = work_order_service.send_work_order(db, wo.id, actor="agronomist")
    db.commit()
    assert result["delivered"] is True and result["recipient"] == "worker@example.com"
    refreshed = db.get(WorkOrder, wo.id)
    assert refreshed.status == "sent" and refreshed.sent_at is not None
    # Only the hash is stored, never the raw token.
    assert refreshed.secure_access_token_hash and refreshed.secure_access_token_hash != result["token"]
    # The raw token resolves back to the work order (used by the mobile page later).
    assert work_order_service.find_by_token(db, result["token"]).id == wo.id
    assert work_order_service.find_by_token(db, "wrong-token") is None
    assert "send_email" in [l.action for l in audit_service.history(db, "work_order", wo.id)]


def test_send_without_recipient_returns_error(db):
    a = _activity(db)
    wo = work_order_service.create_work_order(db, {"title": "No email"}, [{"activity_id": a.id}])
    db.commit()
    assert work_order_service.send_work_order(db, wo.id) == {"error": "no_recipient"}


def test_generate_link_mints_shareable_token_without_email(db):
    a = _activity(db)
    # No assignee email needed — the link is for manual sharing (WhatsApp/QR).
    wo = work_order_service.create_work_order(db, {"title": "Share me"}, [{"activity_id": a.id}])
    db.commit()
    result = work_order_service.generate_link(db, wo.id, actor="agronomist")
    db.commit()
    assert "/work-orders/complete/" in result["link"]
    assert result["link"].endswith(result["token"])
    refreshed = db.get(WorkOrder, wo.id)
    # Only the hash is persisted; status advances out of draft.
    assert refreshed.status == "sent" and refreshed.secure_access_token_hash
    assert refreshed.secure_access_token_hash != result["token"]
    # The token resolves to the work order (used by the mobile completion page).
    assert work_order_service.find_by_token(db, result["token"]).id == wo.id
    assert "generate_link" in [l.action for l in audit_service.history(db, "work_order", wo.id)]


def test_generate_link_rotates_token(db):
    a = _activity(db)
    wo = work_order_service.create_work_order(db, {"title": "Rotate"}, [{"activity_id": a.id}])
    db.commit()
    first = work_order_service.generate_link(db, wo.id)
    db.commit()
    second = work_order_service.generate_link(db, wo.id)
    db.commit()
    # Re-generating rotates the token: the old link stops working.
    assert work_order_service.find_by_token(db, first["token"]) is None
    assert work_order_service.find_by_token(db, second["token"]).id == wo.id
