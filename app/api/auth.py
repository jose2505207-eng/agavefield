"""Lightweight role-based access control via API keys.

A request authenticates with the `X-API-Key` header. Each configured key maps
to a role (admin / agronomist / reviewer). Field workers are NOT covered here —
they use their per-work-order token on the public mobile completion page.

Open-mode: if NO role keys are configured, auth is disabled (local dev / current
behavior) so existing flows and tests keep working. Set keys in production to
enforce RBAC. Apply via `include_router(..., dependencies=[Depends(require_staff)])`.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException

from app.config import settings

OPEN = "open"


def _key_map() -> dict[str, str]:
    m: dict[str, str] = {}
    if settings.admin_api_key:
        m[settings.admin_api_key] = "admin"
    if settings.agronomist_api_key:
        m[settings.agronomist_api_key] = "agronomist"
    if settings.reviewer_api_key:
        m[settings.reviewer_api_key] = "reviewer"
    return m


def auth_enabled() -> bool:
    return bool(_key_map())


def get_role(x_api_key: Optional[str] = Header(default=None)) -> str:
    """Resolve the caller's role from the API key, or OPEN when auth is off."""
    km = _key_map()
    if not km:
        return OPEN  # no keys configured → open dev mode
    if not x_api_key or x_api_key not in km:
        raise HTTPException(401, "Missing or invalid API key")
    return km[x_api_key]


def require_staff(role: str = Depends(get_role)) -> str:
    """Allow admin or agronomist (open mode always passes)."""
    if role == OPEN or role in ("admin", "agronomist"):
        return role
    raise HTTPException(403, "Requires admin or agronomist")


def require_reviewer(role: str = Depends(get_role)) -> str:
    """Allow admin, agronomist, or reviewer (open mode always passes)."""
    if role == OPEN or role in ("admin", "agronomist", "reviewer"):
        return role
    raise HTTPException(403, "Requires reviewer access")
