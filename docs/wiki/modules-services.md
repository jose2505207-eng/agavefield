# Modules & Services Guide

What each service/integration does, where it lives, and the contracts to respect.
All under `app/services/` and `app/integrations/`.

## Operations-layer services

### `work_order_service.py`
Work-order lifecycle: create (with locked carbon snapshots) and secure send.
- `generate_work_order_code(db)` → `WO-<year>-NNNN`.
- `create_work_order(db, data, items, actor)` → builds `WorkOrder` + items;
  `_snapshot_item_carbon` locks carbon via `carbon_service.compute_carbon`.
- `duplicate_work_order` → clones into a fresh draft; carbon is **re-snapshot**
  from the current catalog (a new plan), not copied from the source's locked values.
- `send_work_order` → `secrets.token_urlsafe(32)`, stores **SHA-256 hash only**,
  sets `secure_link_expires_at` (`work_order_link_expiry_days`, default 14),
  emails the assignee, marks `sent`, audit-logs, returns raw token/link to caller.
- `find_by_token(db, raw_token)` → hash match **and** expiry check; returns `None`
  if expired/invalid.
- `hash_token` = `hashlib.sha256(token).hexdigest()`.

### `execution_service.py`
Worker submission → immutable `ExecutionRecord`(s).
- `submit_execution(db, wo, payload)` → one weather snapshot per submission;
  per item computes **actual carbon** from the item's *locked* factor snapshot ×
  actual quantities; gates completeness (GPS/note/photos) into `compliance_status`;
  writes the record with `is_revision_of_id` set to the prior record for that item
  (revision chain); links photos; adds timeline event; audit-logs.
- `override_carbon(db, execution_id, value, reason, user)` → manual override with
  reason + user + timestamp; preserves the calculated value; audit-logged.
- **Contract:** never overwrite a submitted record; never recompute historical carbon.

### `review_service.py`
Reviewer decisions on a submitted `ExecutionRecord`.
- `review_queue(db)` → open records (`pending_review`, `needs_correction`).
- `approve` / `reject` / `request_correction` → write a `Review` row (one per
  decision), flip `ExecutionRecord.compliance_status` and the item status, audit-log,
  add timeline event. **The execution data itself is never modified.**
- `revision_history(db, execution_id)` → walks the `is_revision_of_id` chain
  oldest→newest.

### `carbon_service.py`
Applies **manually defined** carbon factors to actual data; never invents factors.
- Supported factor units: `kgCO2e_per_ha | _m2 | _kg_product | _liter | _event`.
- `calculate_single(...)` → applies one factor; status `calculated` /
  `missing_data` / `no_factor` / `unknown_unit`.
- `compute_carbon(...)` → total = activity contribution + product contribution;
  returns `(total, status, snapshot)`. Partial totals are kept but flagged
  `missing_data`. The `snapshot` dict is what gets persisted as the locked factor.

### `catalog_service.py`
History-safe CRUD for `Assignee`/`Product`/`Activity`.
- `_create` / `_update` always audit-log.
- `delete_or_deactivate_*` → counts references in work orders/executions/reviews;
  if any exist, **deactivate** (`active=False`); else hard-delete the unused row.

### `audit_service.py`
Append-only audit trail.
- `log(db, entity_type, entity_id, action, new_values, old_values, changed_by, …)`
  → coerces values to JSON-safe primitives (`_jsonable`), writes an `AuditLog`.
- `history(db, entity_type, entity_id)` → newest-first list. **No update/delete API.**

### `ops_weather_service.py`, `timeline_service.py`, `carbon_report_service.py`
- `ops_weather_service.capture_snapshot(...)` → fetches via `weather_provider`,
  persists an `OpsWeatherSnapshot`, returns `(snapshot, status)`.
- `timeline_service` → reads `timeline_events` for an entity.
- `carbon_report_service` → aggregations behind `/api/carbon/*` (summary,
  by-season/activity/product/lot/field, missing-data, overrides).

## Older agronomy / observation services
(`observation_service`, `task_service`, `escalation_service`, `weather_service`,
`lot_matching_service`, `report_service`, `passport_service`, `image_service`,
`comparison_service`, `dashboard_service`, `system_status_service`,
`notification_service`.) These power Telegram intake, observation review, lots,
passports, tasks/alerts, weekly reports, before/after comparison, and the
system-status panel. `image_service.store_image_bytes` is the shared image
persistence path (also used by ops photo upload) and produces thumbnails via Pillow.

## Integrations (`app/integrations/`) — provider abstractions

### `email_client.py`
`EmailProvider` ABC → `Console | SMTP | SendGrid | Resend`. `get_email_provider()`
picks by `EMAIL_PROVIDER` and **falls back to console** if credentials are missing.
`send_email(to, subject, body) → (delivered, provider_name)`. Never hard-fails.

### `storage_client.py`
`StorageClient` ABC → `LocalStorageClient` (writes `./storage`, serves `/media`) or
`S3StorageClient` (boto3, SigV4, works with AWS S3 / MinIO / **Supabase Storage**).
`get_storage_client()` falls back to local if S3 is unconfigured/unavailable.

### `weather_provider.py`
Open-Meteo (no key) / mock fallback, selected by `WEATHER_PROVIDER` (`auto` default).

### `telegram_client.py`, `whatsapp_client.py`
Outbound messaging for the intake layer. Enabled only when tokens are set
(`settings.telegram_enabled`, `settings.whatsapp_enabled`).

### `vision_client.py` (gated OFF)
Multimodal vision client. **Not called on upload** in the MVP —
`ENABLE_AI_IMAGE_ANALYSIS=false`. Photos are evidence; humans are the source of
truth. Do not wire vision into upload paths without flipping the flag *and*
updating `CLAUDE.md`.

## Config (`app/config.py`)
`Settings(BaseSettings)` with **safe defaults for every field** so the app boots
on an empty `.env`. Notable: `secret_key` defaults to `"dev-insecure-change-me"`,
`work_order_link_expiry_days=14`, `email_provider="console"`, `storage_provider="local"`,
`weather_provider="auto"`. `get_settings()` is `lru_cache`d. **There is no
fail-fast validation** that production secrets/URLs are real — see
[gaps](missing-features-gaps.md#weak-env-validation).

## Conventions to follow (from `CLAUDE.md`)
- Services in `app/services/`, routes in `app/api/`, Pydantic schemas for all
  request/response bodies, SQLAlchemy 2.0 `Mapped[...]` columns.
- `from __future__ import annotations` at top; type hints everywhere.
- Keep business logic in services; route handlers orchestrate only.
- Keep models DB-agnostic so SQLite tests pass.
