"""Admin/staff login: password hashing, signed sessions, authentication.

Stdlib-only by design (pbkdf2 + HMAC) so the API stays slim for Vercel's
serverless size limit and the test suite runs fully offline with no native
build dependencies (no bcrypt, no PyJWT).

Credentials live in the ``app_users`` table (see ``AppUser``). A session is a
compact ``<payload>.<signature>`` token signed with SECRET_KEY, carrying the
username, role, demo flag, an expiry and a unique ``jti``. The token is
self-validating (signature + expiry), but each ``jti`` is also recorded in
``app_sessions`` so a session can be revoked server-side (logout / log-out-
everywhere): a revoked or unknown ``jti`` is rejected even though the signature
is still valid.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.operations import AppSession, AppUser

log = logging.getLogger("agave.auth")

_PBKDF2_ITERATIONS = 240_000
_ALGO = "pbkdf2_sha256"


# --------------------------------------------------------------------------- #
# Password hashing (pbkdf2-hmac-sha256)
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{_ALGO}${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$", 3)
        if algo != _ALGO:
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# --------------------------------------------------------------------------- #
# Stateless session tokens (HMAC-signed, with expiry)
# --------------------------------------------------------------------------- #
def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(body: str) -> str:
    sig = hmac.new(settings.secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256)
    return _b64(sig.digest())


def create_token(payload: dict, ttl_hours: Optional[int] = None) -> str:
    ttl = ttl_hours if ttl_hours is not None else settings.session_ttl_hours
    exp = datetime.now(timezone.utc) + timedelta(hours=ttl)
    data = {**payload, "exp": int(exp.timestamp())}
    body = _b64(json.dumps(data, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}"


def decode_token(token: Optional[str]) -> Optional[dict]:
    """Return the payload if the signature is valid and unexpired, else None."""
    if not token or "." not in token:
        return None
    body, _, sig = token.partition(".")
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    try:
        data = json.loads(_unb64(body).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if int(data.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
        return None
    return data


def create_session(
    db: Session, user: AppUser, ttl_hours: Optional[int] = None
) -> tuple[str, AppSession]:
    """Issue a signed token AND record its ``jti`` so it can be revoked later."""
    ttl = ttl_hours if ttl_hours is not None else settings.session_ttl_hours
    jti = secrets.token_urlsafe(24)
    expires = datetime.now(timezone.utc) + timedelta(hours=ttl)
    session = AppSession(
        jti=jti, user_id=user.id, username=user.username, expires_at=expires
    )
    db.add(session)
    db.flush()
    token = create_token(
        {
            "sub": user.username,
            "role": user.role,
            "is_demo": bool(user.is_demo),
            "jti": jti,
        },
        ttl_hours=ttl,
    )
    return token, session


def _session_is_active(db: Session, jti: str) -> bool:
    row = db.execute(
        select(AppSession).where(AppSession.jti == jti)
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return False
    expires = row.expires_at
    if expires is not None:
        # Stored naive (UTC); compare against a naive UTC now.
        if expires.tzinfo is not None:
            expires = expires.astimezone(timezone.utc).replace(tzinfo=None)
        if expires < datetime.now(timezone.utc).replace(tzinfo=None):
            return False
    return True


def revoke_session(db: Session, jti: Optional[str]) -> bool:
    """Revoke a single session by ``jti``. Returns True if a row was updated."""
    if not jti:
        return False
    result = db.execute(
        update(AppSession)
        .where(AppSession.jti == jti, AppSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()
    return bool(result.rowcount)


def revoke_all_for_user(db: Session, username: str) -> int:
    """Revoke every active session for a user ("log out everywhere")."""
    result = db.execute(
        update(AppSession)
        .where(AppSession.username == username, AppSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()
    return int(result.rowcount or 0)


def public_user(user: AppUser) -> dict:
    return {
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "is_demo": bool(user.is_demo),
    }


# --------------------------------------------------------------------------- #
# Lookup / authentication
# --------------------------------------------------------------------------- #
def get_user(db: Session, username: str) -> Optional[AppUser]:
    if not username:
        return None
    return db.execute(
        select(AppUser).where(AppUser.username == username)
    ).scalar_one_or_none()


def authenticate(db: Session, username: str, password: str) -> Optional[AppUser]:
    user = get_user(db, (username or "").strip())
    if not user or not user.is_active:
        return None
    if not verify_password(password or "", user.password_hash):
        return None
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return user


def user_from_token(db: Session, token: Optional[str]) -> Optional[AppUser]:
    payload = decode_token(token)
    if not payload:
        return None
    # Tokens issued by create_session carry a jti recorded in app_sessions;
    # reject it if that session was revoked or is unknown. (Tokens minted
    # without a jti — e.g. low-level tests — remain stateless.)
    jti = payload.get("jti")
    if jti and not _session_is_active(db, jti):
        return None
    user = get_user(db, payload.get("sub", ""))
    if not user or not user.is_active:
        return None
    return user


# --------------------------------------------------------------------------- #
# Seeding (idempotent; safe to call on every startup)
# --------------------------------------------------------------------------- #
def _ensure_user(
    db: Session, username: str, password: str, role: str, is_demo: bool
) -> None:
    existing = get_user(db, username)
    if existing:
        return
    db.add(
        AppUser(
            username=username,
            password_hash=hash_password(password),
            full_name=username.title(),
            role=role,
            is_demo=is_demo,
        )
    )
    db.commit()
    log.info("Seeded app_user '%s' (role=%s, demo=%s)", username, role, is_demo)


def seed_users(db: Session) -> None:
    """Ensure the DEMO account and (if configured) a real admin account exist.

    Idempotent: only creates accounts that are missing; never resets an existing
    password. Best-effort — callers should not let a failure crash startup.
    """
    _ensure_user(
        db,
        settings.demo_username,
        settings.demo_password,
        role="admin",
        is_demo=True,
    )
    if settings.auth_admin_username and settings.auth_admin_password:
        _ensure_user(
            db,
            settings.auth_admin_username,
            settings.auth_admin_password,
            role="admin",
            is_demo=False,
        )


# --------------------------------------------------------------------------- #
# Login throttling (brute-force / credential-stuffing mitigation)
# --------------------------------------------------------------------------- #
# In-process sliding window: after MAX failures for a key (ip+username) within
# WINDOW seconds, further attempts are locked out for the rest of the window.
# Best-effort on serverless (state is per-instance, reset on cold start); it
# raises the cost of online guessing without an external store. A successful
# login clears the counter for that key.
_LOGIN_MAX_FAILURES = 5
_LOGIN_WINDOW_SECONDS = 300
_login_failures: dict[str, list[float]] = {}
_login_lock = threading.Lock()


def _prune(stamps: list[float], now: float) -> list[float]:
    return [t for t in stamps if now - t < _LOGIN_WINDOW_SECONDS]


def login_retry_after(key: str) -> int:
    """Seconds the caller must wait before retrying, or 0 if not locked out."""
    now = time.monotonic()
    with _login_lock:
        stamps = _prune(_login_failures.get(key, []), now)
        _login_failures[key] = stamps
        if len(stamps) >= _LOGIN_MAX_FAILURES:
            return max(1, int(_LOGIN_WINDOW_SECONDS - (now - stamps[0])))
    return 0


def register_login_failure(key: str) -> None:
    now = time.monotonic()
    with _login_lock:
        stamps = _prune(_login_failures.get(key, []), now)
        stamps.append(now)
        _login_failures[key] = stamps


def reset_login_failures(key: str) -> None:
    with _login_lock:
        _login_failures.pop(key, None)
