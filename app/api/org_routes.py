"""Organization, membership, and invitation endpoints (session-authenticated).

Mounted WITHOUT the API-key RBAC dependency: these authenticate the human by
their signed session token (see ``app/api/rbac.py``). Write actions are
additionally subject to the demo read-only guard and the member read-only guard
in ``app.main``.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.rbac import current_membership, current_user, require_permission
from app.config import settings
from app.db import get_db
from app.models.operations import (
    AppUser,
    Invitation,
    Organization,
    OrganizationMember,
)
from app.models.rbac_schemas import (
    ContextOut,
    InvitationAccept,
    InvitationCreate,
    InvitationCreated,
    InvitationRead,
    InvitationValidateOut,
    MemberUpdate,
    MemberWithUser,
)
from app.services import auth_service, rbac_service

router = APIRouter(prefix="/api/org", tags=["organization"])


def _member_with_user(db: Session, member: OrganizationMember) -> MemberWithUser:
    user = db.get(AppUser, member.app_user_id)
    out = MemberWithUser.model_validate(member)
    if user:
        out.username = user.username
        out.full_name = user.full_name
    return out


def can_view_roster(member: OrganizationMember = Depends(current_membership)) -> OrganizationMember:
    """Viewing the roster needs member-management OR invite rights (admins +
    supervisors). Workers/auditors get 403."""
    if not (
        rbac_service.has_permission(member, "can_manage_members")
        or rbac_service.has_permission(member, "can_invite_members")
    ):
        raise HTTPException(403, "Requires member management or invite permission")
    return member


# --------------------------------------------------------------------------- #
# Resolved context — drives the data-driven frontend
# --------------------------------------------------------------------------- #
@router.get("/context", response_model=ContextOut)
def get_context(
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    member = rbac_service.get_current_membership(db, user)
    if member:
        perms = rbac_service.permission_dict(member)
        org: Optional[Organization] = db.get(Organization, member.organization_id)
        dashboard = rbac_service.dashboard_config(member)
    else:
        # No membership: derive a sensible profile from the legacy web role so
        # existing admins keep full access (see rbac_service.fallback_role_for_user).
        fallback_role = rbac_service.fallback_role_for_user(user)
        perms = rbac_service.resolve_permissions(fallback_role)
        org = None
        dashboard = rbac_service.dashboard_config(
            role=fallback_role, permissions=perms, data_scope="organization"
        )
    return {
        "user": auth_service.public_user(user),
        "has_membership": member is not None,
        "organization": org,
        "member": member,
        "permissions": perms,
        "dashboard": dashboard,
    }


# --------------------------------------------------------------------------- #
# Members
# --------------------------------------------------------------------------- #
@router.get("/members", response_model=list[MemberWithUser])
def list_members(
    acting: OrganizationMember = Depends(can_view_roster),
    db: Session = Depends(get_db),
):
    rows = rbac_service.list_members(db, acting.organization_id)
    return [_member_with_user(db, m) for m in rows]


@router.patch("/members/{member_id}", response_model=MemberWithUser)
def update_member(
    member_id: int,
    payload: MemberUpdate,
    acting: OrganizationMember = Depends(require_permission("can_manage_members")),
    db: Session = Depends(get_db),
):
    existing = db.get(OrganizationMember, member_id)
    if not existing or existing.organization_id != acting.organization_id:
        raise HTTPException(404, "Member not found")
    actor = _actor_name(db, acting)
    member = rbac_service.update_member(
        db,
        member_id,
        role=payload.role.value if payload.role else None,
        permission_overrides=payload.permissions.model_dump(exclude_none=True)
        if payload.permissions
        else None,
        data_scope=payload.data_scope.value if payload.data_scope else None,
        scope_ranch_ids=payload.scope_ranch_ids,
        scope_lot_ids=payload.scope_lot_ids,
        scope_assignee_emails=payload.scope_assignee_emails,
        actor=actor,
    )
    db.commit()
    db.refresh(member)
    return _member_with_user(db, member)


@router.post("/members/{member_id}/deactivate", response_model=MemberWithUser)
def deactivate_member(
    member_id: int,
    acting: OrganizationMember = Depends(require_permission("can_manage_members")),
    db: Session = Depends(get_db),
):
    existing = db.get(OrganizationMember, member_id)
    if not existing or existing.organization_id != acting.organization_id:
        raise HTTPException(404, "Member not found")
    member = rbac_service.deactivate_member(db, member_id, actor=_actor_name(db, acting))
    db.commit()
    db.refresh(member)
    return _member_with_user(db, member)


# --------------------------------------------------------------------------- #
# Invitations
# --------------------------------------------------------------------------- #
@router.get("/invitations", response_model=list[InvitationRead])
def list_invitations(
    acting: OrganizationMember = Depends(require_permission("can_invite_members")),
    db: Session = Depends(get_db),
):
    return rbac_service.list_invitations(db, acting.organization_id)


@router.post("/invitations", response_model=InvitationCreated, status_code=201)
def create_invitation(
    payload: InvitationCreate,
    acting: OrganizationMember = Depends(require_permission("can_invite_members")),
    db: Session = Depends(get_db),
):
    actor_user = db.get(AppUser, acting.app_user_id)
    expires_at = rbac_service._now() + timedelta(days=payload.expires_in_days)
    inv, raw_token = rbac_service.create_invitation(
        db,
        organization_id=acting.organization_id,
        invited_role=payload.invited_role.value,
        invited_permissions=payload.permissions.model_dump(exclude_none=True)
        if payload.permissions
        else None,
        invited_data_scope=payload.data_scope.value if payload.data_scope else None,
        invited_email=payload.invited_email,
        expires_at=expires_at,
        max_uses=payload.max_uses,
        created_by_user_id=actor_user.id if actor_user else None,
        actor=actor_user.username if actor_user else None,
    )
    db.commit()
    db.refresh(inv)
    return InvitationCreated(
        **InvitationRead.model_validate(inv).model_dump(),
        token=raw_token,
        accept_url=f"{settings.app_base_url.rstrip('/')}/invite/{raw_token}",
    )


@router.post("/invitations/{invitation_id}/revoke", response_model=InvitationRead)
def revoke_invitation(
    invitation_id: int,
    acting: OrganizationMember = Depends(require_permission("can_invite_members")),
    db: Session = Depends(get_db),
):
    existing = db.get(Invitation, invitation_id)
    if not existing or existing.organization_id != acting.organization_id:
        raise HTTPException(404, "Invitation not found")
    inv = rbac_service.revoke_invitation(db, invitation_id, actor=_actor_name(db, acting))
    db.commit()
    db.refresh(inv)
    return inv


@router.get("/invitations/validate/{token}", response_model=InvitationValidateOut)
def validate_invitation(token: str, db: Session = Depends(get_db)):
    """Public: inspect an invite token before accepting (no auth required)."""
    return rbac_service.validate_invitation(db, token)


@router.post("/invitations/accept")
def accept_invitation(payload: InvitationAccept, db: Session = Depends(get_db)):
    """Public: accept an invite, creating/linking an AppUser + membership."""
    result = rbac_service.accept_invitation(
        db,
        raw_token=payload.token,
        username=payload.username,
        password=payload.password,
        full_name=payload.full_name,
        email=payload.email,
        verification_code=payload.verification_code,
    )
    if not result.get("ok"):
        reason = result.get("reason", "invalid")
        status = 404 if reason == "not_found" else 400
        raise HTTPException(status, f"Invitation cannot be accepted: {reason}")
    db.commit()
    return result


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _actor_name(db: Session, member: OrganizationMember) -> Optional[str]:
    user = db.get(AppUser, member.app_user_id)
    return user.username if user else None
