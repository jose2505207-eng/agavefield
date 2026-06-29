# Agave Field — Technical Wiki

A living, source-grounded wiki for the **Agave Field** platform: a field
operations, work-order, and traceability system for agave production in Jalisco,
Mexico. Every claim here is grounded in real files under `/home/ivancito/agavefield`.
Where something could not be verified in source, it is marked **"not found in
source"** rather than invented.

> Last generated against the working tree on branch `HEAD` (detached). Re-verify
> against `git log` / current code before acting on any specific symbol — see
> [Missing Features / Gaps](missing-features-gaps.md) for known drift risks.

## What this system is

A field worker (or agronomist) is assigned a **Work Order** with a checklist of
**Activities** (optionally tied to **Products** and doses). The worker opens a
**tokenized mobile link**, records actual surface/dose/notes, captures **GPS**
and **photo evidence**, and submits. The system snapshots **weather** and
**carbon factors**, writes an **immutable execution record**, and routes it to a
**reviewer** for approval/rejection/correction. Everything is **audit-logged**
and surfaced on a **Streamlit command-center dashboard** (and a newer Next.js
frontend). The product equation (from `CLAUDE.md`):

> Planned Work Order + Assigned Checklist + Product/Activity Control +
> Dose/Surface + Photo/GPS Evidence + Weather Snapshot + Carbon Factor +
> Review Approval + Audit Trail = **Enterprise Field Traceability**

There is also an **older Telegram/observation intake layer** (field observations,
tasks, alerts, escalations, weekly reports) that predates the operations layer
and still ships. See [Architecture](architecture.md) for how the two relate.

## Navigation

| Page | What's inside |
|------|---------------|
| [Architecture](architecture.md) | Request flow across API ⇄ DB ⇄ Streamlit ⇄ Next.js ⇄ Telegram ⇄ storage/weather; the two data subsystems |
| [Data Flow & Module Boundary](data-flow.md) | The two-subsystem boundary: what operations vs. observation each own, the shared foundation, the divergences (separate weather/timeline), and a "which layer do I extend?" guide |
| [Data Model Reference](data-model.md) | Entities, relationships, immutability/soft-delete/carbon-snapshot principles |
| [Modules & Services Guide](modules-services.md) | `carbon_service`, `audit_service`, `catalog_service`, `work_order_service`, `execution_service`, `review_service`, integrations |
| [API Route Reference](api-reference.md) | Every router and endpoint that exists in `app/api/` |
| [Dashboard & Mobile Task Page](dashboard-and-mobile.md) | Streamlit dashboard pages, the mobile completion page, and the Next.js `web/` frontend |
| [Setup, Env & Deploy](setup-env-deploy.md) | Local run, env vars (from `.env.example`), Docker, Vercel, Streamlit Cloud, Supabase |
| **[Missing Features / Gaps](missing-features-gaps.md)** | What the enterprise goal calls for that is **not yet** (or only partially) implemented — grounded in source |
| [Future Scope / Roadmap](future-scope-roadmap.md) | Phased, prioritized future work aligned with the ~7-year agave lifecycle mission |

## Stack at a glance (verified in `requirements.txt`, `app/`, `dashboard/`)

- **Python 3.12**, **FastAPI 0.115** (`app/main.py`), **SQLAlchemy 2.0** (`app/db.py`)
- **Pydantic v2 / pydantic-settings** (`app/config.py`, `app/models/*_schemas.py`)
- **PostgreSQL / Supabase** in prod; **SQLite** for tests
- **Next.js / TypeScript** `web/` — the **canonical admin frontend** (decision 2026-06-28)
- **Streamlit** dashboard (`dashboard/app.py`) — legacy/internal, over HTTP via `API_BASE_URL`
- Schema managed by **Alembic** (`alembic/versions/`, baseline `49fa233d5c67`); `supabase_schema.sql` is reference only
- S3-compatible **storage** (`app/integrations/storage_client.py`), Open-Meteo **weather**, **Telegram** intake
- Deploy: API on **Vercel** (`vercel.json`, `api/index.py`); dashboard on **Streamlit Cloud**
- Tests: **pytest** (`tests/`, 86 test functions; all green)

## How to keep this wiki honest

This wiki documents the code *as read*. When you change code, update the matching
page and the [gaps](missing-features-gaps.md) / [roadmap](future-scope-roadmap.md)
pages. Prefer linking to file paths and symbol names so future readers can verify.
