# 🌵 Agave Field Copilot

AI-powered **field intelligence** for agronomists working in the agave industry
in Jalisco, Mexico.

An agronomist sends a photo of an agave plant, row, pest/disease symptom, soil
or lot condition through **Telegram** (or **WhatsApp**). The system stores the
image, analyzes it with a vision model via the **Hermes** agent, extracts
structured agronomic observations, enriches them with **weather** and **lot**
context, writes everything to **PostgreSQL**, surfaces it on a **dashboard with
photos**, and automatically **escalates** serious cases to supervisors.

> This is a field operations system, not a chatbot. **The agronomist is always
> the expert.** Hermes assists, expresses uncertainty, never gives a definitive
> disease diagnosis, and never recommends chemical products or dosages.

---

## Table of contents
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Setup](#setup)
- [Environment variables](#environment-variables)
- [Run with Docker Compose](#run-with-docker-compose)
- [Run locally without Docker](#run-locally-without-docker)
- [Create & configure a Telegram bot](#create--configure-a-telegram-bot)
- [Configure WhatsApp later](#configure-whatsapp-later)
- [How Hermes works](#how-hermes-works)
- [How weather enrichment works](#how-weather-enrichment-works)
- [How escalation rules work](#how-escalation-rules-work)
- [The dashboard](#the-dashboard)
- [API reference](#api-reference)
- [Testing](#testing)
- [Safety notes](#safety-notes)
- [Roadmap](#roadmap)

---

## Architecture

```
                         ┌──────────────────────────────────────────────┐
   Telegram  ─┐          │                 FastAPI backend               │
   WhatsApp  ─┼─ webhook ▶  /webhooks/telegram  /webhooks/whatsapp        │
              │          │            │                                   │
              │          │            ▼                                   │
              │          │     image_service ──▶ storage_client (local/S3)│
              │          │            │                                   │
              │          │            ▼                                   │
              │          │      ┌───────────── HERMES AGENT ───────────┐  │
              │          │      │  tool_analyze_image  → vision_client  │  │
              │          │      │  tool_match_lot      → lot_matching   │  │
              │          │      │  tool_fetch_weather  → weather_service│  │
              │          │      │  tool_create_obs     → observation_svc│  │
              │          │      │  tool_maybe_escalate → escalation_svc │  │
              │          │      └───────────────────┬───────────────────┘  │
              │          │                          ▼                      │
   reply  ◀───┴──────────│   PostgreSQL: users, farms, lots,              │
   + buttons             │   field_observations, model_outputs,          │
                         │   weather_snapshots, escalations              │
                         │                          │                      │
   Supervisors ◀── escalation (WhatsApp preferred,  │                      │
                   Telegram fallback)               ▼                      │
                         │   /dashboard/* endpoints ──▶ Streamlit dashboard│
                         └──────────────────────────────────────────────┘
```

**Modularity:** messaging channels, the vision model, storage, and weather are
all behind small abstractions (`integrations/`), so each can be swapped or
extended (e.g. a future agave-specific YOLO classifier) without touching the
agent or the API.

---

## Project structure

```
app/
  main.py                 FastAPI app, /health, static /media mount, lifespan
  config.py               Env-driven settings (graceful defaults)
  db.py                   Engine, session, get_db dependency
  models/
    database.py           SQLAlchemy ORM tables
    schemas.py            Pydantic schemas + strict HermesOutput contract
  agents/
    hermes_agent.py       Orchestrates the full photo→evidence pipeline
    prompts.py            Vision system prompt (safety rules baked in)
    tools.py              Tool layer Hermes calls (wraps services)
  services/
    observation_service.py  Create/verify/correct/query observations
    weather_service.py       Open-Meteo enrichment + risk flags
    image_service.py         Download, thumbnail, store
    escalation_service.py    Rules + cooldown + WhatsApp/Telegram dispatch
    lot_matching_service.py  Point-in-polygon / nearest-centroid matching
    dashboard_service.py     Aggregations for the dashboard
  integrations/
    telegram_client.py    Telegram Bot API (send, getFile, buttons)
    whatsapp_client.py    WhatsApp Cloud API (optional)
    vision_client.py      OpenAI-compatible client + offline stub
    storage_client.py     Local + S3-compatible storage
  api/
    telegram_routes.py    Telegram webhook + button callbacks
    whatsapp_routes.py    WhatsApp verify + inbound
    observation_routes.py CRUD + verify/correct/escalate
    dashboard_routes.py   summary, gallery, lot-risk, map-points
    lot_routes.py         Lots CRUD + lot observations
dashboard/app.py          Streamlit dashboard (photos, filters, map)
scripts/seed.py           Seed a sample Jalisco farm + lots
alembic/                  Migration scaffolding (autogenerate-ready)
tests/                    pytest suite (runs offline on SQLite)
Dockerfile, docker-compose.yml, requirements.txt, .env.example
```

---

## Setup

Requirements: Python 3.12+, and Docker (optional but recommended for Postgres).

```bash
cp .env.example .env          # then edit as needed (works as-is for a local demo)
```

The MVP **runs with zero credentials**: no vision key → an offline stub
analyzer (conservative, always "needs human review"); no Telegram/WhatsApp
token → sends are logged instead of delivered.

---

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `APP_ENV` | Environment name | `development` |
| `DATABASE_URL` | PostgreSQL DSN (SQLite works for tests) | local Postgres |
| `PUBLIC_BASE_URL` | Base URL used to build `/media` image links | `http://localhost:8000` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (BotFather) | _empty_ |
| `TELEGRAM_WEBHOOK_SECRET` | Optional secret validated on webhook | _empty_ |
| `WHATSAPP_ACCESS_TOKEN` | WhatsApp Cloud API token | _empty (disabled)_ |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp sender phone id | _empty_ |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verification token | _empty_ |
| `WHATSAPP_DEFAULT_ESCALATION_RECIPIENTS` | Comma-separated phone numbers | _empty_ |
| `VISION_PROVIDER` | `openai_compatible` (falls back to stub) | `openai_compatible` |
| `VISION_API_KEY` | Vision model key; blank → offline stub | _empty_ |
| `VISION_BASE_URL` | OpenAI-compatible base URL | `https://api.openai.com/v1` |
| `VISION_MODEL` | Multimodal model id | `gpt-4o-mini` |
| `STORAGE_PROVIDER` | `local` or `s3` | `local` |
| `STORAGE_*` | S3 bucket/keys/endpoint | _empty_ |
| `WEATHER_PROVIDER` | `auto` / `mock` / `openmeteo` / `openweather` | `auto` |
| `WEATHER_API_KEY` | Required only for `openweather` | _empty_ |
| `ESCALATION_COOLDOWN_HOURS` | Dedup window per lot+issue | `24` |

Secrets are never hard-coded; everything is read from the environment.

---

## Run with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Services:
- **api** → http://localhost:8000 (Swagger docs at `/docs`)
- **dashboard** → http://localhost:8501
- **db** → PostgreSQL + PostGIS on `localhost:5432`

Tables are auto-created on startup (`init_db()`). For schema evolution use
Alembic (below).

---

## Run locally without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Point DATABASE_URL at a Postgres instance, or use SQLite for a quick demo:
export DATABASE_URL="sqlite:///./agave.db"

uvicorn app.main:app --reload --port 8000        # API + /docs
python -m scripts.seed                            # optional sample farm/lots
API_BASE_URL=http://localhost:8000 streamlit run dashboard/app.py   # dashboard
```

### Alembic migrations (optional)
```bash
alembic revision --autogenerate -m "init schema"
alembic upgrade head
```

---

## Create & configure a Telegram bot

1. In Telegram, message **@BotFather** → `/newbot` → choose a name & username.
2. Copy the token into `.env` as `TELEGRAM_BOT_TOKEN`.
3. Expose your local server (e.g. `ngrok http 8000`) to get an HTTPS URL.
4. Register the webhook (optionally with a secret matching
   `TELEGRAM_WEBHOOK_SECRET`):

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<your-ngrok>.ngrok.io/webhooks/telegram" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

5. Send a **photo** (optionally with a caption and shared location) to the bot.
   It replies with a summary and the action buttons:
   **Confirm · Change lot · Mark false positive · Escalate · Request location**.

---

## Configure WhatsApp later

WhatsApp is fully optional and gated behind env vars.

1. Create a Meta app with the **WhatsApp** product; get a `PHONE_NUMBER_ID` and
   a (permanent) access token.
2. Set `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
   `WHATSAPP_VERIFY_TOKEN`, and `WHATSAPP_DEFAULT_ESCALATION_RECIPIENTS`.
3. Configure the webhook callback URL to `…/webhooks/whatsapp` and the verify
   token to match `WHATSAPP_VERIFY_TOKEN`. The `GET` handshake is handled.
4. Inbound text/image messages create observations; escalations now prefer
   WhatsApp, with Telegram as the fallback.

---

## How Hermes works

`app/agents/hermes_agent.py` runs one inbound image through a tool pipeline
(`app/agents/tools.py`):

1. **Analyze image** — `vision_client.analyze()` returns raw JSON, validated
   against the strict `HermesOutput` Pydantic schema. **Nothing unvalidated is
   ever written to the database.**
2. **Persist observation** — `observation_service.create_observation()` runs
   **lot matching** and **weather enrichment** inside the same transaction, and
   writes an **immutable `model_outputs` row** (never overwritten).
3. **Determine missing fields** — e.g. no lot match → ask for the lot; no GPS →
   ask for location.
4. **Escalation decision** — delegated to the escalation engine (rules +
   cooldown).
5. **Reply** — a concise summary + recommended next step + action buttons.

The vision prompt (`app/agents/prompts.py`) instructs the model to report only
observable symptoms, use uncertainty, never give a final diagnosis, and never
recommend any chemical product or dosage.

**Swapping the model:** point `VISION_*` at any OpenAI-compatible multimodal
endpoint (OpenAI, Azure, a local vLLM, or a Claude-compatible gateway). A future
agave-specific classifier just implements the same `analyze(...) -> dict`
contract.

---

## How weather enrichment works

`app/services/weather_service.py` calls **Open-Meteo** (no API key) for current
conditions plus 7-day precipitation. It normalizes temperature, humidity,
precipitation, wind, and recent rain, and derives simple **heat_risk** and
**drought_risk** flags. A `weather_snapshots` row is linked to the observation.
Network failures return `None` so the pipeline never breaks.

---

## How escalation rules work

`app/services/escalation_service.py` escalates automatically when **any** of:

- severity is **high** or **critical**;
- `escalation_recommended` is true **and** confidence ≥ **0.75**;
- the same lot has **3+ medium**-severity observations within **10 days**;
- the caption contains urgent terms (`urgent`, `urgente`, `escalar`,
  `plaga fuerte`, `riesgo alto`, `se está extendiendo`, `revisar hoy`);
- a human presses **Escalate**.

**Anti-spam:** a duplicate escalation for the same **lot + suspected issue** is
suppressed within `ESCALATION_COOLDOWN_HOURS`. The message includes severity,
lot, suspected issue, AI summary, recommended next step, image link, timestamp,
and location. Dispatch prefers **WhatsApp**; falls back to **Telegram**. Every
attempt is recorded in `escalations`.

---

## The dashboard

Streamlit app (`dashboard/app.py`) — **photos first**:

- **Overview** — totals, severity & issue breakdowns, needs-review count,
  escalations sent, human verification rate, recent photos, lot risk ranking.
- **Photo Gallery** — thumbnails filtered by lot, severity, issue, date range.
- **Observation Detail** — large photo, AI summary, symptoms, severity,
  confidence, weather, location, lot, verification status, correction notes,
  escalation history, plus Verify / Correct / Escalate actions.
- **Lots** — code, farm, recent observations, photo history, severity
  breakdown, repeated issues, last inspection.
- **Map** — geolocated observations with severity and summary.

---

## API reference

```
GET    /health

POST   /webhooks/telegram
GET    /webhooks/whatsapp           (verification handshake)
POST   /webhooks/whatsapp

GET    /observations                ?severity&suspected_issue&lot_id&needs_review
GET    /observations/{id}
POST   /observations                (runs the Hermes pipeline on image_url)
PATCH  /observations/{id}/verify
PATCH  /observations/{id}/correct
POST   /observations/{id}/escalate

GET    /dashboard/summary
GET    /dashboard/recent-observations
GET    /dashboard/gallery
GET    /dashboard/lot-risk-ranking
GET    /dashboard/map-points

GET    /lots
POST   /lots
GET    /lots/{id}
GET    /lots/{id}/observations

# --- Field-intelligence modules (v0.2) ---
GET    /api/passports
POST   /api/passports
GET    /api/passports/{id}
PATCH  /api/passports/{id}
GET    /api/passports/{id}/photos/compare      (before/after)

GET    /observations/queue/needs-review        (human validation queue)
PATCH  /observations/{id}/validate             (confirm | correct | reject)

GET    /api/tasks
POST   /api/tasks
PATCH  /api/tasks/{id}
GET    /api/tasks/queue/overdue

GET    /api/alerts
POST   /api/alerts/escalate                    (manual escalation)
PATCH  /api/alerts/{id}/read

GET    /api/weather/current
GET    /api/weather/forecast
GET    /api/weather/context

GET    /api/map/zones                           (map-ready markers)

GET    /api/reports/weekly
POST   /api/reports/weekly/generate
```

Interactive docs at `/docs`.

---

## Field-intelligence modules (v0.2)

These extend the core pipeline. When a new image arrives Hermes now: stores it →
analyzes → **upserts an Agave Passport** → creates an Observation (with diagnosis,
confidence, severity) → **applies validation rules** → **auto-creates tasks** →
adds weather context → raises alerts if rules require → everything shows on the
dashboard.

- **Agave Passport** (`AgavePassport`) — persistent memory for a plant/row/
  zone/lot: health status, risk level, photo & observation history, tasks, last
  and next inspection dates. A passport is reused per lot, matched by GPS
  proximity (~50 m), or created fresh.
- **Tasks** (`Task`) — Hermes auto-creates follow-ups (reinspect, validate,
  closer photo). **Dangerous/expensive actions (treatments) are detected and
  gated `needs_approval` — never auto-approved.** Humans manage status.
- **Alerts & notifications** — a provider abstraction (`notification_service`)
  with **whatsapp / telegram / dashboard / console** channels. No credentials
  required locally (falls back to console + always records the `Alert` for the
  dashboard). Triggers: high/urgent severity, repeated zone issue, low
  confidence + high severity, overdue tasks, weather risk, manual escalation.
- **Weather** — provider pattern (`MockWeatherProvider`, Open-Meteo, optional
  OpenWeather via `WEATHER_API_KEY`). Adds forecast, frost/heat risk, and
  **treatment warnings** ("Avoid applying treatment tomorrow — rain expected").
  Never breaks the app if no provider/key is configured.
- **Before/After comparison** — fetches a passport's photo history and pairs the
  two most recent with a change summary (placeholder now; multimodal visual diff
  is wired as an extension point).
- **Diagnosis confidence + human validation** — every observation carries
  `confidence`, `severity`, `needs_human_review`, `human_validation_status`
  (pending/confirmed/corrected/rejected) and correction fields. Rule: confidence
  < 0.75 **or** high/critical severity → needs review. Corrections are stored
  immutably in `human_validations` as training data; original `model_outputs`
  are never overwritten.
- **Weekly reports** — on-demand (`/api/reports/weekly`), no queue: observations,
  photos, top issues, high-risk zones, open/overdue/completed tasks, weather
  warnings, follow-ups, human corrections, and thumbnails.

### Satellite / NDVI — Version 2 (NOT implemented)

`app/integrations/satellite_provider.py` defines `SatelliteProvider` and
`VegetationIndexService` **interfaces only**, with a clear TODO and no concrete
implementation, no dependency, and no UI. Nothing in the MVP imports it, so it
cannot affect stability. V2 will add NDVI, satellite imagery, vegetation-health
maps, drought-stress detection, and regional monitoring.

---

## Testing

```bash
pip install -r requirements.txt   # or: pip install pytest httpx Pillow ...
pytest -q
```

The suite runs **offline on SQLite** with the stub vision client and stubbed
weather. It covers the Hermes schema, weather normalization/risk, escalation
rules + cooldown, and the full observation flow (create → model output →
weather → escalation; correction preserves the original model output).

---

## Safety notes

- Hermes **assists**; the agronomist makes every final decision.
- Hermes uses **"suspected" / "possible" / "unknown"** and flags
  **needs_human_review** when uncertain.
- Hermes **never** gives a definitive disease diagnosis.
- Hermes **never** recommends a pesticide, herbicide, fungicide, fertilizer, or
  any chemical product or dosage — only inspection/sampling next steps.
- Human corrections are stored as training-quality feedback and the **original
  AI output is preserved** (`model_outputs` is immutable).

---

## Roadmap

- Custom agave **disease/stress classifier** trained on field data
- **YOLO-based** plant/symptom detection
- **Drone imagery** upload
- **Satellite imagery** integration
- **Offline mobile** app mode for low-connectivity fields
- **WhatsApp-first** production deployment
- **PDF report** generation and **weekly automated reports**
- **Role-based access control** and **farm-owner accounts**
- **Multi-farm** support
- **Model training from human corrections** (closing the feedback loop)
- **Predictive lot risk scoring**
```
