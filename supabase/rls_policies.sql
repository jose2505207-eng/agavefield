-- =============================================================================
-- Agave Field — Supabase PostgreSQL Row-Level Security (RLS)
-- DEFENSE IN DEPTH — opt-in, standalone artifact. NOT an Alembic migration.
-- =============================================================================
--
-- WHAT THIS IS
-- ------------
-- A NON-DESTRUCTIVE, idempotent SQL artifact that enables Postgres Row-Level
-- Security on the tenant-scoped tables and isolates rows by `organization_id`
-- (and, as closely as RLS reasonably can, by the per-member `data_scope`
-- tiers self/team/ranch/organization).
--
-- It is a SECOND fence *behind* the authoritative app-layer enforcement
-- (`app/services/rbac_service.py` scope filtering + the read-only middleware
-- guards in `app/main.py`). It is NOT a replacement for them. If the app layer
-- were bypassed, these policies would still keep one org from reading/writing
-- another org's rows — provided the connection is NOT the Supabase service role
-- (see "SERVICE ROLE BYPASS" below).
--
-- WHAT THIS IS NOT
-- ----------------
-- * NOT a schema migration. It never CREATEs/DROPs/ALTERs a table or column.
--   Alembic (`alembic/versions/`, head `b4b8620239bc`) stays the single source
--   of truth for the schema. This file only touches POLICIES + helper FUNCTIONS
--   and toggles ENABLE ROW LEVEL SECURITY.
-- * NOT wired into the app connection lifecycle yet. It is OPT-IN: nothing sets
--   the session GUCs described below until we choose to thread them through the
--   SQLAlchemy connection/transaction. Until then, applying this file with the
--   app connecting as the table owner or service role is a no-op at runtime
--   (RLS is bypassed) — safe to install ahead of wiring.
--
-- SAFE TO RUN twice, against an empty schema, or against the live schema:
-- every table touch is guarded by to_regclass(); every policy is drop-if-exists
-- then create; every function is CREATE OR REPLACE. No data is read, mutated,
-- or deleted by running this file.
--
-- =============================================================================
-- GUC CONTRACT — what the FastAPI layer MUST set per connection/transaction
-- =============================================================================
-- Because this app authenticates in the FastAPI service layer (custom
-- AppUser/session tokens), NOT via Supabase Auth JWTs, the policies read the
-- tenant context from session-local GUCs (Grand Unified Configuration settings)
-- that the app sets right after checking out a connection, inside the request's
-- transaction. `current_setting(name, true)` returns NULL (missing_ok) when a
-- GUC is unset, and every policy FAILS CLOSED (denies) when `app.current_org_id`
-- is absent.
--
--   app.current_org_id              -> integer  the resolved tenant (member.organization_id)
--   app.current_app_user_id         -> integer  the resolved AppUser id (informational)
--   app.current_data_scope          -> text     'self' | 'team' | 'ranch' | 'organization'
--   app.current_scope_ranch_ids     -> text     CSV of farm ids     e.g. '3,7,12'
--   app.current_scope_lot_ids       -> text     CSV of lot ids      e.g. '44,45'
--   app.current_scope_assignee_emails -> text   CSV of WO emails    e.g. 'a@x.com,b@x.com'
--
-- These mirror OrganizationMember.{organization_id, data_scope, scope_ranch_ids,
-- scope_lot_ids, scope_assignee_emails} resolved by rbac_service. The CSV shape
-- keeps it to plain string GUCs (no arrays/JSON in settings).
--
-- HOW FastAPI WOULD SET THEM (sketch — NOT yet wired):
--
--   # transaction-local (reset automatically at COMMIT/ROLLBACK)
--   session.execute(text("SELECT set_config('app.current_org_id', :v, true)"),
--                   {"v": str(member.organization_id)})
--   session.execute(text("SELECT set_config('app.current_data_scope', :v, true)"),
--                   {"v": member.data_scope})
--   session.execute(text("SELECT set_config('app.current_scope_ranch_ids', :v, true)"),
--                   {"v": ",".join(map(str, member.scope_ranch_ids or []))})
--   # ...same for lot_ids and assignee_emails...
--
-- Use `is_local => true` (3rd arg) so the setting lives only for the current
-- transaction and cannot leak across pooled connections. Do this at the START
-- of every request transaction, from the resolved membership.
--
-- =============================================================================
-- SERVICE ROLE BYPASS (critical caveat)
-- =============================================================================
-- * The Supabase **service role** key has the BYPASSRLS attribute: connections
--   using it IGNORE every policy here. The FastAPI backend today typically holds
--   a privileged/service connection, so RLS would NOT take effect until the app
--   connects as a NON-bypassing role (or we FORCE it — see below). Treat RLS as
--   protection for *non-service* paths and as depth behind the app guards.
-- * A table's OWNER also bypasses RLS unless the table is set to FORCE ROW LEVEL
--   SECURITY. `ALTER TABLE ... FORCE ROW LEVEL SECURITY;` would close that gap,
--   but it is intentionally LEFT OUT here (kept as an opt-in note) so this file
--   stays "policies only" and cannot lock out the owner/service migrations that
--   Alembic and Supabase rely on. Enable FORCE deliberately, per table, only
--   once the app connects as a dedicated least-privilege role.
--
-- WARNING: RLS is defense-in-depth, not the primary control. Keep the
-- app/service-layer scope filtering and read-only guards authoritative.
-- =============================================================================

-- Bodies of functions that reference tenant tables are validated at run time,
-- not at CREATE time, so this file also installs cleanly on an empty schema.
set check_function_bodies = off;

-- --------------------------------------------------------------------------- --
-- 1. Session-context accessors (read the GUCs; fail closed on absence)
-- --------------------------------------------------------------------------- --
create or replace function agave_current_org_id() returns integer
  language sql stable as $$
  select nullif(current_setting('app.current_org_id', true), '')::integer
$$;

create or replace function agave_current_app_user_id() returns integer
  language sql stable as $$
  select nullif(current_setting('app.current_app_user_id', true), '')::integer
$$;

create or replace function agave_current_data_scope() returns text
  language sql stable as $$
  -- Default to the most restrictive-but-safe tenant-wide read only when a scope
  -- is not supplied; org isolation still applies via agave_current_org_id().
  select coalesce(nullif(current_setting('app.current_data_scope', true), ''),
                  'organization')
$$;

create or replace function agave_current_scope_ranch_ids() returns integer[]
  language sql stable as $$
  select case
    when coalesce(current_setting('app.current_scope_ranch_ids', true), '') = ''
      then array[]::integer[]
    else array(
      select trim(x)::integer
      from unnest(string_to_array(
             current_setting('app.current_scope_ranch_ids', true), ',')) as x
      where trim(x) <> ''
    )
  end
$$;

create or replace function agave_current_scope_lot_ids() returns integer[]
  language sql stable as $$
  select case
    when coalesce(current_setting('app.current_scope_lot_ids', true), '') = ''
      then array[]::integer[]
    else array(
      select trim(x)::integer
      from unnest(string_to_array(
             current_setting('app.current_scope_lot_ids', true), ',')) as x
      where trim(x) <> ''
    )
  end
$$;

create or replace function agave_current_scope_emails() returns text[]
  language sql stable as $$
  select case
    when coalesce(current_setting('app.current_scope_assignee_emails', true), '') = ''
      then array[]::text[]
    else array(
      select trim(x)
      from unnest(string_to_array(
             current_setting('app.current_scope_assignee_emails', true), ',')) as x
      where trim(x) <> ''
    )
  end
$$;

-- --------------------------------------------------------------------------- --
-- 2. Row-visibility predicates (encapsulate org isolation + data_scope tiers)
--    plpgsql so their table references are resolved at run time.
-- --------------------------------------------------------------------------- --
-- A work order is visible when (a) a tenant context is set, (b) the row belongs
-- to that org (legacy NULL-org rows stay visible, mirroring the app layer), and
-- (c) the row satisfies the member's data_scope tier:
--   organization -> every row in the org
--   ranch        -> field_id (farm) in the scope ranch ids
--   team         -> ranch OR lot OR assignee-email match
--   self         -> assignee-email match only
create or replace function agave_work_order_visible(p_work_order_id integer)
  returns boolean language plpgsql stable as $$
declare
  v_ctx_org  integer := agave_current_org_id();
  v_scope    text    := agave_current_data_scope();
  v_row_org  integer;
  v_field    integer;
  v_lot      integer;
  v_email    text;
begin
  -- Fail closed: no tenant context => deny.
  if v_ctx_org is null then
    return false;
  end if;

  select organization_id, field_id, lot_id, assigned_to_email
    into v_row_org, v_field, v_lot, v_email
    from public.work_orders
   where id = p_work_order_id;

  if not found then
    return false;
  end if;

  -- Org isolation (NULL-org == legacy/single-tenant, visible for BC).
  if not (v_row_org = v_ctx_org or v_row_org is null) then
    return false;
  end if;

  -- data_scope tiers.  `x = any(array)` is NULL (=> not-true => deny) when x is
  -- NULL, which is the desired conservative behavior.
  if v_scope = 'organization' then
    return true;
  elsif v_scope = 'ranch' then
    return v_field = any (agave_current_scope_ranch_ids());
  elsif v_scope = 'team' then
    return v_field = any (agave_current_scope_ranch_ids())
        or v_lot   = any (agave_current_scope_lot_ids())
        or v_email = any (agave_current_scope_emails());
  elsif v_scope = 'self' then
    return v_email = any (agave_current_scope_emails());
  end if;

  return false;
end
$$;

-- An execution record (and its reviews) inherits visibility from its work order.
create or replace function agave_execution_visible(p_execution_record_id integer)
  returns boolean language plpgsql stable as $$
declare
  v_wo integer;
begin
  select work_order_id into v_wo
    from public.execution_records
   where id = p_execution_record_id;
  if not found then
    return false;
  end if;
  return agave_work_order_visible(v_wo);
end
$$;

-- --------------------------------------------------------------------------- --
-- 3. Idempotent policy applicator (guards missing tables; drop-then-create)
-- --------------------------------------------------------------------------- --
create or replace function agave_rls_apply(
  p_table  text,
  p_policy text,
  p_cmd    text,   -- 'SELECT' | 'INSERT' | 'UPDATE'
  p_using  text,   -- USING expression (NULL for INSERT)
  p_check  text    -- WITH CHECK expression (NULL to omit)
) returns void language plpgsql as $$
begin
  if to_regclass('public.' || p_table) is null then
    raise notice 'agave_rls: table public.% absent, skipping policy %', p_table, p_policy;
    return;
  end if;

  execute format('alter table public.%I enable row level security', p_table);
  execute format('drop policy if exists %I on public.%I', p_policy, p_table);

  if upper(p_cmd) = 'INSERT' then
    execute format('create policy %I on public.%I for insert with check (%s)',
                   p_policy, p_table, coalesce(p_check, 'true'));
  elsif p_check is null then
    execute format('create policy %I on public.%I for %s using (%s)',
                   p_policy, p_table, p_cmd, p_using);
  else
    execute format('create policy %I on public.%I for %s using (%s) with check (%s)',
                   p_policy, p_table, p_cmd, p_using, p_check);
  end if;
end
$$;

-- --------------------------------------------------------------------------- --
-- 4. Apply policies to the tenant tables
--    Policies apply to PUBLIC (all roles). Supabase service_role BYPASSes RLS;
--    table owners bypass unless FORCE ROW LEVEL SECURITY (intentionally omitted).
-- --------------------------------------------------------------------------- --
do $$
begin
  -- ---- work_orders (direct organization_id) -------------------------------
  perform agave_rls_apply('work_orders', 'agave_wo_select', 'SELECT',
    'agave_work_order_visible(id)', null);
  perform agave_rls_apply('work_orders', 'agave_wo_insert', 'INSERT',
    null,
    'agave_current_org_id() is not null '
    'and (organization_id = agave_current_org_id() or organization_id is null)');
  perform agave_rls_apply('work_orders', 'agave_wo_update', 'UPDATE',
    'agave_work_order_visible(id)',
    -- Check on the org column directly (a self-referential visibility lookup
    -- during UPDATE would read the pre-image); still enforces tenant ownership.
    'organization_id = agave_current_org_id() or organization_id is null');

  -- ---- work_order_items (via parent work order) ---------------------------
  perform agave_rls_apply('work_order_items', 'agave_woi_select', 'SELECT',
    'agave_work_order_visible(work_order_id)', null);
  perform agave_rls_apply('work_order_items', 'agave_woi_insert', 'INSERT',
    null, 'agave_work_order_visible(work_order_id)');
  perform agave_rls_apply('work_order_items', 'agave_woi_update', 'UPDATE',
    'agave_work_order_visible(work_order_id)',
    'agave_work_order_visible(work_order_id)');

  -- ---- execution_records (via parent work order) --------------------------
  perform agave_rls_apply('execution_records', 'agave_exec_select', 'SELECT',
    'agave_work_order_visible(work_order_id)', null);
  perform agave_rls_apply('execution_records', 'agave_exec_insert', 'INSERT',
    null, 'agave_work_order_visible(work_order_id)');
  perform agave_rls_apply('execution_records', 'agave_exec_update', 'UPDATE',
    'agave_work_order_visible(work_order_id)',
    'agave_work_order_visible(work_order_id)');

  -- ---- photo_evidence (via parent work order) -----------------------------
  perform agave_rls_apply('photo_evidence', 'agave_photo_select', 'SELECT',
    'agave_work_order_visible(work_order_id)', null);
  perform agave_rls_apply('photo_evidence', 'agave_photo_insert', 'INSERT',
    null, 'agave_work_order_visible(work_order_id)');
  perform agave_rls_apply('photo_evidence', 'agave_photo_update', 'UPDATE',
    'agave_work_order_visible(work_order_id)',
    'agave_work_order_visible(work_order_id)');

  -- ---- reviews (via parent execution record) ------------------------------
  perform agave_rls_apply('reviews', 'agave_review_select', 'SELECT',
    'agave_execution_visible(execution_record_id)', null);
  perform agave_rls_apply('reviews', 'agave_review_insert', 'INSERT',
    null, 'agave_execution_visible(execution_record_id)');
  perform agave_rls_apply('reviews', 'agave_review_update', 'UPDATE',
    'agave_execution_visible(execution_record_id)',
    'agave_execution_visible(execution_record_id)');

  -- ---- organizations (own tenant row only) --------------------------------
  -- SELECT + UPDATE isolate to the current tenant. INSERT (creating a NEW org)
  -- is deliberately NOT granted a policy: with RLS enabled and no INSERT policy,
  -- non-service roles cannot create orgs — tenant creation is a service-role /
  -- bootstrap operation. This never blocks Alembic (owner) or the service key.
  perform agave_rls_apply('organizations', 'agave_org_select', 'SELECT',
    'id = agave_current_org_id()', null);
  perform agave_rls_apply('organizations', 'agave_org_update', 'UPDATE',
    'id = agave_current_org_id()', 'id = agave_current_org_id()');

  -- ---- organization_members (own tenant only) -----------------------------
  perform agave_rls_apply('organization_members', 'agave_member_select', 'SELECT',
    'organization_id = agave_current_org_id()', null);
  perform agave_rls_apply('organization_members', 'agave_member_insert', 'INSERT',
    null, 'organization_id = agave_current_org_id()');
  perform agave_rls_apply('organization_members', 'agave_member_update', 'UPDATE',
    'organization_id = agave_current_org_id()',
    'organization_id = agave_current_org_id()');

  -- ---- invitations (own tenant only) --------------------------------------
  perform agave_rls_apply('invitations', 'agave_invite_select', 'SELECT',
    'organization_id = agave_current_org_id()', null);
  perform agave_rls_apply('invitations', 'agave_invite_insert', 'INSERT',
    null, 'organization_id = agave_current_org_id()');
  perform agave_rls_apply('invitations', 'agave_invite_update', 'UPDATE',
    'organization_id = agave_current_org_id()',
    'organization_id = agave_current_org_id()');

  -- ---- app_users (home-org fast path; NULL home-org tolerated) -------------
  -- NOTE: app_users.organization_id is only the "home org" pointer; a person may
  -- belong to several orgs via organization_members. This policy is a coarse
  -- home-org fence. Cross-org login resolution must remain a service-role path.
  perform agave_rls_apply('app_users', 'agave_appuser_select', 'SELECT',
    'organization_id = agave_current_org_id() or organization_id is null', null);
  perform agave_rls_apply('app_users', 'agave_appuser_update', 'UPDATE',
    'organization_id = agave_current_org_id() or organization_id is null',
    'organization_id = agave_current_org_id() or organization_id is null');
end
$$;

-- NOTE ON TABLES INTENTIONALLY LEFT WITHOUT RLS HERE:
--   ops_weather_snapshots, timeline_events, audit_logs — these are cross-cutting
--   / shared and carry no organization_id nor a reliable single work-order link.
--   Scoping them safely needs schema work (an org column threaded via Alembic)
--   and is out of scope for this policies-only artifact. They remain governed by
--   the app layer. Add them here once they carry a tenant key.

-- Reversible: run supabase/rls_rollback.sql to disable all of the above.
