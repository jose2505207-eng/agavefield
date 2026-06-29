# Architecture

Source-grounded map of how Agave Field is wired together. File paths are
relative to the repo root unless absolute.

## 10,000-ft view

```
  Intake                     FastAPI backend (app/main.py)                Frontends
  ──────                     ─────────────────────────────                ─────────
  Telegram  ─webhook──▶  /webhooks/telegram (telegram_routes)
  WhatsApp  ─webhook──▶  /webhooks/whatsapp (whatsapp_routes)        ┌▶ Streamlit dashboard
                              │                                       │   (dashboard/app.py)
  Agronomist (browser) ──────▶  REST /api/* routers ─────────────────┤   over API_BASE_URL
                              │                                       │
  Field worker (mobile) ─────▶  /work-orders/complete/{token}        └▶ Next.js web/ frontend
   (tokenized link)            /api/work-orders/complete/{token}/...      over /proxy/* → API
                              │
                              ▼
                    Services (app/services/*)
                      work_order · execution · review · carbon · audit · catalog
                              │
              ┌───────────────┼─────────────────────────┐
              ▼               ▼                          ▼
     SQLAlchemy ORM    Integrations (app/integrations/*)   Provider abstractions
     (app/db.py)        storage_client (local | S3)         email_client (console|smtp|
     → Supabase         weather_provider (open-meteo|mock)   sendgrid|resend)
       Postgres /       telegram_client / whatsapp_client
       SQLite (test)    vision_client (gated, OFF by default)
```

## The FastAPI app (`app/main.py`)

- Creates the `FastAPI` app with a `lifespan` that calls `init_db()` **best-effort**
  (wrapped in try/except so serverless cold starts never crash if the schema
  already exists — see lines 47–63).
- CORS is wide open (`allow_origins=["*"]`) — see [gaps](missing-features-gaps.md).
- If `STORAGE_PROVIDER=local`, mounts `./storage` at `/media` for image serving.
- Registers ~25 routers. RBAC dependencies are applied **at router include time**
  (lines 115–127): `require_staff` for catalogs/assignees/work-orders/audit/
  execution/system; `require_reviewer` for review/timeline/carbon; **public
  token-based** for `ops_photo` upload and `completion` (mobile worker page).
- `/health` returns env + feature flags (`app/main.py:87`).

### RBAC model (`app/api/auth.py`)
API-key header `X-API-Key` → role (`admin` / `agronomist` / `reviewer`). **If no
keys are configured, auth is OPEN** (dev mode) so existing flows/tests pass.
Field workers are **not** in this model — they authenticate with their
per-work-order token on the public mobile page.

## Two data subsystems (important)

The repo contains **two overlapping domains** that share the same DB and app:

### 1. Operations / traceability layer (the current focus of `CLAUDE.md`)
- Models: `app/models/operations.py` — `Assignee, Product, Activity, WorkOrder,
  WorkOrderItem, ExecutionRecord, PhotoEvidence, OpsWeatherSnapshot, Review,
  TimelineEvent, AuditLog`.
- Services: `work_order_service`, `execution_service`, `review_service`,
  `carbon_service`, `audit_service`, `catalog_service`, `ops_weather_service`,
  `timeline_service`, `carbon_report_service`.
- This is the work-order → execution → review → carbon/audit pipeline.

### 2. Older Telegram/observation intake layer (predates the ops layer)
- Models: `app/models/database.py` — `User, Farm, Lot, FieldZone, AgavePassport,
  FieldObservation, ModelOutput, WeatherSnapshot, Escalation, Task, Alert,
  HumanValidation, WeeklyReport` (table list confirmed in `supabase_schema.sql`).
- Services: `observation_service`, `task_service`, `escalation_service`,
  `weather_service`, `lot_matching_service`, `report_service`, `passport_service`,
  `image_service`, `comparison_service`, `dashboard_service`, `notification_service`.
- The **Hermes agent** (`app/agents/hermes_agent.py`, `tools.py`, `prompts.py`)
  orchestrates Telegram intake. Vision/LLM is **gated OFF** by
  `ENABLE_AI_IMAGE_ANALYSIS=false` — photos are stored as evidence only.

**Shared agronomy base** spans both: `Farm`(=field), `Lot`, `FieldZone`(=zone),
`AgavePassport`. Work orders and photo evidence reference these by FK.

> **Integration seam / open question:** the two layers are loosely coupled —
> they share farms/lots/zones/passports and the `/media` store but maintain
> *separate* weather snapshot tables (`weather_snapshots` vs
> `ops_weather_snapshots`) and separate timelines (the ops `timeline_events`
> table vs observation history). See [gaps](missing-features-gaps.md#overlapping-subsystems).

## Core request flows

### A. Create & send a work order (admin)
1. `POST /api/work-orders` → `work_order_service.create_work_order`
   - Generates `WO-<year>-NNNN` code, creates `WorkOrder` (status `draft`) + items.
   - For each item, **locks a carbon snapshot** via `carbon_service.compute_carbon`
     (`_snapshot_item_carbon`). Later catalog edits never mutate it.
   - Audit-logs `create`; adds a `TimelineEvent` if a field/lot is set.
2. `POST /api/work-orders/{id}/send` → `work_order_service.send_work_order`
   - Generates `secrets.token_urlsafe(32)`, stores **only its SHA-256 hash**
     (`secure_access_token_hash`) + expiry (`work_order_link_expiry_days`, default 14).
   - Emails the assignee a link `…/work-orders/complete/<raw_token>` via
     `email_client.send_email` (provider-abstracted; falls back to console).
   - Marks `status=sent`, audit-logs `send_email`, adds timeline event.
   - Returns the raw token/link **to the caller** (for dev/console); only the
     hash is persisted.

### B. Worker completes the order (public, token)
1. `GET /work-orders/complete/{token}` (`completion_routes`) → resolves work order
   via `work_order_service.find_by_token` (hash match + expiry check) and renders a
   **self-contained mobile HTML page** (inline CSS/JS, no admin assets).
2. Per photo: `POST /api/photos/upload` (`ops_photo_routes`) with the token +
   file + GPS → `image_service.store_image_bytes` → real object storage → a
   `PhotoEvidence` row.
3. `POST /api/work-orders/complete/{token}/submit` → `execution_service.submit_execution`:
   - Captures **one weather snapshot** for the location (`ops_weather_service`).
   - For each item: computes **actual carbon** from the item's *locked* factor
     snapshot × actual quantities; checks completeness (GPS/note/photos) and sets
     `compliance_status` = `needs_correction` if anything is missing, else
     `pending_review`.
   - Writes an **immutable `ExecutionRecord`**; a re-submit for the same item sets
     `is_revision_of_id` to chain revisions (never overwrites).
   - Links photos, adds a `TimelineEvent`, audit-logs `submit`.

### C. Reviewer decides (reviewer+)
- `GET /api/review-queue` → open records (`pending_review`/`needs_correction`).
- `POST /api/review/{id}/approve|reject|request-correction` → `review_service`
  writes a `Review` row + flips `compliance_status` / item status. **The submitted
  `ExecutionRecord` is never mutated.** `GET /api/review/{id}/revisions` walks the
  revision chain.

### D. Carbon & audit reads
- `/api/carbon/*` → `carbon_report_service` aggregations (summary, by-season/
  activity/product/lot/field, missing-data, overrides).
- `/api/audit/{entity_type}/{entity_id}` → append-only `audit_service.history`.

## Persistence (`app/db.py`)
- `Base`, `engine`, `SessionLocal`, `get_db` dependency, `init_db()` (= `create_all`,
  **dev/test convenience only**).
- Models are **DB-agnostic** (no PostGIS-only types) so tests run on SQLite.
- **Alembic is the source of truth for the schema** (`alembic/versions/`, baseline
  `49fa233d5c67`). `alembic upgrade head` on an empty DB reproduces the full schema;
  existing Supabase DBs are stamped at the baseline. `supabase_schema.sql` is kept
  for reference only. See [Setup & Deploy](setup-env-deploy.md#database--schema).

## Deployment topology
- **API** → Vercel serverless (`api/index.py` re-exports `app`; `vercel.json`
  rewrites all paths to `/api/index`, `maxDuration: 60`).
- **Next.js `web/` (canonical admin frontend)** → separate Vercel project, root dir
  `web/`.
- **Streamlit dashboard (legacy/internal)** → Streamlit Cloud (long-running; cannot
  run on Vercel).
- **DB + Storage** → Supabase Postgres + Supabase Storage (S3 API). Schema applied
  via **Alembic** (`upgrade head` for new DBs; `stamp` for existing ones).
See [Setup, Env & Deploy](setup-env-deploy.md).
