"""Organization RBAC: permission resolution, data-scope visibility, member/
invite endpoints, and authoritative server-side enforcement (worker denial,
auditor read-only, invitation lifecycle)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models.operations import AppUser, Organization, WorkOrder
from app.services import auth_service, rbac_service


@pytest.fixture(autouse=True)
def _clear_login_throttle():
    auth_service._login_failures.clear()
    yield
    auth_service._login_failures.clear()


def _client():
    from app.main import app
    return TestClient(app)


def _org(db, slug="acme-agave") -> Organization:
    org = rbac_service.get_or_create_organization(db, name="Acme Agave", slug=slug)
    db.commit()
    return org


def _user(db, username, organization_id=None, is_demo=False) -> AppUser:
    u = AppUser(
        username=username,
        password_hash=auth_service.hash_password(username),
        full_name=username.title(),
        role="agronomist",
        is_demo=is_demo,
        organization_id=organization_id,
    )
    db.add(u)
    db.commit()
    return u


def _member(db, org, user, role, **scope):
    m = rbac_service.create_member(
        db, organization_id=org.id, app_user_id=user.id, role=role, **scope
    )
    db.commit()
    return m


def _token(db, user) -> str:
    token, _ = auth_service.create_session(db, user)
    db.commit()
    return token


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Permission resolution (role template + per-member override)
# --------------------------------------------------------------------------- #
def test_role_templates_have_expected_defaults():
    eng = rbac_service.resolve_permissions("engineer")
    assert eng["can_review_work_orders"] is True
    assert eng["can_view_labor_analytics"] is True
    assert eng["can_invite_members"] is False
    assert eng["can_manage_org_settings"] is False

    aud = rbac_service.resolve_permissions("auditor")
    assert aud["can_export_data"] is True
    assert aud["can_view_reports"] is True
    # auditor holds no write-capable permission
    assert all(aud[p] is False for p in rbac_service.WRITE_PERMISSIONS)

    admin = rbac_service.resolve_permissions("admin")
    assert all(admin[p] is True for p in rbac_service.PERMISSION_FIELDS)


def test_override_diverges_from_template():
    # An engineer granted invite rights but who keeps everything else.
    eff = rbac_service.resolve_permissions("engineer", {"can_invite_members": True})
    assert eff["can_invite_members"] is True
    assert eff["can_review_work_orders"] is True
    assert eff["can_manage_org_settings"] is False
    # A worker granted report viewing only.
    w = rbac_service.resolve_permissions("worker", {"can_view_reports": True})
    assert w["can_view_reports"] is True
    assert w["can_create_work_orders"] is False


def test_update_member_applies_override_and_audits(db):
    org = _org(db)
    u = _user(db, "eng1", organization_id=org.id)
    m = _member(db, org, u, "engineer")
    assert m.can_manage_org_settings is False
    rbac_service.update_member(
        db, m.id, permission_overrides={"can_manage_org_settings": True}, actor="boss"
    )
    db.commit()
    db.refresh(m)
    assert m.can_manage_org_settings is True
    # engineer template perms are preserved alongside the override
    assert m.can_review_work_orders is True
    actions = [a.action for a in __import__("app.services.audit_service",
               fromlist=["history"]).history(db, "organization_member", m.id)]
    assert "permissions_changed" in actions


# --------------------------------------------------------------------------- #
# Data-scope visibility (service-layer filter)
# --------------------------------------------------------------------------- #
def test_worker_cannot_see_other_workers_work_orders(db):
    org = _org(db)
    u = _user(db, "juan", organization_id=org.id)
    member = _member(db, org, u, "worker", scope_assignee_emails=["juan@x.com"])

    mine = WorkOrder(work_order_code="WO-1", title="Mine", status="sent",
                     organization_id=org.id, assigned_to_email="juan@x.com")
    theirs = WorkOrder(work_order_code="WO-2", title="Theirs", status="sent",
                       organization_id=org.id, assigned_to_email="ana@x.com")
    db.add_all([mine, theirs])
    db.commit()

    visible = rbac_service.filter_work_orders_by_scope(member, [mine, theirs])
    codes = {w.work_order_code for w in visible}
    assert codes == {"WO-1"}


def test_engineer_sees_whole_org(db):
    org = _org(db)
    u = _user(db, "camila", organization_id=org.id)
    member = _member(db, org, u, "engineer")
    a = WorkOrder(work_order_code="WO-A", title="A", status="sent",
                  organization_id=org.id, assigned_to_email="juan@x.com")
    b = WorkOrder(work_order_code="WO-B", title="B", status="sent",
                  organization_id=org.id, assigned_to_email="ana@x.com")
    db.add_all([a, b])
    db.commit()
    visible = rbac_service.filter_work_orders_by_scope(member, [a, b])
    assert {w.work_order_code for w in visible} == {"WO-A", "WO-B"}


def test_demo_member_does_not_see_legacy_null_org_rows(db):
    org = _org(db)
    u = _user(db, "demo_admin_x", organization_id=org.id, is_demo=True)
    member = _member(db, org, u, "admin")
    legacy = WorkOrder(work_order_code="WO-LEG", title="Legacy", status="sent",
                       organization_id=None, assigned_to_email="x@x.com")
    owned = WorkOrder(work_order_code="WO-OWN", title="Owned", status="sent",
                      organization_id=org.id, assigned_to_email="x@x.com")
    db.add_all([legacy, owned])
    db.commit()
    visible = rbac_service.filter_work_orders_by_scope(member, [legacy, owned], is_demo=True)
    assert {w.work_order_code for w in visible} == {"WO-OWN"}


def test_work_orders_endpoint_filters_by_session_scope(db):
    org = _org(db)
    u = _user(db, "juan2", organization_id=org.id)
    _member(db, org, u, "worker", scope_assignee_emails=["juan2@x.com"])
    db.add_all([
        WorkOrder(work_order_code="WO-MINE", title="Mine", status="sent",
                  organization_id=org.id, assigned_to_email="juan2@x.com"),
        WorkOrder(work_order_code="WO-OTHER", title="Other", status="sent",
                  organization_id=org.id, assigned_to_email="ana@x.com"),
    ])
    db.commit()
    token = _token(db, u)
    c = _client()
    rows = c.get("/api/work-orders", headers=_hdr(token)).json()
    assert {r["work_order_code"] for r in rows} == {"WO-MINE"}


# --------------------------------------------------------------------------- #
# Endpoint authorization
# --------------------------------------------------------------------------- #
def test_worker_denied_member_and_invite_endpoints(db):
    org = _org(db)
    u = _user(db, "worker_a", organization_id=org.id)
    _member(db, org, u, "worker")
    token = _token(db, u)
    c = _client()
    assert c.get("/api/org/members", headers=_hdr(token)).status_code == 403
    assert c.post("/api/org/invitations", json={"invited_role": "worker"},
                  headers=_hdr(token)).status_code == 403


def test_context_reports_role_and_dashboard(db):
    org = _org(db)
    u = _user(db, "camila2", organization_id=org.id)
    _member(db, org, u, "engineer")
    token = _token(db, u)
    c = _client()
    ctx = c.get("/api/org/context", headers=_hdr(token)).json()
    assert ctx["dashboard"]["role"] == "engineer"
    assert ctx["dashboard"]["title"] == "Labor & Agronomic Operations"
    assert ctx["permissions"]["can_view_labor_analytics"] is True
    assert ctx["permissions"]["can_manage_org_settings"] is False
    nav_keys = {n["key"] for n in ctx["dashboard"]["nav"]}
    assert "analytics" in nav_keys and "members" not in nav_keys


def test_legacy_admin_without_membership_keeps_full_access(db):
    # A pre-RBAC admin account (no OrganizationMember) must NOT be downgraded to
    # a worker; the context derives permissions from the legacy web role.
    u = AppUser(username="legacy_admin", password_hash=auth_service.hash_password("legacy_admin"),
                role="admin", is_demo=False)
    db.add(u)
    db.commit()
    token = _token(db, u)
    c = _client()
    ctx = c.get("/api/org/context", headers=_hdr(token)).json()
    assert ctx["has_membership"] is False
    assert ctx["dashboard"]["role"] == "admin"
    assert ctx["permissions"]["can_manage_members"] is True
    # ...and is NOT blocked by the member read-only guard (no membership → open)
    body = {"product_name": "Lime", "carbon_factor_value": 1.0,
            "carbon_factor_unit": "kgCO2e_per_kg_product"}
    assert c.post("/api/products", json=body, headers=_hdr(token)).status_code == 201


def test_admin_and_permitted_nonadmin_can_create_invites(db):
    org = _org(db)
    admin = _user(db, "boss", organization_id=org.id)
    _member(db, org, admin, "admin")
    sup = _user(db, "ana", organization_id=org.id)
    _member(db, org, sup, "supervisor")  # supervisor template grants can_invite_members

    c = _client()
    admin_tok, sup_tok = _token(db, admin), _token(db, sup)
    r1 = c.post("/api/org/invitations", json={"invited_role": "worker"}, headers=_hdr(admin_tok))
    assert r1.status_code == 201 and r1.json()["token"]
    r2 = c.post("/api/org/invitations", json={"invited_role": "worker"}, headers=_hdr(sup_tok))
    assert r2.status_code == 201 and r2.json()["token"]


# --------------------------------------------------------------------------- #
# Auditor is read-only (server-side, authoritative)
# --------------------------------------------------------------------------- #
def test_auditor_cannot_mutate_records(db):
    org = _org(db)
    aud = _user(db, "auditor_a", organization_id=org.id)
    _member(db, org, aud, "auditor")
    admin = _user(db, "admin_a", organization_id=org.id)
    _member(db, org, admin, "admin")
    aud_tok, admin_tok = _token(db, aud), _token(db, admin)
    body = {"product_name": "Urea", "carbon_factor_value": 2.0,
            "carbon_factor_unit": "kgCO2e_per_kg_product"}
    c = _client()
    # auditor: read allowed, write blocked server-side
    assert c.get("/api/products", headers=_hdr(aud_tok)).status_code == 200
    assert c.post("/api/products", json=body, headers=_hdr(aud_tok)).status_code == 403
    # a write-capable role (admin) is NOT blocked by the member guard
    assert c.post("/api/products", json=body, headers=_hdr(admin_tok)).status_code == 201


# --------------------------------------------------------------------------- #
# Invitation lifecycle
# --------------------------------------------------------------------------- #
def test_accept_invitation_creates_user_and_member(db):
    org = _org(db)
    inv, raw = rbac_service.create_invitation(
        db, organization_id=org.id, invited_role="worker",
        invited_email="newhire@x.com",
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.commit()
    res = rbac_service.accept_invitation(
        db, raw_token=raw, username="newhire", password="pw12345", full_name="New Hire",
        email="newhire@x.com",  # email-bound invite: acceptance must match
    )
    db.commit()
    assert res["ok"] is True
    user = auth_service.get_user(db, "newhire")
    assert user is not None
    member = rbac_service.get_membership(db, user.id, organization_id=org.id)
    assert member is not None and member.role == "worker"


def test_revoked_invitation_cannot_be_accepted(db):
    org = _org(db)
    inv, raw = rbac_service.create_invitation(db, organization_id=org.id, invited_role="worker")
    db.commit()
    rbac_service.revoke_invitation(db, inv.id)
    db.commit()
    res = rbac_service.accept_invitation(db, raw_token=raw, username="x", password="pw12345")
    assert res["ok"] is False and res["reason"] == "revoked"


def test_expired_invitation_cannot_be_accepted(db):
    org = _org(db)
    inv, raw = rbac_service.create_invitation(
        db, organization_id=org.id, invited_role="worker",
        expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    db.commit()
    assert rbac_service.validate_invitation(db, raw)["reason"] == "expired"
    res = rbac_service.accept_invitation(db, raw_token=raw, username="y", password="pw12345")
    assert res["ok"] is False and res["reason"] == "expired"


def test_over_max_uses_invitation_cannot_be_accepted(db):
    org = _org(db)
    inv, raw = rbac_service.create_invitation(
        db, organization_id=org.id, invited_role="worker", max_uses=1,
    )
    db.commit()
    first = rbac_service.accept_invitation(db, raw_token=raw, username="u1", password="pw12345")
    db.commit()
    assert first["ok"] is True
    second = rbac_service.accept_invitation(db, raw_token=raw, username="u2", password="pw12345")
    assert second["ok"] is False and second["reason"] == "accepted"


def test_accept_invitation_endpoint_is_public(db):
    org = _org(db)
    inv, raw = rbac_service.create_invitation(db, organization_id=org.id, invited_role="worker")
    db.commit()
    c = _client()
    # validate (public GET) then accept (public POST, no Bearer)
    v = c.get(f"/api/org/invitations/validate/{raw}")
    assert v.status_code == 200 and v.json()["valid"] is True
    r = c.post("/api/org/invitations/accept",
               json={"token": raw, "username": "pubhire", "password": "pw12345"})
    assert r.status_code == 200 and r.json()["ok"] is True
