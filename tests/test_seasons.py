"""Season directory: history-safe CRUD with audit logging."""
from __future__ import annotations

from app.models.operations import Season, WorkOrder
from app.services import audit_service, season_service


def test_create_and_list_season_writes_audit_log(db):
    s = season_service.create_season(
        db, {"name": "2026 Spring", "code": "SP26"}, actor="agronomist"
    )
    db.commit()
    assert s.id and s.active is True
    listed = season_service.list_seasons(db)
    assert [x.name for x in listed] == ["2026 Spring"]
    assert [l.action for l in audit_service.history(db, "season", s.id)] == ["create"]


def test_update_season_logs_change(db):
    s = season_service.create_season(db, {"name": "Cycle A"})
    db.commit()
    updated = season_service.update_season(db, s.id, {"name": "Cycle A (revised)"}, actor="admin")
    db.commit()
    assert updated.name == "Cycle A (revised)"
    actions = [l.action for l in audit_service.history(db, "season", s.id)]
    assert "update" in actions


def test_delete_deactivates_when_referenced_by_work_order(db):
    s = season_service.create_season(db, {"name": "Linked"})
    db.commit()
    wo = WorkOrder(work_order_code="WO-SEASON-1", title="t", season_id=s.id)
    db.add(wo)
    db.commit()
    result = season_service.delete_or_deactivate_season(db, s.id, actor="admin")
    db.commit()
    assert result == "deactivated"
    refreshed = db.get(Season, s.id)
    assert refreshed is not None and refreshed.active is False


def test_delete_hard_deletes_when_unreferenced(db):
    s = season_service.create_season(db, {"name": "Orphan"})
    db.commit()
    result = season_service.delete_or_deactivate_season(db, s.id)
    db.commit()
    assert result == "deleted"
    assert db.get(Season, s.id) is None
