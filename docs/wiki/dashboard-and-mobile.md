# Dashboard & Mobile Task Page

Three user-facing surfaces exist. All read/write through the FastAPI backend.

> **Canonical admin frontend = the Next.js `web/` app (see §3).** Build new admin/
> ops screens there. The Streamlit dashboard below is **legacy/internal** — still
> supported for quick internal views, but not where new admin UI work goes.

## 1. Streamlit admin dashboard (`dashboard/app.py`, 735 lines) — legacy/internal

The original "field command center," now a legacy internal surface. Pure HTTP
client — reads everything from
`API_BASE_URL` (default `http://localhost:8000`) via `requests`, sending an
optional `X-API-Key` header (`_HEADERS`).

- Config: `st.set_page_config(... layout="wide")`; sidebar radio navigation.
- Helper layer: `api_get` / `api_patch` / `api_post` wrap `requests` with timeouts
  and error handling.
- Pages (from `st.header(...)` blocks):
  - **Field Overview**, **Photo Gallery**, **Field Record Detail**
  - **Lots**, **Agave Passports**, **Map / Zone Overview**
  - **Tasks**, **Alerts**, **Weather**, **Before / After Comparison**
  - **Field Notes Review**, **Weekly Report**
  - **Work Orders** (All + "Generate work order" tab)
  - **Review Queue**, **Timeline**, **Carbon Footprint**
  - **Evidence Gallery**, **Audit Trail**
  - **Settings / Environment Status** (renders feature/env readiness rows)
- Dependencies: `dashboard/requirements.txt` (streamlit, pandas, requests) — kept
  **out** of the API `requirements.txt` so the API stays within Vercel's size limit.

UX standard (`CLAUDE.md`): always show loading/empty/error/success states; never
fake data — if there is none, say "data not available."

## 2. Mobile worker completion page (`app/api/completion_routes.py`)

A **self-contained mobile-first HTML page** served by the API at
`GET /work-orders/complete/{token}`. No build step, no admin assets, inline CSS/JS.

- Token-gated: resolves the work order via `work_order_service.find_by_token`
  (hash match + expiry). Invalid/expired → a friendly 404 `_ERROR_PAGE`.
- Renders each checklist item with actual surface/dose/note inputs and a camera
  file input (`capture="environment"`).
- Captures GPS via `navigator.geolocation`.
- Uploads each photo immediately to `POST /api/photos/upload` (token in form body).
- Submits the whole order to `POST /api/work-orders/complete/{token}/submit`;
  shows a success state and surfaces any completeness warnings (missing GPS/note/
  photos) returned by the backend.

This satisfies the `CLAUDE.md` rule that the worker page must be mobile-first and
must **not** expose the admin dashboard.

## 3. Next.js admin frontend (`web/`) — CANONICAL

The canonical admin/ops frontend (decision 2026-06-28). A TypeScript/Next.js
(App Router) app consuming the FastAPI backend. Stack: Next.js · TypeScript ·
Tailwind · lucide-react (`web/README.md`). New admin/ops UI is built here.

- Calls go through a **same-origin proxy** route `web/app/proxy/[...path]/route.ts`
  which injects the RBAC API key **server-side** (`web/lib/api.ts` → `/proxy/...`).
- **Demo-mode fallback**: when the API is empty/unreachable, read views render
  realistic demo data with a "Demo data" badge and switch to live data when present
  (`web/lib/demo.ts`, `web/components/demo-badge.tsx`).
- Sections (under `web/app/(app)/`): dashboard (`page.tsx`), `work-orders`,
  `review`, `execution`, `fields`, `catalogs`, `carbon`, `timeline`, `settings`.
  Plus a worker page `web/app/complete/[token]/page.tsx`.
- Per its README, **Dashboard is built; the rest are purposeful placeholders** for
  later phases — those placeholder sections are the natural next build-out targets.
- `CLAUDE.md` has been updated to make `web/` the canonical admin frontend (backend
  stack stays fixed; the frontend is a thin client over `/api/*`).

## Which frontend should I touch?
- **New admin/ops UI → the Next.js `web/` app.** Add/replace the placeholder sections
  under `web/app/(app)/`; keep all logic in the FastAPI backend (the frontend only
  calls `/api/*` via the server-side proxy).
- **Streamlit dashboard** (`dashboard/app.py`) is legacy/internal — use only for quick
  internal views; avoid investing new admin features here.
- **Worker flow:** the **completion page** in `completion_routes.py` is the production
  path; the Next.js `web/complete/[token]` is the matching frontend implementation.
