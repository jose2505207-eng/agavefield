# Missing Features / Gaps

This page is the heart of the wiki: what the **enterprise production goal**
(`CLAUDE.md`) calls for versus what actually exists in source. Each gap is
grounded in a file/symbol (or its absence). **Several items the task brief assumed
were missing are in fact already implemented** — those are recorded under
"Already implemented" so future agents don't rebuild them.

Legend: ✅ implemented · 🟡 partial · ❌ missing/not found in source.

---

## ✅ Already implemented (do NOT rebuild)

| Capability | Where | Evidence |
|---|---|---|
| Tokenized task links + expiry | `work_order_service.send_work_order` / `find_by_token` | random `token_urlsafe(32)`, **only SHA-256 hash stored** (`secure_access_token_hash`), `secure_link_expires_at` (default 14d), expiry checked on resolve |
| Soft deletes | `WorkOrder.deleted_at`; `catalog_service.delete_or_deactivate_*` | list filters `deleted_at IS NULL`; catalog rows with history are deactivated not deleted |
| Immutable execution records | `execution_service.submit_execution` | never overwrites; new record per submit |
| Revision history | `ExecutionRecord.is_revision_of_id`; `review_service.revision_history` | revision chain walked oldest→newest |
| Review / approval flow | `review_service` approve/reject/request_correction; `review_routes` | one `Review` row per decision; execution data untouched |
| Email delivery + provider abstraction | `email_client` | console/smtp/sendgrid/resend, graceful fallback |
| Storage abstraction | `storage_client` | local / S3 (Supabase) with fallback |
| Weather abstraction | `weather_provider` + `ops_weather_service` | Open-Meteo / mock; snapshot per submission |
| Audit logging | `audit_service` across services | append-only, before/after values |
| RBAC | `app/api/auth.py` | API-key roles, open-mode fallback |
| Mobile-first worker page | `completion_routes` | self-contained HTML, token-gated, no admin UI |
| Carbon factor snapshots + override | `carbon_service`, `work_order_service`, `execution_service.override_carbon` | locked factors, partial/missing-data states, manual override with reason |
| Server-side validation | Pydantic schemas (`ops_schemas.py`) on all bodies | |
| Completeness states (loading/empty/error/success) | dashboard + completion warnings | |

---

## 🟡 / ❌ Real gaps

### Weak env validation — ✅ RESOLVED (2026-06-28) {#weak-env-validation}
Implemented `config_problems()` + `validate_runtime()` in `app/config.py`, called
from the `app/main.py` lifespan. In production (`APP_ENV` in
`production|prod|staging`) it **refuses to start** on critical issues: a default/
blank `SECRET_KEY`, or no RBAC API keys configured. It warns (non-fatal) on
localhost `DATABASE_URL`/`APP_BASE_URL` and provider/credential mismatches
(e.g. `EMAIL_PROVIDER=smtp` with blank `SMTP_HOST`). In dev/test nothing raises,
so the app still boots on empty defaults. Verified: dev boots, misconfigured prod
raises, configured prod boots.

### Migrations / schema authority — ✅ RESOLVED (2026-06-28) {#no-real-migrations}
**Alembic is now the source of truth for the schema.** A baseline revision
`49fa233d5c67` (`alembic/versions/`) captures all 24 tables (agronomy + ops)
exactly as the ORM defines them — `alembic upgrade head` on an empty DB reproduces
what `supabase_schema.sql` builds (verified: `alembic check` reports no drift).
`alembic/env.py` now imports **both** `app.models.database` and
`app.models.operations`, so autogenerate sees every table. `supabase_schema.sql`
is kept **for reference only**. CI (`.github/workflows/ci.yml`) runs
`alembic upgrade head && alembic check` to **fail on any model/migration drift**,
forcing future schema changes through versioned migrations.
- **Existing Supabase DBs** (already built from `supabase_schema.sql`) must be
  marked at the baseline with `alembic stamp 49fa233d5c67` **instead of**
  `upgrade head`, so the baseline isn't re-applied over existing tables. New/empty
  DBs use `alembic upgrade head`. See [Setup & Deploy](setup-env-deploy.md#database--schema).
- `init_db()` (`create_all`) remains a **dev/test convenience only**; production
  schema changes go through Alembic.

### Frontend direction — ✅ RESOLVED (2026-06-28) {#two-frontends}
**Decision: the Next.js `web/` app is the canonical admin frontend.** `CLAUDE.md`
has been updated — the "NOT a TypeScript/Next.js project" prohibition is replaced
with: backend stack is fixed (Python/FastAPI/SQLAlchemy/Pydantic), and new admin/
ops UI is built in `web/` (a thin client over `/api/*`, no business logic in the
frontend). The **Streamlit dashboard** (`dashboard/app.py`) is now **legacy/
internal** — still supported for quick internal views, but not the surface for new
admin work. The mobile worker completion page (`completion_routes.py`) is
unchanged. See [Dashboard & Mobile](dashboard-and-mobile.md).

### Overlapping subsystems / weak integration seam {#overlapping-subsystems}
🟡 The older **observation/Telegram** layer and the newer **operations/work-order**
layer coexist with **separate weather tables** (`weather_snapshots` vs
`ops_weather_snapshots`) and **separate timelines/history**. A lot/passport's
"full history" is split across both.
- **Impact:** no single unified entity timeline; carbon/traceability reporting may
  miss observation-side events. **Fix:** a unified timeline read that merges both,
  or a documented boundary stating they are intentionally separate.

### Open photo-listing endpoint — ✅ RESOLVED (2026-06-28) {#open-photo-listing}
`GET /api/photos` (`ops_photo_routes.py`) now carries a route-level
`dependencies=[Depends(require_staff)]`, so evidence/GPS listing requires
admin/agronomist in a keyed deployment. The `POST /api/photos/upload` route stays
**token-authorized** (workers must still upload from the mobile page), so the two
concerns are now correctly separated without splitting the router.

### Worker re-notification on correction — ✅ RESOLVED (2026-06-28) {#no-correction-notification}
`request_correction` now takes an opt-in `notify` flag
(`POST /api/review/{id}/request-correction?notify=true`). When set, it calls
`work_order_service.notify_correction`, which mints a **fresh** completion link
(rotating the old token), emails the assignee a correction message including the
reviewer's notes, and audit-logs `notify_correction` + a `correction_link_sent`
timeline event. **Default stays off** so the original token keeps working for the
existing resubmit flow. The route strips the raw token/link from the API response
(exposes `dev_link` only in console mode), matching the `/send` policy.

### CORS configurability — ✅ RESOLVED (2026-06-28) {#cors}
CORS origins are now driven by `CORS_ALLOW_ORIGINS` (comma-separated, default
`*`). `app/main.py` reads `settings.cors_origins`; production deploys set explicit
origins, and `config_problems` warns when production still uses `*`. Methods/
headers remain `*` (acceptable under the token/API-key model).

### No Season or lifecycle model {#no-season-or-lifecycle-model}
❌ `WorkOrder.season_id` is a bare integer ("no Season table in MVP"). Carbon can
be grouped by season id (`/api/carbon/by-season`) but there is **no `Season`
entity**, and **no agave lifecycle-stage model** (planting → maturation → jima/
harvest over ~7 years). The mission is long-horizon traceability, but the schema
has no first-class multi-year lifecycle/maturity milestones per `AgavePassport`.
- **Impact:** the headline ~7-year-lifecycle carbon/traceability story is not yet
  representable as structured data. **Fix:** see [roadmap Phase 2](future-scope-roadmap.md).

### Testing / CI — ✅ CI ADDED (2026-06-28) {#testing-gap}
80 test functions now exist and **pass** (78 original + 2 new for the link
generator); the full suite was executed in a scratch venv (`80 passed`). A CI
workflow was added at `.github/workflows/ci.yml` (Python 3.12, installs
`requirements.txt`, runs `pytest -q` on push/PR). Note: the base image still lacks
the Python deps, so contributors must `pip install -r requirements.txt` locally
before running `pytest`.

### Misc smaller gaps
- 🟡 `image_service` thumbnailing relies on Pillow; no verification that S3 stores
  both image + thumbnail keys consistently (worth a targeted test).
- 🟡 No rate limiting / brute-force protection on token endpoints (token entropy is
  high — 32 bytes — so low risk, but no lockout/throttle exists).
- 🟡 `init_db()` is best-effort and swallows errors at startup; a genuinely broken
  schema would surface only at first query, not at boot.

---

## Open questions {#open-questions}
1. ✅ **Frontend direction — RESOLVED (2026-06-28):** the Next.js `web/` app is the
   canonical admin frontend; Streamlit is legacy/internal. `CLAUDE.md` updated.
2. ✅ **Schema authority — RESOLVED (2026-06-28):** Alembic is authoritative
   (baseline `49fa233d5c67`); `supabase_schema.sql` is reference only.
3. **Subsystem boundary — NOW DOCUMENTED (2026-06-28):** the boundary is defined
   in [data-flow.md](data-flow.md) (owning models/services/routes per layer, the
   shared agronomy + `/media` foundation, the separate weather/timeline
   divergences, and a "which layer do I extend?" guide). The **merge vs. stay
   separate** product decision remains **open**; the concrete near-term gap is the
   unified entity timeline (roadmap 1.2, see
   [overlapping subsystems](#overlapping-subsystems)).
4. **Deployment target confirmation:** `web/` is the canonical admin frontend on a
   separate Vercel project (root `web/`) — confirm it is actually deployed/live as a
   third deploy alongside the API (Vercel) and Streamlit dashboard (Streamlit Cloud).

Record answers in this file and in `CLAUDE.md` when resolved.
