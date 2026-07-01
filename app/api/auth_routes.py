"""Public authentication endpoints for the web admin login.

These are intentionally NOT behind the API-key RBAC (login must be reachable
without credentials). They authenticate a human against the ``app_users`` table
and issue a stateless signed session token. The Next.js frontend stores the
token in an httpOnly cookie and forwards it here as ``Authorization: Bearer``.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.integrations import email_client
from app.services import audit_service, auth_service, rbac_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str
    full_name: Optional[str] = None
    role: str
    is_demo: bool


class LoginResponse(BaseModel):
    token: str
    user: UserOut


class PasswordResetRequest(BaseModel):
    username: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class RegisterRequest(BaseModel):
    organization_name: str
    username: str
    password: str
    full_name: Optional[str] = None
    email: Optional[str] = None


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token else None


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    username = (payload.username or "").strip()
    ip = _client_ip(request)
    ua = request.headers.get("user-agent")
    throttle_key = f"{ip}:{username.lower()}"

    retry_after = auth_service.login_retry_after(throttle_key)
    if retry_after:
        raise HTTPException(
            429,
            "Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = auth_service.authenticate(db, username, payload.password)
    if not user:
        auth_service.register_login_failure(throttle_key)
        # Audit the failed attempt for accountability (no entity id — the
        # username may not even exist).
        audit_service.log(
            db, entity_type="app_user", entity_id=None, action="login_failed",
            changed_by=username or None, ip_address=ip, user_agent=ua,
            new_values={"username": username},
        )
        db.commit()
        raise HTTPException(401, "Invalid username or password")

    auth_service.reset_login_failures(throttle_key)
    token, _session = auth_service.create_session(db, user)
    audit_service.log(
        db, entity_type="app_user", entity_id=user.id, action="login",
        changed_by=user.username, ip_address=ip, user_agent=ua,
    )
    db.commit()
    return {"token": token, "user": auth_service.public_user(user)}


@router.get("/me", response_model=UserOut)
def me(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = auth_service.user_from_token(db, _bearer(authorization))
    if not user:
        raise HTTPException(401, "Not authenticated")
    return auth_service.public_user(user)


@router.post("/logout")
def logout(
    request: Request,
    all_sessions: bool = False,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Revoke the current session server-side (or all of the user's sessions).

    Revocation is authoritative: the token's jti is marked revoked in
    ``app_sessions`` so it is rejected on the next request even though its
    signature is still valid. The frontend also drops the cookie.
    """
    payload = auth_service.decode_token(_bearer(authorization))
    if payload:
        if all_sessions:
            auth_service.revoke_all_for_user(db, payload.get("sub", ""))
        else:
            auth_service.revoke_session(db, payload.get("jti"))
        audit_service.log(
            db, entity_type="app_user", entity_id=None,
            action="logout_all" if all_sessions else "logout",
            changed_by=payload.get("sub"), ip_address=_client_ip(request),
        )
        db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Password reset (no user enumeration)
# --------------------------------------------------------------------------- #
@router.post("/password-reset/request")
def password_reset_request(
    payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)
):
    """ALWAYS returns 200 ``{"ok": true}`` — the response never reveals whether
    the username exists. When it does (and email is configured for the account)
    a reset link is emailed; only a hash of the token is stored."""
    username = (payload.username or "").strip()
    ip = _client_ip(request)
    user = auth_service.get_user(db, username)
    if user and user.is_active:
        raw = auth_service.create_password_reset(db, user)
        if user.email and email_client.is_live():
            link = f"{settings.app_base_url.rstrip('/')}/reset-password/{raw}"
            try:
                email_client.send_email(
                    user.email,
                    "Reset your Agave Field password",
                    f"Use this link to reset your password: {link}\n\n"
                    f"It expires in {settings.password_reset_ttl_hours} hours. "
                    "If you did not request this, you can ignore this email.",
                )
            except Exception:  # pragma: no cover - never crash on email failure
                pass
        audit_service.log(
            db, entity_type="app_user", entity_id=user.id,
            action="password_reset_requested", changed_by=username, ip_address=ip,
        )
        db.commit()
    return {"ok": True}


@router.post("/password-reset/confirm")
def password_reset_confirm(
    payload: PasswordResetConfirm, request: Request, db: Session = Depends(get_db)
):
    """Validate the reset token + expiry, set the new password, invalidate the
    token, and revoke existing sessions. Returns ``{"ok": bool, "reason"?}``."""
    result = auth_service.reset_password(db, payload.token, payload.new_password)
    if result.get("ok"):
        audit_service.log(
            db, entity_type="app_user", entity_id=result.get("user_id"),
            action="password_reset", changed_by=result.get("username"),
            ip_address=_client_ip(request),
        )
        db.commit()
    return result


# --------------------------------------------------------------------------- #
# New-tenant self-signup (creates a brand-new organization + first admin)
# --------------------------------------------------------------------------- #
@router.post("/register", response_model=LoginResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Onboard a NEW tenant: a fresh organization, a first admin AppUser, and an
    admin membership. Joining an existing org stays invite-gated. On success the
    new admin is issued a session so they are logged straight in."""
    result = rbac_service.register_new_tenant(
        db,
        organization_name=payload.organization_name,
        username=payload.username,
        password=payload.password,
        full_name=payload.full_name,
        email=payload.email,
    )
    if not result.get("ok"):
        reason = result.get("reason", "invalid")
        status = 409 if reason == "username_taken" else 400
        raise HTTPException(status, f"Registration failed: {reason}")
    user = auth_service.get_user(db, result["username"])
    token, _session = auth_service.create_session(db, user)
    audit_service.log(
        db, entity_type="app_user", entity_id=user.id, action="register",
        changed_by=user.username, ip_address=_client_ip(request),
    )
    db.commit()
    return {"token": token, "user": auth_service.public_user(user)}
