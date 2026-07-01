# CLAUDE.md — Agave Field

Project brain for Claude Code. Read this before making changes.

## Mission
Agave Field is a **field operations, work-order, and traceability platform** for
agave production. Core users: agronomist, field-ops manager, agricultural
compliance lead. The product equation:

> Planned Work Order + Assigned Checklist + Product/Activity Control + Dose/Surface
> + Photo/GPS Evidence + Weather Snapshot + Carbon Factor + Review Approval + Audit
> Trail = **Enterprise Field Traceability**

## Current stack — PRESERVE IT (do not change without strong, explained reason)
- **Language:** Python 3.12
- **API:** FastAPI (`app/main.py`, routers in `app/api/*`)
- **ORM/DB:** SQLAlchemy 2.0 (`app/db.py`, `Base`) → **Supabase PostgreSQL** in prod
  (DB-agnostic models; SQLite for tests). **Alembic is the source of truth for the
  schema** (`alembic/versions/`, baseline `49fa233d5c67`); `supabase_schema.sql` is
  kept for reference only.
- **Validation:** Pydantic v2 (`app/models/schemas.py`, `app/models/ops_schemas.py`)
- **Admin frontend (canonical):** **Next.js / TypeScript** (`web/`, App Router, Tailwind,
  lucide-react) — the primary admin/ops UI. Talks to the API through a same-origin proxy
  (`web/app/proxy/[...path]/route.ts`) that injects the RBAC key server-side.
- **Streamlit dashboard:** `dashboard/app.py` — legacy internal command center, still
  supported for quick internal/ops views; **not** the surface for new admin UI work.
- **Storage:** S3-compatible (`app/integrations/storage_client.py`) → Supabase Storage
- **Weather:** `app/integrations/weather_provider.py` (Open-Meteo / mock)
- **Intake:** Telegram bot (`app/api/telegram_routes.py`) — human-centered, no AI
- **Deploy:** API on Vercel (`vercel.json`, `api/index.py`); `web/` frontend on a separate
  Vercel project (root dir `web/`); Streamlit dashboard on Streamlit Cloud
- **Tests:** pytest (`tests/`), offline on SQLite

> **Backend stack is fixed:** Python 3.12 + FastAPI + SQLAlchemy 2.0 + Pydantic v2. Do
> **not** swap the backend language, web framework, or ORM. **Frontend:** the canonical
> admin UI is the Next.js `web/` app (TypeScript/Tailwind) — build new admin/ops screens
> there. Keep all business logic in the FastAPI services; the frontend is a thin client
> over `/api/*` (no business logic, no direct DB access).

## What already exists (operations / traceability layer)
- Models: `app/models/operations.py` — `Assignee, Product, Activity, WorkOrder,
  WorkOrderItem, ExecutionRecord, PhotoEvidence, OpsWeatherSnapshot, Review,
  TimelineEvent, AuditLog` (all live in Supabase).
- Services: `carbon_service.py` (factor snapshots + per ha/m²/kg/liter/event math),
  `audit_service.py` (append-only audit), `catalog_service.py` (history-safe CRUD).
- Routes: `/api/products`, `/api/activities`, `/api/assignees`, `/api/audit/...`.
- Agronomy base: `Farm`(=field), `Lot`, `FieldZone`(=zone), `AgavePassport`.
- **Organization RBAC** (multi-user profiles): `Organization`, `OrganizationMember`
  (role + 10 normalized permission booleans + `data_scope`), `Invitation`
  (hash-only tokens, expiry, max-uses). Resolution/enforcement in
  `app/services/rbac_service.py`, deps in `app/api/rbac.py`, endpoints in
  `app/api/org_routes.py` (`/api/org/context|members|invitations`). Data
  visibility is filtered **server-side** by `data_scope`; a **member read-only
  guard** in `app/main.py` blocks writes by auditor/worker roles (twin of the
  demo guard). Roles seed defaults but permissions are per-member overridable —
  read the stored booleans, never the role string. Full spec: `docs/RBAC.md`.
  Migration head: **`b4b8620239bc`** (baseline `49fa233d5c67`).

## Module boundary (two subsystems)
This app hosts **two overlapping domains on one DB/app**. Know which you're in
before extending. Full definition: `docs/wiki/data-flow.md`.
- **Operations / traceability layer** (`app/models/operations.py`): work-order →
  execution → review → carbon/audit. Extend this for work orders, executions,
  evidence, reviews, carbon, audit.
- **Observation / intake layer** (`app/models/database.py`): Telegram/WhatsApp
  intake, observations, tasks, alerts, escalations, weekly reports. Extend this
  for inbound human-reported field signal (AI/vision stays gated OFF).
- **Shared foundation:** `farms/lots/field_zones/agave_passports`, `/media`
  storage, the FastAPI app + RBAC, the DB (one Alembic history).
- **Deliberate divergences:** separate weather tables
  (`ops_weather_snapshots` vs `weather_snapshots`) and separate timelines (ops
  `timeline_events` vs observation history). No unified entity timeline yet
  (roadmap 1.2). Merge-vs-separate is still an open question.

## Enterprise production goal
Real DB persistence, real file storage, env validation, safe secrets, secure
tokenized task links + expiry, soft deletes, immutable execution records, revision
history, server-side validation, clear error/loading/empty/success states,
mobile-first task UI, audit logs, clean provider abstractions (email/storage/weather).

## Coding standards
- Match existing patterns: services in `app/services/`, routes in `app/api/`, Pydantic
  schemas for all request/response bodies, SQLAlchemy 2.0 `Mapped[...]` columns.
- Small, composable services. No business logic in route handlers beyond orchestration.
- Type hints everywhere. `from __future__ import annotations` at top of modules.
- Comment only non-obvious design decisions.
- Keep models DB-agnostic (no PostGIS-only types) so tests run on SQLite.

## UI/UX standards (Next.js `web/` admin frontend, Streamlit dashboard, mobile task page)
- Feels like an **agricultural operations command center**, not a generic admin panel.
- Always show loading / empty / error / success states. Never fake data — if there's
  no data, say "data not available".
- The worker **mobile task page** (token link) must be mobile-first and must NOT expose
  the admin dashboard.

## Data-model principles
- Entity mapping: field=`farms`, lot=`lots`, zone=`field_zones`, passport=`agave_passports`.
- Carbon factors are **copied as locked snapshots** onto `WorkOrderItem` / `ExecutionRecord`.
  Never recompute historical records when catalog factors change.
- Catalog records tied to history are **deactivated, never hard-deleted**.
- Corrections create **revision history**; never overwrite a submitted `ExecutionRecord`.

## Audit / traceability principles (FDA-style, NOT certified)
- Do not claim official FDA compliance. Implement the principles: controlled records,
  required fields, reviewer approval, immutable execution history, evidence preservation,
  clear accountability.
- Audit-log every create/update/submit/approve/reject/send/upload/carbon action via
  `audit_service.log(...)`.
- Preserve timestamps, reviewer identity, factor snapshots, evidence links.

## Security principles
- Never commit secrets. Secrets live only in `.env` / `.env.vercel` (git-ignored) and in
  Vercel/Streamlit env settings. `.env.example` has placeholders only.
- Work-order links use a random token; store only a **hash** of it; support expiry.
- Validate all input server-side with Pydantic. Fail gracefully on missing third-party
  credentials (email/weather/storage).

## Environment variables
Document every new var in `.env.example` (placeholders only). Current/expected:
`DATABASE_URL, APP_BASE_URL, SECRET_KEY, STORAGE_PROVIDER, STORAGE_BUCKET/S3_*,
STORAGE_ENDPOINT, STORAGE_ACCESS_KEY/SECRET, EMAIL_PROVIDER, SMTP_*, SENDGRID_API_KEY,
RESEND_API_KEY, WEATHER_PROVIDER, WEATHER_API_KEY, TELEGRAM_*, ENABLE_AI_IMAGE_ANALYSIS=false`.

## What NOT to do
- ❌ No LLM/computer-vision image analysis in the MVP (pest/disease/severity/diagnosis).
  `ENABLE_AI_IMAGE_ANALYSIS=false` (default). Photos are evidence; humans are the source of truth.
- ❌ No **backend** framework/language/ORM swap (Python / FastAPI / SQLAlchemy / Pydantic
  are fixed). No business logic or direct DB access in the frontend. (TypeScript / Next.js
  IS allowed and IS the canonical admin frontend — but only in `web/`.)
- ❌ No hard deletes of execution/product/carbon/evidence records.
- ❌ No mutating historical carbon once snapshotted.
- ❌ No fabricated carbon factors, no external carbon APIs.
- ❌ No secrets in code; no `git push` unless explicitly asked.
- ❌ No whole-app rewrites; small, safe, reversible increments only.

## Implementation workflow
1. Inspect relevant files first (use `legacy-code-surgeon`).
2. Plan the smallest safe slice (use `product-architect`).
3. Implement: model → **Alembic migration** (`alembic revision --autogenerate -m "..."`,
   additive; then `alembic upgrade head`) → service → Pydantic schema → route → frontend
   (`web/`; or the Streamlit dashboard for internal views).
4. Keep the suite green: `pytest -q`. Add tests for new critical logic.
5. Update `.env.example` + this file when conventions change.
6. Verify build/import; report risks. Do not push unless asked.
