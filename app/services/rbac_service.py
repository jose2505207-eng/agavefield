"""Organization RBAC: roles, permission resolution, data-scope filtering,
membership + invitation lifecycle, and role-driven dashboard config.

This is the authoritative permission layer for the multi-user profile system.
It sits ALONGSIDE the existing API-key RBAC (``app/api/auth.py``) and the admin
login sessions (``auth_service``):

- ``auth_service`` answers "who is this AppUser?" (signed session).
- ``rbac_service`` answers "what may this AppUser do, and which rows may they
  see?" via their ``OrganizationMember`` (role + effective permissions + scope).

Permissions are stored as normalized booleans on the membership. A role only
seeds *defaults* (``ROLE_TEMPLATES``); per-member overrides then diverge from
the template, so all checks read the stored booleans — never the role string.
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations import email_client
from app.models.operations import (
    AppUser,
    Invitation,
    Organization,
    OrganizationMember,
    WorkOrder,
)
from app.services import audit_service, auth_service

log = logging.getLogger("agave.rbac")

# --------------------------------------------------------------------------- #
# Permission catalogue
# --------------------------------------------------------------------------- #
PERMISSION_FIELDS: tuple[str, ...] = (
    "can_invite_members",
    "can_create_work_orders",
    "can_assign_work_orders",
    "can_review_work_orders",
    "can_manage_catalogs",
    "can_view_reports",
    "can_view_labor_analytics",
    "can_manage_org_settings",
    "can_manage_members",
    "can_export_data",
)

# Write-capable permissions. A member with NONE of these is "read-only" (auditor,
# bare worker) and is blocked from mutating session requests by the middleware in
# ``app.main`` — the same authoritative pattern as the demo read-only guard.
WRITE_PERMISSIONS: tuple[str, ...] = (
    "can_invite_members",
    "can_create_work_orders",
    "can_assign_work_orders",
    "can_review_work_orders",
    "can_manage_catalogs",
    "can_manage_org_settings",
    "can_manage_members",
)

ROLES = ("worker", "supervisor", "engineer", "admin", "auditor")
DATA_SCOPES = ("self", "team", "ranch", "organization")


def _perms(**overrides: bool) -> dict[str, bool]:
    base = {f: False for f in PERMISSION_FIELDS}
    base.update(overrides)
    return base


# Sensible default permission set per role. These are *templates* only; a
# member's stored permissions may diverge via overrides.
ROLE_TEMPLATES: dict[str, dict] = {
    "worker": {
        "data_scope": "self",
        "permissions": _perms(),  # all False: acts via the token-based mobile page
    },
    "supervisor": {
        "data_scope": "team",
        "permissions": _perms(
            can_invite_members=True,
            can_create_work_orders=True,
            can_assign_work_orders=True,
            can_view_reports=True,
        ),
    },
    "engineer": {
        "data_scope": "organization",
        "permissions": _perms(
            can_create_work_orders=True,
            can_assign_work_orders=True,
            can_review_work_orders=True,
            can_manage_catalogs=True,
            can_view_reports=True,
            can_view_labor_analytics=True,
            can_export_data=True,
        ),
    },
    "admin": {
        "data_scope": "organization",
        "permissions": _perms(**{f: True for f in PERMISSION_FIELDS}),
    },
    "auditor": {
        "data_scope": "organization",
        "permissions": _perms(
            can_view_reports=True,
            can_view_labor_analytics=True,
            can_export_data=True,
        ),  # read-only: no write permissions
    },
}


def role_template(role: str) -> dict:
    return ROLE_TEMPLATES.get(role, ROLE_TEMPLATES["worker"])


def resolve_permissions(role: str, overrides: Optional[dict] = None) -> dict[str, bool]:
    """Effective permissions = role template defaults, then per-member overrides.

    Only known permission keys are honoured; unknown keys are ignored. This is
    the single source of truth used both when seeding a member and when an
    admin edits one, so role + override always produce a deterministic set.
    """
    effective = dict(role_template(role)["permissions"])
    for k, v in (overrides or {}).items():
        if k in PERMISSION_FIELDS and v is not None:
            effective[k] = bool(v)
    return effective


def has_permission(member: Optional[OrganizationMember], perm: str) -> bool:
    if member is None or not member.is_active:
        return False
    return bool(getattr(member, perm, False))


def is_read_only(member: Optional[OrganizationMember]) -> bool:
    """True when the member holds no write-capable permission (auditor/worker)."""
    if member is None:
        return False  # non-members are not governed by this guard (open/legacy)
    return not any(getattr(member, p, False) for p in WRITE_PERMISSIONS)


def permission_dict(member: OrganizationMember) -> dict[str, bool]:
    return {f: bool(getattr(member, f)) for f in PERMISSION_FIELDS}


# --------------------------------------------------------------------------- #
# Membership resolution
# --------------------------------------------------------------------------- #
def get_membership(
    db: Session, app_user_id: int, organization_id: Optional[int] = None
) -> Optional[OrganizationMember]:
    stmt = select(OrganizationMember).where(
        OrganizationMember.app_user_id == app_user_id,
        OrganizationMember.is_active.is_(True),
    )
    if organization_id is not None:
        stmt = stmt.where(OrganizationMember.organization_id == organization_id)
    return db.execute(stmt.order_by(OrganizationMember.id.asc())).scalars().first()


def get_current_membership(db: Session, user: Optional[AppUser]) -> Optional[OrganizationMember]:
    """Resolve the AppUser's primary active membership (their home org first)."""
    if user is None:
        return None
    return get_membership(db, user.id, organization_id=user.organization_id)


def membership_from_token(db: Session, token: Optional[str]) -> Optional[OrganizationMember]:
    user = auth_service.user_from_token(db, token)
    return get_current_membership(db, user)


# --------------------------------------------------------------------------- #
# Data-scope filtering (authoritative row visibility)
# --------------------------------------------------------------------------- #
def _as_set(values: Optional[Iterable]) -> set:
    return set(values or [])


def can_access_work_order(
    member: Optional[OrganizationMember], wo: WorkOrder, *, is_demo: bool = False
) -> bool:
    """Whether `member` may see a single work order, honouring org isolation
    and the member's data scope. Mirrors :func:`filter_work_orders_by_scope`."""
    if member is None:
        return True  # no membership → open/legacy behaviour (unchanged)
    # Org isolation: demo members are confined to their org; non-demo members
    # additionally see legacy (NULL-org) rows.
    if is_demo:
        if wo.organization_id != member.organization_id:
            return False
    else:
        if wo.organization_id not in (member.organization_id, None):
            return False

    scope = member.data_scope
    if scope == "organization":
        return True
    if scope == "ranch":
        return wo.field_id in _as_set(member.scope_ranch_ids)
    if scope == "team":
        return (
            wo.field_id in _as_set(member.scope_ranch_ids)
            or wo.lot_id in _as_set(member.scope_lot_ids)
            or (wo.assigned_to_email or "") in _as_set(member.scope_assignee_emails)
        )
    # self
    return (wo.assigned_to_email or "") in _as_set(member.scope_assignee_emails)


def filter_work_orders_by_scope(
    member: Optional[OrganizationMember],
    work_orders: Iterable[WorkOrder],
    *,
    is_demo: bool = False,
) -> list[WorkOrder]:
    """Drop any work order the member is not allowed to see.

    Called at the service/route boundary so the API can NEVER return
    out-of-scope rows even if a client crafts a request directly.
    """
    if member is None:
        return list(work_orders)
    return [w for w in work_orders if can_access_work_order(member, w, is_demo=is_demo)]


def allowed_work_order_ids(
    db: Session,
    member: Optional[OrganizationMember],
    *,
    is_demo: bool = False,
) -> Optional[list[int]]:
    """The work-order ids visible to ``member``, or ``None`` when there is no
    membership (open / API-key / legacy → no filtering, preserving today's
    behaviour for the aggregate endpoints).

    Reuses :func:`can_access_work_order` so aggregate endpoints scope by exactly
    the same org-isolation + data-scope rules as the list endpoints — no
    duplicated scope logic. An empty list means the member can see no work
    orders (their aggregates are correctly empty)."""
    if member is None:
        return None
    wos = db.execute(select(WorkOrder)).scalars().all()
    return [w.id for w in wos if can_access_work_order(member, w, is_demo=is_demo)]


def filter_executions_by_scope(
    db: Session,
    member: Optional[OrganizationMember],
    executions: list,
    *,
    is_demo: bool = False,
) -> list:
    """Filter execution records by the work order each belongs to.

    Executions inherit visibility from their parent work order, so a worker only
    sees executions for work orders within their scope.
    """
    if member is None:
        return list(executions)
    wo_ids = {e.work_order_id for e in executions if e.work_order_id is not None}
    if not wo_ids:
        return list(executions)
    wos = db.execute(select(WorkOrder).where(WorkOrder.id.in_(wo_ids))).scalars().all()
    allowed = {
        w.id for w in wos if can_access_work_order(member, w, is_demo=is_demo)
    }
    return [e for e in executions if e.work_order_id in allowed]


# --------------------------------------------------------------------------- #
# Dashboard config (role-driven; the frontend renders from this, not hardcode)
# --------------------------------------------------------------------------- #
_DASHBOARD_TITLES = {
    "worker": "My Field Work",
    "supervisor": "Team Field Operations",
    "engineer": "Labor & Agronomic Operations",
    "admin": "Organization Control Center",
    "auditor": "Compliance & Traceability Review",
}


# Backward-compat: a logged-in AppUser with NO organization membership (e.g. the
# legacy AUTH_ADMIN account or a pre-RBAC admin) must not be downgraded to a bare
# worker. Map their legacy web role to an org role so existing admins keep full
# access until they are formally added as members.
_LEGACY_ROLE_TO_ORG = {"admin": "admin", "agronomist": "engineer", "reviewer": "engineer"}


def fallback_role_for_user(user: Optional[AppUser]) -> str:
    if user is None:
        return "worker"
    return _LEGACY_ROLE_TO_ORG.get((user.role or "").lower(), "worker")


def dashboard_config(
    member: Optional[OrganizationMember] = None,
    *,
    role: Optional[str] = None,
    permissions: Optional[dict] = None,
    data_scope: Optional[str] = None,
) -> dict:
    """Resolved, permission-aware dashboard + navigation descriptor.

    Pass ``member`` for a real membership, or explicit ``role``/``permissions``
    for the no-membership fallback (legacy admins).
    """
    eff_role = role or (member.role if member else "worker")
    perms = (
        permissions
        if permissions is not None
        else (permission_dict(member) if member else {f: False for f in PERMISSION_FIELDS})
    )
    scope = data_scope or (member.data_scope if member else "organization")
    return {
        "role": eff_role,
        "title": _DASHBOARD_TITLES.get(eff_role, "My Field Work"),
        "data_scope": scope,
        "nav": _nav_for(perms, eff_role),
    }


# Navigation catalogue. Each item lists the permission(s)/role(s) that reveal it.
# `key` matches a frontend route; the sidebar filters by these flags.
_NAV_CATALOGUE = [
    {"key": "dashboard", "label": "Dashboard", "href": "/", "always": True},
    {"key": "my-work", "label": "My Work", "href": "/", "roles": ["worker"]},
    {"key": "work-orders", "label": "Work Orders", "href": "/work-orders",
     "any": ["can_create_work_orders", "can_assign_work_orders", "can_view_reports"]},
    {"key": "execution", "label": "Field Execution", "href": "/execution",
     "any": ["can_review_work_orders", "can_view_reports"]},
    {"key": "review", "label": "Review Queue", "href": "/review",
     "any": ["can_review_work_orders"]},
    {"key": "timeline", "label": "Evidence Timeline", "href": "/timeline",
     "any": ["can_view_reports", "can_view_labor_analytics"]},
    {"key": "carbon", "label": "Carbon & Traceability", "href": "/carbon",
     "any": ["can_view_reports", "can_view_labor_analytics"]},
    {"key": "analytics", "label": "Labor Analytics", "href": "/carbon",
     "any": ["can_view_labor_analytics"]},
    {"key": "fields", "label": "Fields / Lots", "href": "/fields",
     "any": ["can_view_reports", "can_create_work_orders"]},
    {"key": "catalogs", "label": "Catalogs", "href": "/catalogs",
     "any": ["can_manage_catalogs"]},
    {"key": "members", "label": "Members", "href": "/organization/members",
     "any": ["can_manage_members", "can_invite_members"]},
    {"key": "invitations", "label": "Invitations", "href": "/organization/invitations",
     "any": ["can_invite_members"]},
    {"key": "audit", "label": "Audit Trail", "href": "/timeline",
     "any": ["can_export_data", "can_manage_org_settings"]},
    {"key": "settings", "label": "Settings", "href": "/settings", "always": True},
]


def _nav_for(perms: dict, role: str) -> list[dict]:
    out = []
    for item in _NAV_CATALOGUE:
        if item.get("always"):
            ok = True
        elif "roles" in item:
            ok = role in item["roles"]
        elif "any" in item:
            ok = any(perms.get(p) for p in item["any"])
        else:
            ok = False
        if ok:
            out.append({"key": item["key"], "label": item["label"], "href": item["href"]})
    return out


# --------------------------------------------------------------------------- #
# Organization + membership CRUD
# --------------------------------------------------------------------------- #
def get_or_create_organization(
    db: Session, name: str, slug: str, description: Optional[str] = None
) -> Organization:
    org = db.execute(
        select(Organization).where(Organization.slug == slug)
    ).scalar_one_or_none()
    if org:
        return org
    org = Organization(name=name, slug=slug, description=description)
    db.add(org)
    db.flush()
    return org


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return base[:56] or "org"


def _unique_slug(db: Session, base: str) -> str:
    slug = base
    while db.execute(
        select(Organization).where(Organization.slug == slug)
    ).scalar_one_or_none() is not None:
        slug = f"{base}-{secrets.token_hex(3)}"
    return slug


def register_new_tenant(
    db: Session,
    *,
    organization_name: str,
    username: str,
    password: str,
    full_name: Optional[str] = None,
    email: Optional[str] = None,
) -> dict:
    """Self-service onboarding of a BRAND-NEW tenant.

    Creates a fresh Organization + a first admin AppUser + an admin
    OrganizationMember. This path never joins an existing org (a unique slug is
    always minted), so joining a tenant stays invite-gated. Returns
    ``{"ok": True, ...}`` or ``{"ok": False, "reason": ...}``. Audit-logged.
    """
    username = (username or "").strip()
    org_name = (organization_name or "").strip()
    if not org_name:
        return {"ok": False, "reason": "organization_name_required"}
    if not username:
        return {"ok": False, "reason": "username_required"}
    if not password or len(password) < 8:
        return {"ok": False, "reason": "weak_password"}
    if auth_service.get_user(db, username) is not None:
        return {"ok": False, "reason": "username_taken"}

    slug = _unique_slug(db, _slugify(org_name))
    org = get_or_create_organization(db, name=org_name, slug=slug)
    user = AppUser(
        username=username,
        password_hash=auth_service.hash_password(password),
        full_name=full_name or username.title(),
        role="admin",  # web role label; org role lives on the membership
        is_demo=False,
        organization_id=org.id,
        email=(email or None),
    )
    db.add(user)
    db.flush()
    member = create_member(
        db, organization_id=org.id, app_user_id=user.id, role="admin", actor=username
    )
    audit_service.log(
        db, entity_type="organization", entity_id=org.id, action="org_created",
        new_values={"name": org.name, "slug": org.slug, "admin_username": username},
        changed_by=username,
    )
    db.flush()
    return {
        "ok": True,
        "organization_id": org.id,
        "organization_slug": org.slug,
        "username": username,
        "member_id": member.id,
        "role": member.role,
    }


def create_member(
    db: Session,
    *,
    organization_id: int,
    app_user_id: int,
    role: str,
    permission_overrides: Optional[dict] = None,
    data_scope: Optional[str] = None,
    scope_ranch_ids: Optional[list] = None,
    scope_lot_ids: Optional[list] = None,
    scope_assignee_emails: Optional[list] = None,
    actor: Optional[str] = None,
) -> OrganizationMember:
    role = role if role in ROLES else "worker"
    perms = resolve_permissions(role, permission_overrides)
    scope = data_scope or role_template(role)["data_scope"]
    member = OrganizationMember(
        organization_id=organization_id,
        app_user_id=app_user_id,
        role=role,
        data_scope=scope if scope in DATA_SCOPES else "self",
        scope_ranch_ids=scope_ranch_ids,
        scope_lot_ids=scope_lot_ids,
        scope_assignee_emails=scope_assignee_emails,
        **perms,
    )
    db.add(member)
    db.flush()
    # Point the AppUser at this org for fast login resolution (first membership wins).
    user = db.get(AppUser, app_user_id)
    if user and user.organization_id is None:
        user.organization_id = organization_id
    audit_service.log(
        db, entity_type="organization_member", entity_id=member.id,
        action="member_created",
        new_values={"role": role, "data_scope": member.data_scope, **perms},
        changed_by=actor,
    )
    db.flush()
    return member


def update_member(
    db: Session,
    member_id: int,
    *,
    role: Optional[str] = None,
    permission_overrides: Optional[dict] = None,
    data_scope: Optional[str] = None,
    scope_ranch_ids: Optional[list] = None,
    scope_lot_ids: Optional[list] = None,
    scope_assignee_emails: Optional[list] = None,
    actor: Optional[str] = None,
) -> Optional[OrganizationMember]:
    member = db.get(OrganizationMember, member_id)
    if not member:
        return None
    old = {"role": member.role, "data_scope": member.data_scope,
           **permission_dict(member)}

    role_changed = role is not None and role in ROLES and role != member.role
    if role_changed:
        member.role = role
    # Recompute effective permissions from the (possibly new) role + overrides.
    if role_changed or permission_overrides is not None:
        effective = resolve_permissions(member.role, permission_overrides)
        for f in PERMISSION_FIELDS:
            setattr(member, f, effective[f])
    if data_scope is not None and data_scope in DATA_SCOPES:
        member.data_scope = data_scope
    if scope_ranch_ids is not None:
        member.scope_ranch_ids = scope_ranch_ids
    if scope_lot_ids is not None:
        member.scope_lot_ids = scope_lot_ids
    if scope_assignee_emails is not None:
        member.scope_assignee_emails = scope_assignee_emails
    db.flush()

    action = "role_changed" if role_changed else "permissions_changed"
    audit_service.log(
        db, entity_type="organization_member", entity_id=member.id, action=action,
        old_values=old,
        new_values={"role": member.role, "data_scope": member.data_scope,
                    **permission_dict(member)},
        changed_by=actor,
    )
    db.flush()
    return member


def deactivate_member(
    db: Session, member_id: int, actor: Optional[str] = None
) -> Optional[OrganizationMember]:
    member = db.get(OrganizationMember, member_id)
    if not member:
        return None
    member.is_active = False
    db.flush()
    audit_service.log(
        db, entity_type="organization_member", entity_id=member.id,
        action="member_deactivated", changed_by=actor,
    )
    db.flush()
    return member


def list_members(db: Session, organization_id: int) -> list[OrganizationMember]:
    return list(
        db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(OrganizationMember.id.asc())
        ).scalars().all()
    )


# --------------------------------------------------------------------------- #
# Invitations
# --------------------------------------------------------------------------- #
def _hash_token(token: str) -> str:
    """Keyless SHA-256 (same scheme as work-order link tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()


def _gen_verification_code() -> str:
    """A short, human-transcribable one-time code (6 digits)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def invite_verification_required(invited_email: Optional[str]) -> bool:
    """Whether an emailed verification code should be issued for this invite.

    Gated on the config flag AND a live (non-console) email provider AND an
    invited address to send to. When email is not configured this returns False
    so acceptance degrades to plain email-match binding (never blocks on a code
    that could never be delivered)."""
    return bool(
        settings.require_invite_email_verification
        and invited_email
        and email_client.is_live()
    )


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_invitation(
    db: Session,
    *,
    organization_id: int,
    invited_role: str,
    invited_permissions: Optional[dict] = None,
    invited_data_scope: Optional[str] = None,
    invited_email: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    max_uses: int = 1,
    created_by_user_id: Optional[int] = None,
    actor: Optional[str] = None,
) -> tuple[Invitation, str]:
    """Create an invitation; return (row, raw_token). The raw token is shown to
    the caller ONCE and never persisted — only its hash is stored."""
    role = invited_role if invited_role in ROLES else "worker"
    scope = invited_data_scope or role_template(role)["data_scope"]
    raw_token = secrets.token_urlsafe(32)
    inv = Invitation(
        organization_id=organization_id,
        invited_email=(invited_email or None),
        invited_role=role,
        invited_permissions=invited_permissions or None,
        invited_data_scope=scope if scope in DATA_SCOPES else "self",
        token_hash=_hash_token(raw_token),
        created_by_user_id=created_by_user_id,
        expires_at=expires_at,
        max_uses=max(1, int(max_uses or 1)),
        used_count=0,
        status="pending",
    )
    db.add(inv)
    db.flush()
    # Config-gated email verification: when enabled and a live email provider is
    # configured, mint a one-time code (store only its hash) and email it to the
    # invited address. Best-effort — a send failure must not abort invite creation.
    if invite_verification_required(inv.invited_email):
        code = _gen_verification_code()
        inv.verification_code_hash = _hash_token(code)
        try:
            email_client.send_email(
                inv.invited_email,
                "Your Agave Field invitation verification code",
                f"Your verification code is: {code}\n\n"
                "Enter it together with the invitation link to join the "
                "organization. It is single-use and tied to this email address.",
            )
        except Exception:  # pragma: no cover - defensive; never crash on email
            log.warning("Failed to send invite verification code to %s", inv.invited_email)
        db.flush()
    audit_service.log(
        db, entity_type="invitation", entity_id=inv.id, action="invite_created",
        new_values={"role": role, "data_scope": inv.invited_data_scope,
                    "email": inv.invited_email, "max_uses": inv.max_uses,
                    "verification_required": inv.verification_code_hash is not None},
        changed_by=actor,
    )
    db.flush()
    return inv, raw_token


def _invitation_state(inv: Invitation) -> str:
    """Derive the effective state, accounting for expiry/usage even if the
    stored status is still 'pending'."""
    if inv.status in ("revoked", "accepted"):
        return inv.status
    if inv.expires_at is not None and inv.expires_at < _now():
        return "expired"
    if inv.used_count >= inv.max_uses:
        return "accepted"
    return "pending"


def find_invitation_by_token(db: Session, raw_token: str) -> Optional[Invitation]:
    if not raw_token:
        return None
    return db.execute(
        select(Invitation).where(Invitation.token_hash == _hash_token(raw_token))
    ).scalars().first()


def validate_invitation(db: Session, raw_token: str) -> dict:
    """Return a validity descriptor for an invite token (no side effects)."""
    inv = find_invitation_by_token(db, raw_token)
    if not inv:
        return {"valid": False, "reason": "not_found"}
    state = _invitation_state(inv)
    if state != "pending":
        return {"valid": False, "reason": state, "invitation_id": inv.id}
    org = db.get(Organization, inv.organization_id)
    return {
        "valid": True,
        "invitation_id": inv.id,
        "organization_id": inv.organization_id,
        "organization_name": org.name if org else None,
        "invited_role": inv.invited_role,
        "invited_data_scope": inv.invited_data_scope,
        "invited_email": inv.invited_email,
        # True when a one-time code was actually issued for this invite, so the
        # acceptance UI knows to collect it. Derived from stored state, not config.
        "requires_verification": inv.verification_code_hash is not None,
    }


def revoke_invitation(
    db: Session, invitation_id: int, actor: Optional[str] = None
) -> Optional[Invitation]:
    inv = db.get(Invitation, invitation_id)
    if not inv:
        return None
    if inv.status == "pending":
        inv.status = "revoked"
        db.flush()
        audit_service.log(
            db, entity_type="invitation", entity_id=inv.id, action="invite_revoked",
            changed_by=actor,
        )
        db.flush()
    return inv


def list_invitations(db: Session, organization_id: int) -> list[Invitation]:
    rows = list(
        db.execute(
            select(Invitation)
            .where(Invitation.organization_id == organization_id)
            .order_by(Invitation.id.desc())
        ).scalars().all()
    )
    return rows


def accept_invitation(
    db: Session,
    *,
    raw_token: str,
    username: str,
    password: Optional[str] = None,
    full_name: Optional[str] = None,
    email: Optional[str] = None,
    verification_code: Optional[str] = None,
) -> dict:
    """Accept an invite: create/link an AppUser + OrganizationMember.

    Returns ``{"ok": True, "member_id": ..., "username": ...}`` on success or
    ``{"ok": False, "reason": ...}``. Expired/revoked/over-max-uses invites are
    rejected server-side. When the invite carries an ``invited_email`` the
    acceptance is BOUND to that address (case-insensitive, trimmed); a mismatch
    is rejected with ``email_mismatch``. A config-gated one-time code adds a
    second factor. Audit-logged.
    """
    inv = find_invitation_by_token(db, raw_token)
    if not inv:
        return {"ok": False, "reason": "not_found"}
    state = _invitation_state(inv)
    if state != "pending":
        return {"ok": False, "reason": state}

    username = (username or "").strip()
    if not username:
        return {"ok": False, "reason": "username_required"}

    # --- Email binding: when the invite names an address, acceptance MUST match
    # it server-side (it is no longer merely informational). ---
    invited_email = (inv.invited_email or "").strip().lower()
    email_verified = False
    if invited_email:
        provided_email = (email or "").strip().lower()
        if provided_email != invited_email:
            return {"ok": False, "reason": "email_mismatch"}
        # Second factor: only enforced when a code was actually minted+sent.
        if inv.verification_code_hash:
            if not verification_code:
                return {"ok": False, "reason": "verification_required"}
            if _hash_token(verification_code.strip()) != inv.verification_code_hash:
                return {"ok": False, "reason": "invalid_code"}
            email_verified = True

    user = auth_service.get_user(db, username)
    if user is None:
        if not password:
            return {"ok": False, "reason": "password_required"}
        user = AppUser(
            username=username,
            password_hash=auth_service.hash_password(password),
            full_name=full_name or username.title(),
            role="agronomist",  # web role label; org role lives on the membership
            is_demo=False,
            organization_id=inv.organization_id,
            email=inv.invited_email or (email or None),
            email_verified=email_verified,
        )
        db.add(user)
        db.flush()

    existing = get_membership(db, user.id, organization_id=inv.organization_id)
    if existing:
        return {"ok": False, "reason": "already_member", "member_id": existing.id}

    member = create_member(
        db,
        organization_id=inv.organization_id,
        app_user_id=user.id,
        role=inv.invited_role,
        permission_overrides=inv.invited_permissions,
        data_scope=inv.invited_data_scope,
        scope_assignee_emails=[inv.invited_email] if inv.invited_email else None,
        actor=username,
    )

    inv.used_count += 1
    inv.used_at = _now()
    inv.accepted_by_user_id = user.id
    if inv.used_count >= inv.max_uses:
        inv.status = "accepted"
    db.flush()
    audit_service.log(
        db, entity_type="invitation", entity_id=inv.id, action="invite_accepted",
        new_values={"username": username, "member_id": member.id,
                    "email_bound": bool(invited_email),
                    "email_verified": email_verified},
        changed_by=username,
    )
    db.flush()
    return {"ok": True, "member_id": member.id, "username": username,
            "organization_id": inv.organization_id, "role": member.role}
