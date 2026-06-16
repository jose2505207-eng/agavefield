"""Operations layer: carbon engine, catalog CRUD, history-safe deletes, audit."""
from __future__ import annotations

from app.models.operations import Activity, AuditLog, Product, WorkOrder, WorkOrderItem
from app.services import audit_service, carbon_service, catalog_service


# --------------------------- carbon engine --------------------------- #
def test_carbon_per_ha():
    total, status, snap = carbon_service.compute_carbon(
        activity_factor_value=120.0, activity_factor_unit="kgCO2e_per_ha",
        surface_value=2.0, surface_unit="ha",
    )
    assert total == 240.0 and status == "calculated"


def test_carbon_per_m2_surface_conversion():
    # 1 ha = 10,000 m2; factor per_m2
    total, status, _ = carbon_service.compute_carbon(
        activity_factor_value=0.01, activity_factor_unit="kgCO2e_per_m2",
        surface_value=1.0, surface_unit="ha",
    )
    assert total == 100.0 and status == "calculated"


def test_carbon_per_event_needs_no_data():
    total, status, _ = carbon_service.compute_carbon(
        activity_factor_value=5.0, activity_factor_unit="kgCO2e_per_event",
    )
    assert total == 5.0 and status == "calculated"


def test_carbon_product_per_kg():
    total, status, _ = carbon_service.compute_carbon(
        product_factor_value=2.0, product_factor_unit="kgCO2e_per_kg_product",
        total_product_value=50.0, total_product_unit="kg",
    )
    assert total == 100.0 and status == "calculated"


def test_carbon_activity_plus_product():
    total, status, _ = carbon_service.compute_carbon(
        activity_factor_value=10.0, activity_factor_unit="kgCO2e_per_event",
        product_factor_value=2.0, product_factor_unit="kgCO2e_per_kg_product",
        total_product_value=5.0, total_product_unit="kg",
    )
    assert total == 20.0 and status == "calculated"  # 10 + (2*5)


def test_carbon_missing_data():
    total, status, _ = carbon_service.compute_carbon(
        activity_factor_value=120.0, activity_factor_unit="kgCO2e_per_ha",
        surface_value=None, surface_unit=None,
    )
    assert total is None and status == "missing_data"


def test_carbon_no_factor():
    total, status, _ = carbon_service.compute_carbon()
    assert total is None and status == "no_factor"


# --------------------------- catalog CRUD + audit --------------------------- #
def test_create_product_writes_audit(db):
    p = catalog_service.create_product(db, {"product_name": "Composta A", "product_type": "compost",
                                            "carbon_factor_value": 1.5, "carbon_factor_unit": "kgCO2e_per_kg_product"})
    db.commit()
    assert p.id and p.active is True
    logs = audit_service.history(db, "product", p.id)
    assert len(logs) == 1 and logs[0].action == "create"


def test_unreferenced_product_is_hard_deleted(db):
    p = catalog_service.create_product(db, {"product_name": "Temp"})
    db.commit()
    result = catalog_service.delete_or_deactivate_product(db, p.id)
    db.commit()
    assert result == "deleted"
    assert db.get(Product, p.id) is None


def test_referenced_product_is_deactivated_not_deleted(db):
    p = catalog_service.create_product(db, {"product_name": "Urea"})
    a = catalog_service.create_activity(db, {"activity_name": "Fertilize"})
    db.commit()
    wo = WorkOrder(work_order_code="WO-TST-1", title="t")
    db.add(wo); db.flush()
    db.add(WorkOrderItem(work_order_id=wo.id, activity_id=a.id, product_id=p.id))
    db.commit()
    result = catalog_service.delete_or_deactivate_product(db, p.id)
    db.commit()
    assert result == "deactivated"
    assert db.get(Product, p.id).active is False  # preserved, not deleted


def test_activity_update_audited(db):
    a = catalog_service.create_activity(db, {"activity_name": "Riego", "activity_category": "irrigation"})
    db.commit()
    catalog_service.update_activity(db, a.id, {"recommended_frequency": "weekly"})
    db.commit()
    actions = [l.action for l in audit_service.history(db, "activity", a.id)]
    assert "create" in actions and "update" in actions
