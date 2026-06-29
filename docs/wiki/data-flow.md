# Data Flow & Module Boundary (Two Subsystems)

Agave Field is **one FastAPI app on one database** that hosts **two overlapping
domains**. This page is the single, source-grounded definition of where the line
between them sits — what each owns, what they share, and exactly where they
diverge. It expands on the "Two data subsystems" section of
[architecture.md](architecture.md#two-data-subsystems-important); read this page
for the boundary, and architecture.md for the deep per-flow walkthrough.

> Roadmap item 1.3. The boundary used to be implicit (spread across model files
> and `main.py`); this page makes it explicit. The "merge vs. stay separate"
> decision is still **open** — see [the open question](#open-boundary-question).

---

## The two subsystems at a glance

| | **Operations / traceability layer** | **Observation / intake layer** |
|---|---|---|
| Purpose | Planned work-order → execution → review → carbon/audit pipeline (regulated-style field traceability) | Telegram/WhatsApp photo + note intake, observations, tasks, alerts, weekly reports |
| Age | Newer; current focus of `CLAUDE.md` | Older; predates the ops layer |
| Models file | `app/models/operations.py` | `app/models/database.py` |
| Intended users | Agronomist / field-ops manager (admin), field worker (mobile token page), compliance reviewer | Agronomist in the field (chat intake), internal dashboard viewer |

Both layers are DB-agnostic SQLAlchemy 2.0 models registered on the same `Base`
(`app/db.py`), and `alembic/env.py` imports **both** modules so a single
migration history covers all 24 tables.

---

## 1. Operations / traceability layer

- **Models** (`app/models/operations.py`): `Assignee`, `Product`, `Activity`,
  `WorkOrder`, `WorkOrderItem`, `ExecutionRecord`, `PhotoEvidence`,
  `OpsWeatherSnapshot`, `Review`, `TimelineEvent`, `AuditLog`.
  Tables: `assignees, products, activities, work_orders, work_order_items,
  execution_records, photo_evidence, ops_weather_snapshots, reviews,
  timeline_events, audit_logs` (confirmed in `supabase_schema.sql`).
- **Services** (`app/services/`): `work_order_service`, `execution_service`,
  `review_service`, `carbon_service`, `carbon_report_service`, `audit_service`,
  `catalog_service`, `ops_weather_service`, `timeline_service`.
- **Routes** (`app/main.py:115-131`): `assignee_routes`, `catalog_routes`,
  `audit_routes`, `work_order_routes`, `ops_photo_routes`, `completion_routes`,
  `review_routes`, `timeline_routes`, `carbon_routes`, `execution_routes`,
  `system_routes`.
- **RBAC** (applied at include time): `require_staff` (admin/agronomist) for
  catalogs/assignees/work-orders/audit/execution/system; `require_reviewer` for
  review/timeline/carbon; **public token-based** for `ops_photo` upload and the
  `completion` mobile page. (`app/main.py:119-131`.)

## 2. Observation / intake layer

- **Models** (`app/models/database.py`): `User`, `FieldObservation`,
  `ModelOutput`, `WeatherSnapshot`, `Escalation`, `Task`, `Alert`,
  `HumanValidation`, `WeeklyReport` (plus the **shared agronomy base** below).
  Tables: `users, field_observations, model_outputs, weather_snapshots,
  escalations, tasks, alerts, human_validations, weekly_reports`.
- **Services** (`app/services/`): `observation_service`, `task_service`,
  `escalation_service`, `weather_service`, `lot_matching_service`,
  `report_service`, `passport_service`, `image_service`, `comparison_service`,
  `dashboard_service`, `notification_service`.
- **Routes** (`app/main.py:103-114`): `telegram_routes`, `whatsapp_routes`,
  `observation_routes`, `task_routes`, `alert_routes`, `weather_routes`,
  `report_routes`, `dashboard_routes`.
- **Hermes agent** (`app/agents/hermes_agent.py`, `tools.py`, `prompts.py`)
  orchestrates Telegram intake. **AI/vision is gated OFF.**
  `telegram_routes.py:57` branches on `settings.enable_ai_image_analysis`
  (`ENABLE_AI_IMAGE_ANALYSIS=false` by default): the MVP path
  (`observation_service.create_evidence_record`) just stores the photo as
  historical evidence and asks the human for a note — **no LLM/CV is invoked**.
  The Hermes path is dead code reserved for a future version.

---

## Shared foundation

Both layers stand on the same base; neither owns it exclusively:

- **Agronomy base entities** (defined in `app/models/database.py`):
  `Farm`(=field) → `Lot` → `FieldZone`(=zone), and `AgavePassport`. Operations
  `WorkOrder`/`PhotoEvidence`/`TimelineEvent` reference these by FK or loose id;
  observations also attach to them. Routes that serve this base —
  `lot_routes`, `passport_routes`, `map_routes` — are registered **without** the
  ops RBAC block (`app/main.py:107-114`) because they belong to both.
- **`/media` object storage** — both layers upload through
  `app/integrations/storage_client.py` (local mount at `/media`, or S3/Supabase).
  Observation photos go through `image_service.store_image_*`; ops evidence goes
  through `image_service.store_image_bytes` → `PhotoEvidence`.
- **The FastAPI app + RBAC** — one `app/main.py`, one `app/api/auth.py` API-key
  model, one CORS config.
- **The database** — one `Base`/engine (`app/db.py`), one Alembic history
  (baseline `49fa233d5c67`), Supabase Postgres in prod / SQLite in tests.

---

## Connection points and divergences

**Connected through:** the shared agronomy base (a lot/zone/passport is the same
row for both layers) and the shared `/media` store. That is the entire seam — the
two layers are otherwise loosely coupled with no cross-layer service calls.

**Where they deliberately DIVERGE** (the important part — these are separate by
construction, not by accident):

| Concern | Operations layer | Observation layer |
|---|---|---|
| **Weather** | `OpsWeatherSnapshot` → table `ops_weather_snapshots`, captured once per execution submit by `ops_weather_service` | `WeatherSnapshot` → table `weather_snapshots`, captured by `weather_service` on the intake/observation side |
| **Timeline / history** | `TimelineEvent` → table `timeline_events` (polymorphic `entity_type`+`entity_id`, written by `timeline_service`) | observation history = `field_observations` rows + their status/event_type changes; no `timeline_events` rows |
| **Audit** | append-only `audit_logs` via `audit_service` on every ops action | not wired into the ops `audit_service` |

Consequence: a single field/lot/passport's "full history" is **split across two
stores** — ops `timeline_events` plus observation `field_observations`. There is
**no unified entity timeline** that merges both today. That merge is
**roadmap 1.2**, tracked in
[missing-features-gaps.md](missing-features-gaps.md#overlapping-subsystems);
reference it, do not implement it here.

---

## Which layer do I extend?

Decision guide for future agents:

| If you are building… | Extend the… | Touch these files |
|---|---|---|
| Work orders, checklist items, assignees, catalogs (products/activities) | **Operations layer** | `operations.py`, `work_order_service`, `catalog_service`, `*_routes` under the staff RBAC block |
| Execution submission, mobile completion page, photo evidence, GPS/weather at submit | **Operations layer** | `execution_service`, `completion_routes`, `ops_photo_routes`, `ops_weather_service` |
| Reviewer approve/reject/correction, revision history | **Operations layer** | `review_service`, `review_routes` |
| Carbon factor snapshots, planned/actual carbon, carbon reports | **Operations layer** | `carbon_service`, `carbon_report_service`, `carbon_routes` |
| Audit trail for any of the above | **Operations layer** | `audit_service` (call it; never bypass) |
| Telegram/WhatsApp intake, field observations, evidence-only photo records | **Observation layer** | `telegram_routes`/`whatsapp_routes`, `observation_service`, `image_service` |
| Tasks, alerts, escalations, weekly reports, the Streamlit-facing dashboard reads | **Observation layer** | `task_service`, `escalation_service`, `notification_service`, `report_service`, `dashboard_service` |
| Farms/lots/zones/passports themselves (geometry, passports) | **Shared foundation** | `database.py` base entities, `lot_routes`, `passport_routes`, `map_routes` |

Rule of thumb: **planned, controlled, regulated, carbon/audit-bearing → operations
layer. Inbound, human-reported, ad-hoc field signal → observation layer.** When in
doubt, follow the FK: if the record needs a `work_order_id`/`execution_record_id`,
it is operations.

---

## Data-flow walkthroughs (tight — see architecture.md for the deep version)

### Observation layer: intake → record
1. Photo + caption + GPS arrive via Telegram/WhatsApp webhook
   (`telegram_routes` / `whatsapp_routes`).
2. `image_service` stores the image to `/media`; with
   `ENABLE_AI_IMAGE_ANALYSIS=false`, `observation_service.create_evidence_record`
   writes a `FieldObservation` (evidence-only, no AI) and the bot asks the human
   for a note / event type.
3. Optional `weather_service` snapshot (`weather_snapshots`); tasks/alerts/
   escalations and weekly reports are derived by their services; the Streamlit
   dashboard reads via `dashboard_service`.

### Operations layer: work order → completion → execution → review → carbon/audit
1. Admin creates a `WorkOrder` (+ items, with **locked carbon snapshots**) and
   sends a tokenized link (`work_order_service`).
2. Worker opens the public mobile page (`completion_routes`), uploads photos
   (`ops_photo_routes` → `PhotoEvidence`), and submits.
3. `execution_service.submit_execution` captures an `OpsWeatherSnapshot`, computes
   **actual carbon** from the locked factor, writes an **immutable**
   `ExecutionRecord` (revisions chain via `is_revision_of_id`), and adds a
   `TimelineEvent`.
4. Reviewer approves/rejects/requests-correction (`review_service` → `Review`
   rows; the execution record is never mutated).
5. Carbon/audit reads via `carbon_report_service` and append-only `audit_service`.

The full step-by-step (token hashing, completeness gating, override math) lives in
[architecture.md → Core request flows](architecture.md#core-request-flows).

---

## Open boundary question {#open-boundary-question}

It is **not yet decided** whether the two layers should eventually **merge** into
one domain or remain **separate products sharing a DB**. Tracked as open question
#3 in [missing-features-gaps.md](missing-features-gaps.md#open-questions). What is
decided and documented here: they currently coexist intentionally, share only the
agronomy base + `/media`, and keep **separate weather tables and timelines**. The
concrete near-term gap is the **unified entity timeline** (roadmap 1.2) that would
merge ops `timeline_events` with observation history into one read. Until that
exists, treat a lot/passport's history as living in two places.
