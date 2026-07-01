"""FastAPI dependencies for organization RBAC (session-based).

These resolve the logged-in ``AppUser`` from the signed session Bearer token,
then their ``OrganizationMember`` (role + effective permissions + data scope),
and guard endpoints with ``require_permission(...)``.

This layer is INDEPENDENT of the API-key RBAC in ``app/api/auth.py`` (which
gates the legacy ops endpoints) and of the demo read-only guard. The org
endpoints authenticate humans by session, not by API key.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.operations import AppUser, OrganizationMember
from app.services import auth_service, rbac_service


def bearer_token(authorization: Optional[str] = Header(default=None)) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token else None


def current_user(
    token: Optional[str] = Depends(bearer_token),
    db: Session = Depends(get_db),
) -> AppUser:
    user = auth_service.user_from_token(db, token)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def optional_user(
    token: Optional[str] = Depends(bearer_token),
    db: Session = Depends(get_db),
) -> Optional[AppUser]:
    return auth_service.user_from_token(db, token)


def current_membership(
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> OrganizationMember:
    member = rbac_service.get_current_membership(db, user)
    if not member:
        raise HTTPException(403, "No active organization membership")
    return member


def optional_membership(
    token: Optional[str] = Depends(bearer_token),
    db: Session = Depends(get_db),
) -> Optional[OrganizationMember]:
    """Resolve the caller's membership if they carry a valid session, else None.

    Used by list endpoints to apply data-scope filtering. Returning None (no
    session / no membership) preserves the open / API-key behaviour, so existing
    flows and tests are unaffected.
    """
    return rbac_service.membership_from_token(db, token)


def scope_context(
    token: Optional[str] = Depends(bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    """``{"member": OrganizationMember|None, "is_demo": bool}`` for row filtering."""
    user = auth_service.user_from_token(db, token)
    member = rbac_service.get_current_membership(db, user)
    return {"member": member, "is_demo": bool(user and user.is_demo)}


def require_permission(permission: str):
    """Dependency factory: 403 unless the caller's membership grants `permission`."""

    def _dep(member: OrganizationMember = Depends(current_membership)) -> OrganizationMember:
        if not rbac_service.has_permission(member, permission):
            raise HTTPException(403, f"Missing permission: {permission}")
        return member

    return _dep
