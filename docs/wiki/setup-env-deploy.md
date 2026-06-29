# Setup, Environment & Deploy

Grounded in `requirements.txt`, `.env.example`, `app/config.py`, `docker-compose.yml`,
`Dockerfile`, `vercel.json`, `api/index.py`, and the deploy docs
(`SETUP.md`, `DEPLOY_VERCEL.md`, `GO_LIVE.md`).

## Run locally (no Docker)

```bash
# 1. API
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000  (/docs for OpenAPI)

# 2. Dashboard (separate deps to keep the API slim for Vercel)
pip install -r dashboard/requirements.txt
API_BASE_URL=http://localhost:8000 streamlit run dashboard/app.py

# 3. Next.js frontend (optional)
cd web && npm install && npm run dev    # http://localhost:3000
```

> Note: this analysis ran in an environment **without** the Python deps installed
> (`python` absent; `sqlalchemy` not importable), so the test suite could not be
> executed here — see [Testing](#testing).

## Run with Docker
`docker-compose.yml` + `Dockerfile` exist for a containerized API. The dashboard
reaches the API via the compose service name (see `PUBLIC_BASE_URL` note in
`.env.example`). Review `docker-compose.yml` for service names/ports before use.

## Environment variables (from `.env.example` + `app/config.py`)

Every var has a safe default so the app boots on an empty `.env`. Document any new
var in `.env.example` (placeholders only).

| Group | Vars | Notes |
|---|---|---|
| Core | `APP_ENV`, `DATABASE_URL`, `PUBLIC_BASE_URL`, `APP_BASE_URL` | `APP_BASE_URL` builds secure work-order links |
| Secrets | `SECRET_KEY` | hashes work-order tokens; **defaults to `change-me-in-production` / `dev-insecure-change-me`** — must be overridden in prod |
| RBAC | `ADMIN_API_KEY`, `AGRONOMIST_API_KEY`, `REVIEWER_API_KEY`, `API_KEY` | leave all blank = **open dev mode**; set in prod. `API_KEY` is what the dashboard sends |
| Work orders | `WORK_ORDER_LINK_EXPIRY_DAYS` (config default 14) | token link lifetime |
| Email | `EMAIL_PROVIDER` (`console|smtp|sendgrid|resend`), `SMTP_*`, `SENDGRID_API_KEY`, `RESEND_API_KEY` | falls back to console |
| Storage | `STORAGE_PROVIDER` (`local|s3`), `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY/SECRET`, `STORAGE_ENDPOINT`, `STORAGE_REGION`, `STORAGE_PUBLIC_BASE` | Supabase Storage = S3 + region + public base |
| Weather | `WEATHER_PROVIDER` (`auto|mock|openweather`), `WEATHER_API_KEY` | `auto` = Open-Meteo, mock fallback |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_WEBHOOK_SYNC` | set `SYNC=true` on serverless |
| WhatsApp | `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_DEFAULT_ESCALATION_RECIPIENTS` | optional |
| Vision (gated) | `VISION_PROVIDER`, `VISION_API_KEY`, `VISION_BASE_URL`, `VISION_MODEL`, `ENABLE_AI_IMAGE_ANALYSIS=false` | **keep false** in MVP |
| Escalation | `ESCALATION_COOLDOWN_HOURS` (24) | intake layer |

`web/` uses `NEXT_PUBLIC_API_BASE_URL` (and a server-only API key for the proxy) —
see `web/.env.example`.

### Secrets hygiene
`.gitignore` excludes `.env`, `.env.vercel`, `.env.*` (keeping `.env.example`).
Secrets live only in env files / Vercel / Streamlit settings. **Never commit
secrets**; `.env.example` holds placeholders only.

## Database / schema {#database--schema}
**Alembic is the source of truth for the schema** (`alembic/versions/`, baseline
`49fa233d5c67`). `alembic/env.py` reads `DATABASE_URL` and targets both
`app.models.database` and `app.models.operations`.

```bash
# New / empty database (local or a fresh Supabase project): build the schema.
alembic upgrade head

# Existing Supabase DB already built from supabase_schema.sql: DON'T re-create
# tables — just record that it is already at the baseline.
alembic stamp 49fa233d5c67

# Making a schema change (the standard workflow):
#   1) edit the SQLAlchemy models
#   2) autogenerate a migration, review it, then apply
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

- CI runs `alembic upgrade head && alembic check` to **fail on drift** between the
  models and the migrations.
- `supabase_schema.sql` is kept **for reference only** (it still mirrors the ORM).
- `init_db()` (`create_all`) in `app/db.py` is a **dev/test convenience** — the test
  suite builds its SQLite schema via `Base.metadata.create_all` in
  `tests/conftest.py`, not Alembic.
- Seed helpers: `scripts/seed.py`, `scripts/seed_catalog.py` (+ CSV templates).

## Deploy targets
- **API → Vercel**: `api/index.py` re-exports `app`; `vercel.json` rewrites all
  paths to `/api/index`, `maxDuration: 60`. Keep API deps slim (dashboard deps are
  separate). On serverless, set `TELEGRAM_WEBHOOK_SYNC=true` and rely on the
  pre-created Supabase schema (startup `init_db` is best-effort). See `DEPLOY_VERCEL.md`.
- **Dashboard → Streamlit Cloud**: long-running; cannot run on Vercel. Point it at
  the deployed API with `API_BASE_URL` + `API_KEY`.
- **`web/` → separate Vercel project**, root dir `web/`.
- **DB + Storage → Supabase** (Postgres + Storage S3 API). See `GO_LIVE.md`.

## Testing
- `pytest` suite in `tests/` — **86 test functions** (SQLite,
  offline; `tests/conftest.py` wires `app.db`). Run:
  ```bash
  pip install -r requirements.txt && pytest -q
  ```
- Could **not** be executed in this analysis environment (deps not installed).
  Verify green locally/CI before shipping. See `testing` notes in the
  [roadmap](future-scope-roadmap.md).
