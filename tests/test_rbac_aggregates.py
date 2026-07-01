"""Hardening tests for the org-RBAC layer:

- Email-bound invitation acceptance (match / mismatch).
- Password reset (happy path + expired / invalid token).
- New-tenant self-signup.
- Organization scoping threaded through the AGGREGATE endpoints
  (/api/carbon/summary, /api/review-queue, /api/system/status): a scoped member
  sees only their org's rows; a no-membership caller still sees everything.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models.operations import (
    AppUser,
    ExecutionRecord,
    Organization,
    WorkOrder,
)
from app.services import auth_service, rbac_service


@pytest.fixture(autouse=True)
def _clear_login_throttle():
    auth_service._login_failures.clear()
    yield
    auth_service._login_failures.clear()


def _client():
    from app.main import app
    return TestClient(app)


def _org(db, slug) -> Organization:
    org = rbac_service.get_or_create_organization(db, name=slug.title(), slug=slug)
    db.commit()
    return org


def _user(db, username, organization_id=None, email=None) -> AppUser:
    u = AppUser(
        username=username,
        password_hash=auth_service.hash_password(username + "_pw_12345"),
        full_name=username.title(),
        role="agronomist",
        is_demo=False,
        organization_id=organization_id,
        email=email,
    )
    db.add(u)
    db.commit()
    return u


def _token(db, user) -> str:
    token, _ = auth_service.create_session(db, user)
    db.commit()
    return token


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _execution(db, wo, carbon):
    er = ExecutionRecord(
        work_order_id=wo.id,
        work_order_item_id=1,  # FK not enforced on SQLite; carbon test needs no item
        actual_carbon_kgco2e=carbon,
        carbon_calculation_status="calculated",
        compliance_status="pending_review",
        submitted_at=datetime.utcnow(),
    )
    db.add(er)
    db.commit()
    return er


# --------------------------------------------------------------------------- #
# TASK 1 — email-bound invitation acceptance
# --------------------------------------------------------------------------- #
def test_email_bound_accept_rejects_mismatch(db):
    org = _org(db, "acme")
    inv, raw = rbac_service.create_invitation(
        db, organization_id=org.id, invited_role="worker",
        invited_email="hire@acme.com",
    )
    db.commit()
    bad = rbac_service.accept_invitation(
        db, raw_token=raw, username="hire", password="pw12345",
        email="attacker@evil.com",
    )
    assert bad["ok"] is False and bad["reason"] == "email_mismatch"
    # a missing email is also a mismatch (binding is enforced, not optional)
    missing = rbac_service.accept_invitation(
        db, raw_token=raw, username="hire", password="pw12345",
    )
    assert missing["ok"] is False and missing["reason"] == "email_mismatch"


def test_email_bound_accept_allows_match_case_insensitive(db):
    org = _org(db, "acme2")
    inv, raw = rbac_service.create_invitation(
        db, organization_id=org.id, invited_role="worker",
        invited_email="Hire@Acme.com",
    )
    db.commit()
    ok = rbac_service.accept_invitation(
        db, raw_token=raw, username="hire2", password="pw12345",
        email="  hire@acme.com  ",  # trimmed + lower-cased match
    )
    db.commit()
    assert ok["ok"] is True
    user = auth_service.get_user(db, "hire2")
    assert user is not None and user.email == "Hire@Acme.com"


def test_email_bound_accept_endpoint_returns_400_on_mismatch(db):
    org = _org(db, "acme3")
    inv, raw = rbac_service.create_invitation(
        db, organization_id=org.id, invited_role="worker",
        invited_email="hire@acme3.com",
    )
    db.commit()
    c = _client()
    r = c.post("/api/org/invitations/accept",
               json={"token": raw, "username": "h3", "password": "pw12345",
                     "email": "wrong@x.com"})
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# TASK 3 — password reset
# --------------------------------------------------------------------------- #
def test_password_reset_happy_path_revokes_sessions(db):
    org = _org(db, "reset-org")
    u = _user(db, "resetme", organization_id=org.id, email="resetme@x.com")
    old_token = _token(db, u)
    c = _client()
    # session works before reset
    assert c.get("/api/auth/me", headers=_hdr(old_token)).status_code == 200

    raw = auth_service.create_password_reset(db, u)
    db.commit()

    r = c.post("/api/auth/password-reset/confirm",
               json={"token": raw, "new_password": "brand-new-pw-9"})
    assert r.status_code == 200 and r.json()["ok"] is True

    # old session revoked, new password works, old password fails
    assert c.get("/api/auth/me", headers=_hdr(old_token)).status_code == 401
    db.expire_all()  # confirm committed in the request's own session; drop stale cache
    assert auth_service.authenticate(db, "resetme", "brand-new-pw-9") is not None
    assert auth_service.authenticate(db, "resetme", "resetme_pw_12345") is None


def test_password_reset_request_never_enumerates(db):
    _org(db, "enum-org")
    _user(db, "realuser", email="real@x.com")
    c = _client()
    r_real = c.post("/api/auth/password-reset/request", json={"username": "realuser"})
    r_ghost = c.post("/api/auth/password-reset/request", json={"username": "ghost"})
    assert r_real.status_code == 200 and r_real.json() == {"ok": True}
    assert r_ghost.status_code == 200 and r_ghost.json() == {"ok": True}


def test_password_reset_expired_and_invalid_token(db):
    u = _user(db, "expuser", email="exp@x.com")
    raw = auth_service.create_password_reset(db, u)
    # force expiry into the past
    u.password_reset_expires_at = datetime.utcnow() - timedelta(hours=1)
    db.commit()
    c = _client()
    expired = c.post("/api/auth/password-reset/confirm",
                     json={"token": raw, "new_password": "another-pw-88"})
    assert expired.json()["ok"] is False and expired.json()["reason"] == "expired"

    invalid = c.post("/api/auth/password-reset/confirm",
                     json={"token": "not-a-real-token", "new_password": "another-pw-88"})
    assert invalid.json()["ok"] is False and invalid.json()["reason"] == "invalid_token"


def test_password_reset_rejects_weak_password(db):
    u = _user(db, "weakpw", email="weak@x.com")
    raw = auth_service.create_password_reset(db, u)
    db.commit()
    c = _client()
    r = c.post("/api/auth/password-reset/confirm", json={"token": raw, "new_password": "short"})
    assert r.json()["ok"] is False and r.json()["reason"] == "weak_password"


# --------------------------------------------------------------------------- #
# TASK 3 — new-tenant self-signup
# --------------------------------------------------------------------------- #
def test_register_creates_new_tenant_and_admin(db):
    c = _client()
    r = c.post("/api/auth/register", json={
        "organization_name": "Rancho Nuevo",
        "username": "founder",
        "password": "founder-pw-123",
        "full_name": "The Founder",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["token"] and body["user"]["username"] == "founder"

    # org + admin membership were created
    user = auth_service.get_user(db, "founder")
    assert user is not None and user.organization_id is not None
    member = rbac_service.get_current_membership(db, user)
    assert member is not None and member.role == "admin"
    assert member.can_manage_members is True
    org = db.get(Organization, user.organization_id)
    assert org is not None and org.slug.startswith("rancho-nuevo")

    # the issued session authenticates
    assert c.get("/api/auth/me", headers=_hdr(body["token"])).status_code == 200


def test_register_rejects_duplicate_username(db):
    _user(db, "taken")
    c = _client()
    r = c.post("/api/auth/register", json={
        "organization_name": "Another Org",
        "username": "taken",
        "password": "some-pw-1234",
    })
    assert r.status_code == 409


def test_register_creates_distinct_org_for_same_name(db):
    """Signup must never JOIN an existing tenant — a new slug is always minted."""
    c = _client()
    r1 = c.post("/api/auth/register", json={
        "organization_name": "Twin Farms", "username": "twin1", "password": "pw-abc-123"})
    r2 = c.post("/api/auth/register", json={
        "organization_name": "Twin Farms", "username": "twin2", "password": "pw-abc-123"})
    assert r1.status_code == 201 and r2.status_code == 201
    u1 = auth_service.get_user(db, "twin1")
    u2 = auth_service.get_user(db, "twin2")
    assert u1.organization_id != u2.organization_id


# --------------------------------------------------------------------------- #
# TASK 4 — org scoping through aggregate endpoints
# --------------------------------------------------------------------------- #
def _two_orgs_with_carbon(db):
    org_a = _org(db, "org-a")
    org_b = _org(db, "org-b")
    wo_a = WorkOrder(work_order_code="WO-A", title="A", status="sent",
                     organization_id=org_a.id, assigned_to_email="a@x.com")
    wo_b = WorkOrder(work_order_code="WO-B", title="B", status="sent",
                     organization_id=org_b.id, assigned_to_email="b@x.com")
    db.add_all([wo_a, wo_b])
    db.commit()
    _execution(db, wo_a, carbon=100.0)
    _execution(db, wo_b, carbon=500.0)
    return org_a, org_b, wo_a, wo_b


def test_carbon_summary_scoped_for_member_and_full_for_anonymous(db):
    org_a, org_b, _, _ = _two_orgs_with_carbon(db)
    eng = _user(db, "eng-a", organization_id=org_a.id)
    rbac_service.create_member(db, organization_id=org_a.id, app_user_id=eng.id, role="engineer")
    db.commit()
    token = _token(db, eng)
    c = _client()

    scoped = c.get("/api/carbon/summary", headers=_hdr(token)).json()
    assert scoped["total_actual_kgco2e"] == 100.0  # only org A

    full = c.get("/api/carbon/summary").json()  # no session → no filtering
    assert full["total_actual_kgco2e"] == 600.0  # both orgs


def test_review_queue_scoped_for_member(db):
    org_a, org_b, wo_a, wo_b = _two_orgs_with_carbon(db)
    eng = _user(db, "eng-a2", organization_id=org_a.id)
    rbac_service.create_member(db, organization_id=org_a.id, app_user_id=eng.id, role="engineer")
    db.commit()
    token = _token(db, eng)
    c = _client()

    scoped = c.get("/api/review-queue", headers=_hdr(token)).json()
    assert len(scoped) == 1
    assert {r["work_order_id"] for r in scoped} == {wo_a.id}

    full = c.get("/api/review-queue").json()
    assert len(full) == 2


def test_system_status_counts_scoped_for_member(db):
    org_a, org_b, _, _ = _two_orgs_with_carbon(db)
    eng = _user(db, "eng-a3", organization_id=org_a.id)
    rbac_service.create_member(db, organization_id=org_a.id, app_user_id=eng.id, role="engineer")
    db.commit()
    token = _token(db, eng)
    c = _client()

    scoped = c.get("/api/system/status", headers=_hdr(token)).json()["counts"]
    assert scoped["work_orders"] == 1 and scoped["executions"] == 1

    full = c.get("/api/system/status").json()["counts"]
    assert full["work_orders"] == 2 and full["executions"] == 2


def test_worker_scope_narrows_aggregate_further(db):
    """A self-scoped worker only aggregates their own assigned work orders."""
    org_a = _org(db, "org-worker")
    mine = WorkOrder(work_order_code="WO-MINE", title="Mine", status="sent",
                     organization_id=org_a.id, assigned_to_email="juan@x.com")
    other = WorkOrder(work_order_code="WO-OTHER", title="Other", status="sent",
                      organization_id=org_a.id, assigned_to_email="ana@x.com")
    db.add_all([mine, other])
    db.commit()
    _execution(db, mine, carbon=42.0)
    _execution(db, other, carbon=999.0)
    juan = _user(db, "juan-w", organization_id=org_a.id)
    rbac_service.create_member(db, organization_id=org_a.id, app_user_id=juan.id,
                               role="worker", scope_assignee_emails=["juan@x.com"])
    db.commit()
    token = _token(db, juan)
    c = _client()
    scoped = c.get("/api/carbon/summary", headers=_hdr(token)).json()
    assert scoped["total_actual_kgco2e"] == 42.0
