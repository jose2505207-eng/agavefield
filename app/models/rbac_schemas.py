"""Pydantic v2 schemas for the organization RBAC layer."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OrgRole(str, Enum):
    worker = "worker"
    supervisor = "supervisor"
    engineer = "engineer"
    admin = "admin"
    auditor = "auditor"


class DataScope(str, Enum):
    self_ = "self"
    team = "team"
    ranch = "ranch"
    organization = "organization"


# --------------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------------- #
class PermissionSet(BaseModel):
    can_invite_members: bool = False
    can_create_work_orders: bool = False
    can_assign_work_orders: bool = False
    can_review_work_orders: bool = False
    can_manage_catalogs: bool = False
    can_view_reports: bool = False
    can_view_labor_analytics: bool = False
    can_manage_org_settings: bool = False
    can_manage_members: bool = False
    can_export_data: bool = False


class PermissionOverrides(BaseModel):
    """Sparse overrides — only the keys an admin wants to flip from the template."""
    can_invite_members: Optional[bool] = None
    can_create_work_orders: Optional[bool] = None
    can_assign_work_orders: Optional[bool] = None
    can_review_work_orders: Optional[bool] = None
    can_manage_catalogs: Optional[bool] = None
    can_view_reports: Optional[bool] = None
    can_view_labor_analytics: Optional[bool] = None
    can_manage_org_settings: Optional[bool] = None
    can_manage_members: Optional[bool] = None
    can_export_data: Optional[bool] = None


# --------------------------------------------------------------------------- #
# Organization / member reads
# --------------------------------------------------------------------------- #
class OrganizationRead(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class MemberRead(BaseModel):
    id: int
    organization_id: int
    app_user_id: int
    role: str
    data_scope: str
    is_active: bool
    can_invite_members: bool
    can_create_work_orders: bool
    can_assign_work_orders: bool
    can_review_work_orders: bool
    can_manage_catalogs: bool
    can_view_reports: bool
    can_view_labor_analytics: bool
    can_manage_org_settings: bool
    can_manage_members: bool
    can_export_data: bool
    scope_ranch_ids: Optional[list] = None
    scope_lot_ids: Optional[list] = None
    scope_assignee_emails: Optional[list] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MemberWithUser(MemberRead):
    username: Optional[str] = None
    full_name: Optional[str] = None


class MemberUpdate(BaseModel):
    role: Optional[OrgRole] = None
    permissions: Optional[PermissionOverrides] = None
    data_scope: Optional[DataScope] = None
    scope_ranch_ids: Optional[list[int]] = None
    scope_lot_ids: Optional[list[int]] = None
    scope_assignee_emails: Optional[list[str]] = None


# --------------------------------------------------------------------------- #
# Context (resolved membership + permissions + dashboard config)
# --------------------------------------------------------------------------- #
class ContextUser(BaseModel):
    username: str
    full_name: Optional[str] = None
    role: str
    is_demo: bool


class NavItemOut(BaseModel):
    key: str
    label: str
    href: str


class DashboardConfig(BaseModel):
    role: str
    title: str
    data_scope: str
    nav: list[NavItemOut]


class ContextOut(BaseModel):
    user: ContextUser
    has_membership: bool
    organization: Optional[OrganizationRead] = None
    member: Optional[MemberRead] = None
    permissions: PermissionSet
    dashboard: DashboardConfig


# --------------------------------------------------------------------------- #
# Invitations
# --------------------------------------------------------------------------- #
class InvitationCreate(BaseModel):
    invited_role: OrgRole = OrgRole.worker
    permissions: Optional[PermissionOverrides] = None
    data_scope: Optional[DataScope] = None
    invited_email: Optional[str] = None
    expires_in_days: int = Field(default=14, ge=1, le=365)
    max_uses: int = Field(default=1, ge=1, le=100)


class InvitationRead(BaseModel):
    id: int
    organization_id: int
    invited_email: Optional[str] = None
    invited_role: str
    invited_data_scope: str
    status: str
    max_uses: int
    used_count: int
    expires_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InvitationCreated(InvitationRead):
    token: str  # returned exactly once
    accept_url: Optional[str] = None


class InvitationValidateOut(BaseModel):
    valid: bool
    reason: Optional[str] = None
    invitation_id: Optional[int] = None
    organization_id: Optional[int] = None
    organization_name: Optional[str] = None
    invited_role: Optional[str] = None
    invited_data_scope: Optional[str] = None
    invited_email: Optional[str] = None
    requires_verification: bool = False


class InvitationAccept(BaseModel):
    token: str
    username: str
    password: Optional[str] = None
    full_name: Optional[str] = None
    # Email binding: when the invite names an address, acceptance must present a
    # matching email (enforced server-side). An optional one-time code is a
    # config-gated second factor.
    email: Optional[str] = None
    verification_code: Optional[str] = None
