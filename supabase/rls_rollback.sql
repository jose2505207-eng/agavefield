-- =============================================================================
-- Agave Field — RLS ROLLBACK (fully reverses supabase/rls_policies.sql)
-- =============================================================================
--
-- Drops every policy created by rls_policies.sql, DISABLEs Row-Level Security on
-- the affected tables, and drops the helper functions. Idempotent and
-- NON-DESTRUCTIVE: it never touches a table, column, or a single data row —
-- it only removes policies + functions and flips RLS off.
--
-- Safe to run twice or against a schema where the policies were never applied
-- (every step is guarded / drop-if-exists). Running this returns the tables to
-- their pre-RLS state; the authoritative app-layer guards are unaffected.
-- =============================================================================

-- --------------------------------------------------------------------------- --
-- 1. Drop policies + disable RLS (guarded for absent tables)
-- --------------------------------------------------------------------------- --
create or replace function agave_rls_teardown(p_table text, p_policies text[])
  returns void language plpgsql as $$
declare
  v_policy text;
begin
  if to_regclass('public.' || p_table) is null then
    raise notice 'agave_rls: table public.% absent, nothing to tear down', p_table;
    return;
  end if;
  foreach v_policy in array p_policies loop
    execute format('drop policy if exists %I on public.%I', v_policy, p_table);
  end loop;
  execute format('alter table public.%I disable row level security', p_table);
end
$$;

do $$
begin
  perform agave_rls_teardown('work_orders',
    array['agave_wo_select', 'agave_wo_insert', 'agave_wo_update']);
  perform agave_rls_teardown('work_order_items',
    array['agave_woi_select', 'agave_woi_insert', 'agave_woi_update']);
  perform agave_rls_teardown('execution_records',
    array['agave_exec_select', 'agave_exec_insert', 'agave_exec_update']);
  perform agave_rls_teardown('photo_evidence',
    array['agave_photo_select', 'agave_photo_insert', 'agave_photo_update']);
  perform agave_rls_teardown('reviews',
    array['agave_review_select', 'agave_review_insert', 'agave_review_update']);
  perform agave_rls_teardown('organizations',
    array['agave_org_select', 'agave_org_update']);
  perform agave_rls_teardown('organization_members',
    array['agave_member_select', 'agave_member_insert', 'agave_member_update']);
  perform agave_rls_teardown('invitations',
    array['agave_invite_select', 'agave_invite_insert', 'agave_invite_update']);
  perform agave_rls_teardown('app_users',
    array['agave_appuser_select', 'agave_appuser_update']);
end
$$;

-- --------------------------------------------------------------------------- --
-- 2. Drop helper functions (teardown helper last)
-- --------------------------------------------------------------------------- --
drop function if exists agave_execution_visible(integer);
drop function if exists agave_work_order_visible(integer);
drop function if exists agave_current_scope_emails();
drop function if exists agave_current_scope_lot_ids();
drop function if exists agave_current_scope_ranch_ids();
drop function if exists agave_current_data_scope();
drop function if exists agave_current_app_user_id();
drop function if exists agave_current_org_id();
drop function if exists agave_rls_apply(text, text, text, text, text);
drop function if exists agave_rls_teardown(text, text[]);
