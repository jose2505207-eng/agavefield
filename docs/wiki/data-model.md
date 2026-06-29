# Data Model Reference

Entities, relationships, and the traceability/carbon principles enforced by the
schema. Operations-layer models live in `app/models/operations.py`; the older
agronomy/observation models live in `app/models/database.py`. The production
schema is mirrored by hand in `supabase_schema.sql`.

## Operations / traceability entities (`app/models/operations.py`)

### Catalogs / directory
| Entity | Table | Key columns | Notes |
|--------|-------|-------------|-------|
| `Assignee` | `assignees` | `full_name, email, phone, role, active` | Field workers/reviewers. `active` flag for soft-deactivate. |
| `Product` | `products` | `product_name, product_type, allowed/restricted/prohibited`, dose min/default/max, **carbon factor** (`carbon_factor_value/unit/source/version`), `active` | Carbon factors are **manually defined**, never AI-estimated. |
| `Activity` | `activities` | `activity_name, activity_category`, requirement toggles (`requires_photo_evidence`, `requires_geolocation`, `requires_dose`, `requires_surface_area`, `requires_weather_snapshot`), **carbon factor** fields, `active` | Drives what a checklist item demands. |
| `Season` | `seasons` | `name, code, start_date, end_date, description, active, created_by` + TimestampMixin | First-class season dimension (added Phase 2.1). Referenced by `WorkOrder.season_id` at the service layer. |

### Work orders
| Entity | Table | Highlights |
|--------|-------|-----------|
| `WorkOrder` | `work_orders` | `work_order_code` (`WO-YYYY-NNNN`, unique), FKs to `farms/lots/field_zones/agave_passports`, `assigned_to_id`/`assigned_to_email`, `status` (`draft→sent→submitted→…`), **`secure_access_token_hash`** + `secure_link_expires_at`, requirement toggles, **`deleted_at` (soft delete only)** |
| `WorkOrderItem` | `work_order_items` | One checklist line. FK `activity_id` (+ optional `product_id`), planned surface/dose/total-product, per-item requirement toggles, **locked carbon snapshot** (`planned_carbon_factor_value/unit`, `planned_carbon_kgco2e`, `carbon_factor_snapshot` JSON) |

`season_id` exists on `WorkOrder` as a nullable integer. A first-class **`Season`
entity now exists** (`seasons` table, migration `6e1219fdb59c`; model in
`operations.py`; CRUD at `/api/seasons` via `season_service`). `WorkOrder.season_id`
references `seasons.id` **at the service layer only** — it is not yet a DB-level FK
(deferred to avoid a fragile SQLite ALTER; see
[roadmap 2.1](future-scope-roadmap.md)). A full agave lifecycle/maturity model is
still future work — see [gaps](missing-features-gaps.md#no-season-or-lifecycle-model).

### Execution (immutable)
| Entity | Table | Highlights |
|--------|-------|-----------|
| `ExecutionRecord` | `execution_records` | The worker's submission. Actual surface/dose/total-product, `execution_started/completed_at`, `responsible_person`, `submitted_by_*`, GPS (lat/lon/accuracy/captured_at), `weather_snapshot_id`, **actual carbon** (`actual_carbon_kgco2e`, `carbon_factor_snapshot`, `carbon_calculation_status`) + **manual override** fields (`carbon_override_value/reason/user/at`), `compliance_status` (`pending_review`/`needs_correction`/`compliant`/`non_compliant`), **`is_revision_of_id`** (self-FK for revision chain), `submitted_at` |
| `PhotoEvidence` | `photo_evidence` | `file_url, storage_key, thumbnail_url`, FKs to work order/item/execution + farm/lot/zone/passport, GPS + `gps_source` (`device|exif|manual|unavailable`), `captured_at`, `uploaded_at`, optional `weather_snapshot_id` |
| `OpsWeatherSnapshot` | `ops_weather_snapshots` | Rain-first weather at submission (rainfall current/prob/24h, temp, humidity, wind, `raw_payload_json`, `provider`) |

### Review, timeline, audit
| Entity | Table | Highlights |
|--------|-------|-----------|
| `Review` | `reviews` | `execution_record_id`, `review_status` (`pending/approved/rejected/needs_correction`), reviewer id/name/notes, `correction_requested`, `correction_due_date`, `reviewed_at`. One row **per decision** (history, never overwritten) |
| `TimelineEvent` | `timeline_events` | Polymorphic `entity_type` (`field/lot/zone/agave_passport`) + `entity_id`, `event_type`, `title`, related work-order/execution/product/activity ids, `related_photo_ids` JSON, `carbon_kgco2e`, `weather_snapshot_id` |
| `AuditLog` | `audit_logs` | Append-only. `entity_type/entity_id/action`, `old_values_json`/`new_values_json`, `changed_by(_email)`, `timestamp`, `reason`, `ip_address`, `user_agent` |

### Relationship sketch
```
Farm(=field) ─< Lot ─< FieldZone(=zone)        AgavePassport
     ▲            ▲          ▲                        ▲
     └────────────┴──────────┴── FK ──┐               │
                                      │               │
Assignee ──< WorkOrder ──────────────┘───────────────┘
                  │  1─┐
                  │    └──< WorkOrderItem ── activity_id ▶ Activity
                  │            │             product_id  ▶ Product
                  │            │ (locked carbon snapshot)
                  │            ▼
                  └──< ExecutionRecord ──< PhotoEvidence
                          │  ▲ is_revision_of_id (chain)
                          │  └── weather_snapshot_id ▶ OpsWeatherSnapshot
                          └──< Review (one per decision)
TimelineEvent / AuditLog reference everything by loose ids (no hard FK).
```

## Agronomy + observation entities (`app/models/database.py`)
Confirmed via `supabase_schema.sql` table list: `users, farms, lots, field_zones,
agave_passports, field_observations, model_outputs, weather_snapshots,
escalations, tasks, alerts, human_validations, weekly_reports`. These power the
Telegram intake / observation review / weekly report features and predate the
operations layer.

## Traceability & integrity principles (enforced in code)

1. **Immutable execution history.** `ExecutionRecord` is never overwritten. A
   correction re-submission creates a new record with `is_revision_of_id` →
   revision chain (`execution_service.submit_execution`,
   `review_service.revision_history`).
2. **Locked carbon snapshots.** Carbon factors are copied onto `WorkOrderItem` at
   creation (`work_order_service._snapshot_item_carbon`) and re-used at submission
   (`execution_service` reads `item.carbon_factor_snapshot`). Catalog factor edits
   **never** recompute historical records. See [Modules & Services](modules-services.md#carbon_service).
3. **Soft delete / deactivate.** `WorkOrder.deleted_at` is the only delete path for
   orders (`list_work_orders` filters `deleted_at IS NULL`). Catalog rows tied to
   history are **deactivated, not deleted** (`catalog_service.delete_or_deactivate_*`
   counts references first).
4. **Append-only audit.** Every create/update/submit/approve/reject/send/override
   calls `audit_service.log(...)`.
5. **Required fields / completeness gating.** Per-item toggles (`requires_geolocation`,
   `requires_manual_note`, `required_photo_count`) drive `needs_correction` warnings
   at submission instead of silently accepting incomplete work.
6. **Carbon override is additive.** Overrides set `carbon_override_*` and preserve
   the originally calculated `actual_carbon_kgco2e` (`execution_service.override_carbon`).

## Schema management — Alembic is authoritative
Schema changes go through **Alembic** (`alembic/versions/`, baseline
`49fa233d5c67`, which captures all 24 tables exactly as the ORM defines them).
`alembic/env.py` imports both `app.models.database` and `app.models.operations`,
so autogenerate covers every table. Workflow for a model change:
`alembic revision --autogenerate -m "..."` → review → `alembic upgrade head`. CI
runs `alembic check` to fail on drift. `supabase_schema.sql` is kept **for
reference only**; `init_db()` (`create_all`) is a dev/test convenience. See
[Setup & Deploy](setup-env-deploy.md#database--schema).
