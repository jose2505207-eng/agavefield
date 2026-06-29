"""Admin login: password hashing, signed sessions, login endpoint, demo seed,
server-side session revocation, login throttling, and auth audit logging."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models.operations import AppUser, AuditLog
from app.services import auth_service


@pytest.fixture(autouse=True)
def _clear_login_throttle():
    # The throttle is process-global in-memory state; isolate it per test.
    auth_service._login_failures.clear()
    yield
    auth_service._login_failures.clear()


def _client():
    from app.main import app
    return TestClient(app)


def _make_admin(db, username="boss", password="s3cret-pw"):
    db.add(
        AppUser(
            username=username,
            password_hash=auth_service.hash_password(password),
            full_name=username.title(),
            role="admin",
            is_demo=False,
        )
    )
    db.commit()


# --- password hashing ---
def test_password_hash_roundtrip_and_rejects_wrong():
    h = auth_service.hash_password("s3cret")
    assert h.startswith("pbkdf2_sha256$")
    assert "s3cret" not in h  # never stored in plaintext
    assert auth_service.verify_password("s3cret", h) is True
    assert auth_service.verify_password("nope", h) is False


# --- signed session tokens ---
def test_token_roundtrip_and_tamper_detection():
    tok = auth_service.create_token({"sub": "DEMO", "role": "admin", "is_demo": True})
    payload = auth_service.decode_token(tok)
    assert payload and payload["sub"] == "DEMO" and payload["is_demo"] is True
    # any tampering with the body invalidates the signature
    body, _, sig = tok.partition(".")
    assert auth_service.decode_token(f"{body}x.{sig}") is None
    assert auth_service.decode_token("garbage") is None


def test_expired_token_rejected():
    tok = auth_service.create_token({"sub": "DEMO"}, ttl_hours=-1)
    assert auth_service.decode_token(tok) is None


# --- seeding ---
def test_seed_creates_demo_account(db):
    auth_service.seed_users(db)
    demo = auth_service.get_user(db, settings.demo_username)
    assert demo is not None
    assert demo.is_demo is True
    assert demo.role == "admin"
    # idempotent: a second seed does not duplicate or reset
    auth_service.seed_users(db)
    assert db.query(AppUser).filter_by(username=settings.demo_username).count() == 1


def test_authenticate_demo(db):
    auth_service.seed_users(db)
    user = auth_service.authenticate(db, settings.demo_username, settings.demo_password)
    assert user is not None and user.is_demo is True
    assert auth_service.authenticate(db, settings.demo_username, "wrong") is None
    assert auth_service.authenticate(db, "ghost", "x") is None


# --- HTTP login flow ---
def test_login_endpoint_and_me(db):
    auth_service.seed_users(db)
    c = _client()
    r = c.post("/api/auth/login",
               json={"username": settings.demo_username, "password": settings.demo_password})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["is_demo"] is True
    token = data["token"]

    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == settings.demo_username

    assert c.get("/api/auth/me").status_code == 401  # no token
    assert c.post("/api/auth/login",
                  json={"username": settings.demo_username, "password": "bad"}).status_code == 401


# --- demo accounts are read-only (enforced server-side) ---
def test_demo_token_blocks_writes_but_allows_reads(db):
    c = _client()
    demo_token = auth_service.create_token({"sub": "DEMO", "role": "admin", "is_demo": True})
    real_token = auth_service.create_token({"sub": "boss", "role": "admin", "is_demo": False})
    hdr = lambda t: {"Authorization": f"Bearer {t}"}
    body = {"product_name": "Urea", "carbon_factor_value": 2.0,
            "carbon_factor_unit": "kgCO2e_per_kg_product"}

    # demo: reads pass, writes are refused
    assert c.get("/api/products", headers=hdr(demo_token)).status_code == 200
    assert c.post("/api/products", json=body, headers=hdr(demo_token)).status_code == 403

    # non-demo session can write
    assert c.post("/api/products", json=body, headers=hdr(real_token)).status_code == 201

    # no session token at all → unaffected by the demo guard (open dev mode)
    assert c.post("/api/products", json=body).status_code == 201


# --- server-side session revocation ---
def test_logout_revokes_session(db):
    _make_admin(db)
    c = _client()
    r = c.post("/api/auth/login", json={"username": "boss", "password": "s3cret-pw"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    hdr = {"Authorization": f"Bearer {token}"}

    # valid before logout
    assert c.get("/api/auth/me", headers=hdr).status_code == 200
    # logout revokes server-side...
    assert c.post("/api/auth/logout", headers=hdr).status_code == 200
    # ...so the still-signed, still-unexpired token is now rejected
    assert c.get("/api/auth/me", headers=hdr).status_code == 401


def test_logout_all_revokes_every_session(db):
    _make_admin(db)
    c = _client()
    t1 = c.post("/api/auth/login", json={"username": "boss", "password": "s3cret-pw"}).json()["token"]
    t2 = c.post("/api/auth/login", json={"username": "boss", "password": "s3cret-pw"}).json()["token"]
    h1, h2 = {"Authorization": f"Bearer {t1}"}, {"Authorization": f"Bearer {t2}"}
    assert c.get("/api/auth/me", headers=h1).status_code == 200
    assert c.get("/api/auth/me", headers=h2).status_code == 200
    # log out everywhere using one of the sessions
    assert c.post("/api/auth/logout?all_sessions=true", headers=h1).status_code == 200
    assert c.get("/api/auth/me", headers=h1).status_code == 401
    assert c.get("/api/auth/me", headers=h2).status_code == 401


def test_auth_endpoints_exempt_from_demo_guard(db):
    # The demo read-only guard must NOT block a demo session from hitting the
    # auth endpoints themselves (login is a POST; logout is a POST).
    c = _client()
    demo_token = auth_service.create_token({"sub": "DEMO", "role": "admin", "is_demo": True})
    r = c.post("/api/auth/logout", headers={"Authorization": f"Bearer {demo_token}"})
    assert r.status_code == 200  # not 403


# --- login throttling ---
def test_login_throttled_after_repeated_failures(db):
    _make_admin(db)
    c = _client()
    bad = {"username": "boss", "password": "wrong"}
    for _ in range(auth_service._LOGIN_MAX_FAILURES):
        assert c.post("/api/auth/login", json=bad).status_code == 401
    # next attempt is locked out, even with the CORRECT password
    locked = c.post("/api/auth/login", json={"username": "boss", "password": "s3cret-pw"})
    assert locked.status_code == 429
    assert "Retry-After" in locked.headers


def test_successful_login_clears_throttle(db):
    _make_admin(db)
    c = _client()
    for _ in range(auth_service._LOGIN_MAX_FAILURES - 1):
        c.post("/api/auth/login", json={"username": "boss", "password": "wrong"})
    # a correct login under the limit succeeds and resets the counter
    assert c.post("/api/auth/login", json={"username": "boss", "password": "s3cret-pw"}).status_code == 200
    # the counter is cleared, so a fresh wrong attempt does not immediately lock
    assert c.post("/api/auth/login", json={"username": "boss", "password": "wrong"}).status_code == 401


# --- auth audit trail ---
def test_login_and_failure_are_audited(db):
    _make_admin(db)
    c = _client()
    c.post("/api/auth/login", json={"username": "boss", "password": "wrong"})
    c.post("/api/auth/login", json={"username": "boss", "password": "s3cret-pw"})

    actions = {
        a.action
        for a in db.query(AuditLog).filter(AuditLog.entity_type == "app_user").all()
    }
    assert "login" in actions
    assert "login_failed" in actions
