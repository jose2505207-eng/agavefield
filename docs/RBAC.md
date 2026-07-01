# Organization RBAC — Roles, Permissions & Data Scope

Multi-user profile + organization access-control layer for Agave Field. Roles,
permissions, and **data visibility** are enforced **server-side** in the FastAPI
services and middleware — the frontend only *renders* what the backend resolves.

Migration head introducing this layer: **`b4b8620239bc`**
(`add organizations, members, invitations (RBAC)`), on top of `b2c3d4e5f6a7`.
Baseline remains `49fa233d5c67`. Run `python -m alembic upgrade head`.

---

## 1. Domain model (additive)

New tables (`app/models/operations.py`):

- **`organizations`** — a tenant (`id, name, slug, description, is_active`).
- **`organization_members`** — links an `AppUser` to an `Organization` with a
  `role`, the ten **normalized permission booleans**, a `data_scope`, JSON
  scope-ref lists (`scope_ranch_ids`, `scope_lot_ids`, `scope_assignee_emails`),
  and `is_active`.
- **`invitations`** — tokenized join links (`token_hash` only is stored), with
  `invited_role/permissions/data_scope`, `expires_at`, `max_uses`, `used_count`,
  `status` (`pending|accepted|expired|revoked`).

New nullable columns: `app_users.organization_id` (home-org fast path) and
`work_orders.organization_id` (tenant ownership; `NULL` = legacy/single-tenant).
Both are plain indexed Integers (SQLite-safe, additive), mirroring `season_id`.

> **Two user tables, unchanged:** observation-layer `users` (Telegram) vs login
> `app_users`. RBAC uses **`app_users` only**. Field workers still complete work
> via per-work-order tokens, not accounts.

## 2. Roles & default permission templates

`role` seeds a **default** permission set (`rbac_service.ROLE_TEMPLATES`), but
permissions are stored per-member and may be **overridden independently** — all
checks read the stored booleans, never the role string.

| Permission \ Role        | worker | supervisor | engineer | admin | auditor |
|--------------------------|:------:|:----------:|:--------:|:-----:|:-------:|
| can_invite_members       |        |     ✅     |          |  ✅   |         |
| can_create_work_orders   |        |     ✅     |    ✅    |  ✅   |         |
| can_assign_work_orders   |        |     ✅     |    ✅    |  ✅   |         |
| can_review_work_orders   |        |            |    ✅    |  ✅   |         |
| can_manage_catalogs      |        |            |    ✅    |  ✅   |         |
| can_view_reports         |        |     ✅     |    ✅    |  ✅   |   ✅    |
| can_view_labor_analytics |        |            |    ✅    |  ✅   |   ✅    |
| can_manage_org_settings  |        |            |          |  ✅   |         |
| can_manage_members       |        |            |          |  ✅   |         |
| can_export_data          |        |            |    ✅    |  ✅   |   ✅    |
| **default data_scope**   |  self  |    team    |   org    |  org  |   org   |

**Override examples** (all real): an *engineer who may review but not invite*
(default); an *engineer granted `can_manage_org_settings`*; a *supervisor who can
invite workers but not manage org settings* (default); an *auditor who can export
but not edit* (default — read-only). Effective set is computed by
`rbac_service.resolve_permissions(role, overrides)`.

## 3. Data scope (row visibility)

`rbac_service.filter_work_orders_by_scope(member, rows, is_demo)` and
`filter_executions_by_scope(...)` run at the route boundary so the API **never
returns out-of-scope rows**, even if a client crafts the request directly.

- **self** — only work orders whose `assigned_to_email` ∈ the member's
  `scope_assignee_emails` (a worker sees only their own work).
- **team** — ranch ∈ `scope_ranch_ids`, or lot ∈ `scope_lot_ids`, or assignee ∈
  `scope_assignee_emails`.
- **ranch** — ranch ∈ `scope_ranch_ids`.
- **organization** — every row in the org.

**Org isolation:** non-demo members see their org's rows **plus** legacy
`NULL`-org rows (backward compatible); demo members are confined to their org.
No membership resolved (open / API-key mode, existing tests) → **no filtering**,
preserving current behavior.

Wired into: `GET /api/work-orders`, `GET /api/executions` (via the
`scope_context` dependency, which reads the session Bearer token).

## 4. Server-side enforcement (authoritative)

Three independent guards, all server-side:

1. **API-key RBAC** (`app/api/auth.py`) — unchanged; gates legacy ops endpoints.
2. **Demo read-only guard** (`app.main`) — any non-GET with a demo Bearer → 403
   (except `/api/auth/*`). Unchanged.
3. **Member read-only guard** (`app.main`, new) — the authoritative twin of the
   demo guard: a session whose membership holds **no write-capable permission**
   (auditor, bare worker) is refused on any non-GET (except `/api/auth/*` and
   the public `/api/org/invitations/accept`). This makes **auditor read-only**
   real across the whole API, not just the org endpoints.

Permission gating on the org endpoints uses
`app/api/rbac.py::require_permission(...)`.

### Backend helper map (the requested helpers, as service functions)

| Requested helper            | Implementation |
|-----------------------------|----------------|
| `getCurrentUser`            | `auth_service.user_from_token` |
| `getCurrentMembership`      | `rbac_service.get_current_membership` |
| `hasPermission`             | `rbac_service.has_permission` |
| `canAccessWorkOrder`        | `rbac_service.can_access_work_order` |
| `canInviteMembers`          | `has_permission(m, "can_invite_members")` |
| `canViewLaborAnalytics`     | `has_permission(m, "can_view_labor_analytics")` |
| `getDashboardConfigForRole` | `rbac_service.dashboard_config` |
| `filterWorkOrdersByScope`   | `rbac_service.filter_work_orders_by_scope` |

`GET /api/org/context` returns the resolved `{user, membership, permissions,
dashboard}` so the frontend is **data-driven**, never hardcoded per role.

## 5. Invitation flow (end to end)

Endpoints (`app/api/org_routes.py`):

- `POST /api/org/invitations` — create (needs `can_invite_members`). Returns the
  raw token **once**; only its SHA-256 hash is stored (same scheme as work-order
  links). Includes an `accept_url`.
- `GET /api/org/invitations` — list (needs `can_invite_members`).
- `POST /api/org/invitations/{id}/revoke` — revoke.
- `GET /api/org/invitations/validate/{token}` — **public** pre-check.
- `POST /api/org/invitations/accept` — **public**; creates/links an `AppUser` +
  `OrganizationMember` with the invited role/permissions/scope, marks the invite
  used, writes an audit event.

Expired / revoked / over-`max_uses` invites are rejected **server-side**.
Frontend: `web/app/invite/[token]/page.tsx`.

Audit events (via `audit_service.log`, entity `organization_member` /
`invitation`): `member_created`, `role_changed`, `permissions_changed`,
`member_deactivated`, `invite_created`, `invite_accepted`, `invite_revoked`.

## 6. Demo profiles — how to test each locally

On startup a read-only demo org **"Hacienda Verde (Demo)"** is seeded
(`demo_seed_service.seed_demo_org`) with five accounts (password == username, all
`is_demo=True`):

| Login            | Member          | Role       | Sees |
|------------------|-----------------|------------|------|
| `DEMO` / `DEMO`  | Jose Admin      | admin      | everything (admin profile) |
| `DEMO_WORKER`    | Juan Martinez   | worker     | only his own assigned work |
| `DEMO_SUPERVISOR`| Ana Lopez       | supervisor | his team's field operations |
| `DEMO_ENGINEER`  | Ing. Camila Torres | engineer | labor & agronomic analytics |
| `DEMO_ADMIN`     | Jose Admin      | admin      | full organization control |
| `DEMO_AUDITOR`   | Compliance Viewer | auditor  | read-only compliance review |

**Local steps**

1. Backend: `uvicorn app.main:app --reload` (startup seeds the demo org).
2. Frontend: `cd web && npm run dev`, open `http://localhost:3000`.
3. Sign in with **`DEMO` / `DEMO`** → lands on the **Organization Control
   Center** (admin).
4. Use the **"Demo profile" switcher** (top-right, demo-only) to jump between the
   five profiles. Each switch re-authenticates as that demo account, so the
   dashboard, navigation, and permissions all change from the **backend-resolved**
   context — not a frontend toggle.
5. Verify enforcement: as `DEMO_AUDITOR` or `DEMO_WORKER`, the Members /
   Invitations nav items are hidden, and hitting the API directly returns 403.
   Any write attempt returns 403 (demo + read-only guards).

## 7. What is demo-only vs production-ready

**Production-ready (real, tested):**

- Models, migration, permission resolution (template + override).
- Server-side scope filtering on work orders + executions.
- The three enforcement guards (API-key, demo read-only, member read-only).
- Full invitation lifecycle incl. expiry/revoke/max-uses, hash-only token
  storage, audit logging.
- `/api/org/context` and the data-driven, permission-aware frontend.

**Demo-only / honestly stubbed:**

- The five **dashboard datasets** (work-order tables, labor/product/carbon
  panels) shown for demo accounts are **curated frontend data**
  (`web/lib/demo-rbac.ts`), clearly labelled "Demo data". Real accounts get live,
  scoped API data and honest empty states — never fabricated rows.
- We **do not** seed demo work-order/execution rows into the shared DB. This is
  deliberate: `organization_id` is not yet threaded through the *aggregate*
  endpoints (`/api/carbon/summary`, `/api/review-queue`, `/api/system/status`),
  so seeding demo rows would leak into those aggregates for real accounts. List
  endpoints (`/api/work-orders`, `/api/executions`) **are** scoped today.

## 8. Future work (true production auth / Supabase)

- **Real account signup** beyond invite acceptance (email verification, password
  reset). Today new accounts are created via invite acceptance only.
- **Email-bound invites** — currently `invited_email` is informational; binding
  acceptance to the invited address requires an email step.
- **Thread `organization_id` through aggregate endpoints** (carbon/review/status)
  so multi-tenant aggregates and demo rows are fully isolated; then demo work
  orders can be seeded live.
- **Wire RLS into the connection lifecycle** — the policies in §9 exist but are
  dormant; setting the session GUCs per request transaction (and connecting as a
  non-service role) is the remaining step to make them active.
- **Supabase Postgres RLS** — the server-side guards here are the application
  layer. RLS policies now **exist as an opt-in artifact**
  (`supabase/rls_policies.sql`, reversible via `supabase/rls_rollback.sql`) — see
  §9 — but are **not yet wired** into the app connection lifecycle: nothing sets
  the required session GUCs today, so they are dormant until we thread them
  through the SQLAlchemy connection. Until wired, enforcement remains at the
  API/service layer described above.

## 9. Row-Level Security (defense in depth)

A standalone, reviewable **RLS artifact** now ships alongside the app-layer
guards as a second fence at the database:

- `supabase/rls_policies.sql` — enables RLS and defines `SELECT/INSERT/UPDATE`
  policies isolating rows by tenant.
- `supabase/rls_rollback.sql` — fully reverses it (drops policies, disables RLS,
  drops the helper functions). Both are **idempotent and non-destructive**: no
  table/column is ever created, altered, or dropped, and no data row is read or
  mutated. Safe to run twice, against an empty schema, or against the live one.

> **This is NOT an Alembic migration.** Alembic (head `b4b8620239bc`) stays the
> single source of truth for the schema; this file only touches **policies +
> helper functions** and toggles `ENABLE ROW LEVEL SECURITY`. It is
> **defense-in-depth behind** `rbac_service` scope filtering + the `app.main`
> read-only guards — **not** a replacement for them.

**Tables covered.** `work_orders` (direct `organization_id`); `work_order_items`,
`execution_records`, `photo_evidence` (isolated via their parent work order);
`reviews` (via the parent execution record); `organizations`,
`organization_members`, `invitations`, `app_users` (own-tenant only).
`ops_weather_snapshots`, `timeline_events`, `audit_logs` are **left uncovered**
on purpose — they carry no tenant key yet; scoping them needs schema work and
stays governed by the app layer.

**Data-scope tiers** are modelled as closely as RLS reasonably can, matching
`filter_work_orders_by_scope`: `organization` = all org rows; `ranch` = `field_id`
∈ scope ranch ids; `team` = ranch OR lot OR assignee-email match; `self` =
assignee-email match only. Legacy `NULL`-org work orders remain visible (BC),
mirroring the app.

**GUC contract (the app must set these per request transaction).** Because auth
lives in the FastAPI layer (custom AppUser/session tokens, **not** Supabase Auth
JWTs), the policies read tenant context from session-local GUCs. Every policy
**fails closed** (denies) when `app.current_org_id` is unset:

| GUC | Type | Source (`OrganizationMember` / resolved) |
|-----|------|------------------------------------------|
| `app.current_org_id` | integer | `organization_id` (the tenant) |
| `app.current_app_user_id` | integer | resolved `AppUser.id` (informational) |
| `app.current_data_scope` | text | `data_scope` (`self\|team\|ranch\|organization`) |
| `app.current_scope_ranch_ids` | text (CSV of ints) | `scope_ranch_ids` |
| `app.current_scope_lot_ids` | text (CSV of ints) | `scope_lot_ids` |
| `app.current_scope_assignee_emails` | text (CSV) | `scope_assignee_emails` |

The app would set them transaction-locally (`SELECT set_config(name, value,
true)`) at the start of each request transaction, from the resolved membership,
so they reset on `COMMIT/ROLLBACK` and never leak across pooled connections.
(Sketch is in the header of `rls_policies.sql`.)

**Service-role caveat.** The Supabase **service role** key has `BYPASSRLS`:
connections using it ignore every policy. A table **owner** also bypasses RLS
unless `FORCE ROW LEVEL SECURITY` is set — which this artifact **intentionally
omits** (to stay "policies only" and never lock out owner/service migrations).
So RLS takes effect only once the app connects as a **non-service, non-owner
role**; enabling `FORCE` per table is a deliberate later step.

**Apply / rollback.** Run against the Supabase Postgres DB (e.g. `psql
"$DATABASE_URL" -f supabase/rls_policies.sql`; rollback with
`supabase/rls_rollback.sql`). *This lane could not apply it to a live DB (no
credentials) — the artifact + docs are delivered for review; applying + wiring
the GUCs is the remaining opt-in step.*

**Status: OPT-IN, not yet wired.** Installed policies are dormant until the app
sets the GUCs and connects as a non-bypassing role. See §8 for the wiring
follow-up.
