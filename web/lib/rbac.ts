// RBAC types + helpers shared across the admin frontend. The resolved context
// (membership, permissions, dashboard config) is fetched from the backend
// (/api/org/context) so the UI is DATA-DRIVEN — never hardcoded per role.
//
// IMPORTANT: every permission gate here is COSMETIC. Real enforcement lives in
// the FastAPI services + middleware. The UI hides what a user can't do; the API
// refuses it regardless.

export const PERMISSION_KEYS = [
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
] as const;

export type PermissionKey = (typeof PERMISSION_KEYS)[number];
export type PermissionSet = Record<PermissionKey, boolean>;

export type OrgRole = "worker" | "supervisor" | "engineer" | "admin" | "auditor";
export type DataScope = "self" | "team" | "ranch" | "organization";

export interface NavItem {
  key: string;
  label: string;
  href: string;
}

export interface DashboardConfig {
  role: OrgRole;
  title: string;
  data_scope: DataScope;
  nav: NavItem[];
}

export interface Organization {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  is_active: boolean;
}

export interface Member {
  id: number;
  organization_id: number;
  app_user_id: number;
  role: OrgRole;
  data_scope: DataScope;
  is_active: boolean;
  username?: string | null;
  full_name?: string | null;
  scope_assignee_emails?: string[] | null;
  scope_ranch_ids?: number[] | null;
  scope_lot_ids?: number[] | null;
}

export interface OrgContext {
  user: { username: string; full_name?: string | null; role: string; is_demo: boolean };
  has_membership: boolean;
  organization?: Organization | null;
  member?: (Member & PermissionSet) | null;
  permissions: PermissionSet;
  dashboard: DashboardConfig;
}

export interface Invitation {
  id: number;
  organization_id: number;
  invited_email?: string | null;
  invited_role: OrgRole;
  invited_data_scope: DataScope;
  status: "pending" | "accepted" | "expired" | "revoked";
  max_uses: number;
  used_count: number;
  expires_at?: string | null;
  used_at?: string | null;
  created_at?: string | null;
  token?: string;
  accept_url?: string;
}

export const ROLE_LABELS: Record<OrgRole, string> = {
  worker: "Worker",
  supervisor: "Supervisor",
  engineer: "Engineer / Agronomist",
  admin: "Admin",
  auditor: "Auditor",
};

export const SCOPE_LABELS: Record<DataScope, string> = {
  self: "Own work only",
  team: "Their team / ranch",
  ranch: "Assigned ranch",
  organization: "Whole organization",
};

export const PERMISSION_LABELS: Record<PermissionKey, string> = {
  can_invite_members: "Invite members",
  can_create_work_orders: "Create work orders",
  can_assign_work_orders: "Assign work orders",
  can_review_work_orders: "Review & approve",
  can_manage_catalogs: "Manage catalogs",
  can_view_reports: "View reports",
  can_view_labor_analytics: "Labor analytics",
  can_manage_org_settings: "Org settings",
  can_manage_members: "Manage members",
  can_export_data: "Export data",
};

// Frontend mirror of the backend `rbac_service.ROLE_TEMPLATES` (see docs/RBAC.md
// §2). Used ONLY to PRE-FILL the invite/edit UI so an admin starts from the role
// default and can then override individual permissions. Enforcement stays
// server-side; these are cosmetic defaults. Keep in sync with the RBAC.md table.
function permsFrom(granted: PermissionKey[]): PermissionSet {
  return Object.fromEntries(
    PERMISSION_KEYS.map((k) => [k, granted.includes(k)]),
  ) as PermissionSet;
}

export const ROLE_PERMISSION_TEMPLATES: Record<OrgRole, PermissionSet> = {
  worker: permsFrom([]),
  supervisor: permsFrom([
    "can_invite_members",
    "can_create_work_orders",
    "can_assign_work_orders",
    "can_view_reports",
  ]),
  engineer: permsFrom([
    "can_create_work_orders",
    "can_assign_work_orders",
    "can_review_work_orders",
    "can_manage_catalogs",
    "can_view_reports",
    "can_view_labor_analytics",
    "can_export_data",
  ]),
  admin: permsFrom([...PERMISSION_KEYS]),
  auditor: permsFrom(["can_view_reports", "can_view_labor_analytics", "can_export_data"]),
};

export const ROLE_DEFAULT_SCOPE: Record<OrgRole, DataScope> = {
  worker: "self",
  supervisor: "team",
  engineer: "organization",
  admin: "organization",
  auditor: "organization",
};

// True when the given permission set diverges from the role's default template.
export function permsDivergeFromRole(role: OrgRole, perms: PermissionSet): boolean {
  const tpl = ROLE_PERMISSION_TEMPLATES[role];
  return PERMISSION_KEYS.some((k) => perms[k] !== tpl[k]);
}

export function hasPermission(ctx: OrgContext | null, perm: PermissionKey): boolean {
  return Boolean(ctx?.permissions?.[perm]);
}

// A guest fallback context used before the backend responds / when unauthenticated.
export function guestContext(
  user?: OrgContext["user"],
): OrgContext {
  const permissions = Object.fromEntries(
    PERMISSION_KEYS.map((k) => [k, false]),
  ) as PermissionSet;
  return {
    user: user || { username: "", role: "", is_demo: false },
    has_membership: false,
    organization: null,
    member: null,
    permissions,
    dashboard: {
      role: "worker",
      title: "My Field Work",
      data_scope: "self",
      nav: [
        { key: "dashboard", label: "Dashboard", href: "/" },
        { key: "settings", label: "Settings", href: "/settings" },
      ],
    },
  };
}

// ---- Demo-only profile switcher ----
// Each demo account is seeded server-side (read-only). Selecting one re-logs in
// as that account so the backend resolves a genuinely different membership.
export interface DemoProfile {
  username: string;
  name: string;
  role: OrgRole;
  blurb: string;
}

export const DEMO_PROFILES: DemoProfile[] = [
  { username: "DEMO_WORKER", name: "Juan Martinez", role: "worker",
    blurb: "Only his own assigned work" },
  { username: "DEMO_SUPERVISOR", name: "Ana Lopez", role: "supervisor",
    blurb: "His team's field operations" },
  { username: "DEMO_ENGINEER", name: "Ing. Camila Torres", role: "engineer",
    blurb: "Labor & agronomic analytics" },
  { username: "DEMO_ADMIN", name: "Jose Admin", role: "admin",
    blurb: "Full organization control" },
  { username: "DEMO_AUDITOR", name: "Compliance Viewer", role: "auditor",
    blurb: "Read-only compliance review" },
];
