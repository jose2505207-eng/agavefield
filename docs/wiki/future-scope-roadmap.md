# Future Scope / Roadmap

Phased, prioritized future work, aligned with the mission (long-horizon ~7-year
agave-lifecycle carbon + traceability, FDA-style record integrity) and constrained
by `CLAUDE.md`: **no stack/ORM swap, no Next.js mandate, no AI image analysis in
the MVP, additive/reversible changes only.** Each item references a gap from
[Missing Features / Gaps](missing-features-gaps.md).

Effort: S (<1 day) · M (1–3 days) · L (1–2 weeks). Impact: ⭐–⭐⭐⭐.

---

## Phase 0 — Harden what already works (near-term, do first)
Goal: make the existing, fairly complete system production-safe. Low risk, high
leverage.

| # | Item | Effort | Impact | Depends on |
|---|---|---|---|---|
| 0.1 | **Env validation / fail-fast** — ✅ DONE (`config.validate_runtime` in `main.py` lifespan) | S | ⭐⭐⭐ | — |
| 0.2 | **Lock down `GET /api/photos`** behind `require_staff` — ✅ DONE (route-level dep; upload stays token-public) | S | ⭐⭐⭐ | — |
| 0.3 | **CI workflow** running `pytest -q` — ✅ DONE (`.github/workflows/ci.yml`) | S | ⭐⭐⭐ | deps install |
| 0.4 | **Tighten CORS** to known origins in prod — ✅ DONE (`CORS_ALLOW_ORIGINS`, prod warning) | S | ⭐⭐ | 0.1 |
| 0.5 | **Worker re-notification on correction** — ✅ DONE (`request_correction?notify=true` → `notify_correction` re-emails a fresh link) | M | ⭐⭐ | email_client |
| 0.6 | **Schema authority → Alembic** — ✅ DONE (baseline `49fa233d5c67` captures all 24 tables; CI runs `alembic check`; `supabase_schema.sql` now reference-only) | M | ⭐⭐⭐ | — |

> **Manual link sharing (related to the worker flow):** a `POST /api/work-orders/
> {id}/link` endpoint now generates/refreshes a shareable completion link **without
> sending email** (`work_order_service.generate_link`), for WhatsApp/QR/printout
> delivery. The link opens the existing mobile completion page (tasks + photo
> inputs).

**Why first:** every item closes a concrete, source-confirmed gap without new
surface area. 0.1/0.2/0.6 directly protect the traceability/security guarantees the
product sells.

---

## Phase 1 — Resolve structural ambiguities
Goal: stop divergence before building more.

| # | Item | Effort | Impact | Depends on |
|---|---|---|---|---|
| 1.1 | **Frontend direction** — ✅ DONE: `web/` (Next.js) adopted as canonical admin frontend; Streamlit relegated to legacy/internal; `CLAUDE.md` updated | S (decision) | ⭐⭐⭐ | stakeholder |
| 1.2 | **Unified entity timeline** read that merges observation-layer history with ops `timeline_events` per lot/passport | M | ⭐⭐ | subsystem boundary call |
| 1.3 | **Document the subsystem boundary** — ✅ DONE (`docs/wiki/data-flow.md` + `CLAUDE.md` "Module boundary" section; divergences confirmed by grep) | S | ⭐⭐ | 1.2 |

**Why:** building Phase 2 lifecycle features on top of an undecided frontend /
split-timeline foundation would multiply rework. With 0.6 (Alembic) and 1.1
(frontend) now settled, the remaining structural item is the subsystem boundary
(1.2/1.3) before Phase 2.

> **Next build-out target for the canonical frontend:** the placeholder sections
> under `web/app/(app)/` (`work-orders`, `review`, `execution`, `fields`, `catalogs`,
> `carbon`, `timeline`, `settings`) — wire them to the existing `/api/*` endpoints.

---

## Phase 2 — Long-horizon lifecycle & carbon (the mission)
Goal: make the ~7-year agave story representable and reportable. Additive models +
services only.

| # | Item | Effort | Impact | Depends on |
|---|---|---|---|---|
| 2.1 | **`Season` entity** — 🟡 PARTIAL: `seasons` table + history-safe CRUD (`/api/seasons`) added additively (migration `6e1219fdb59c`). Remaining: promote `WorkOrder.season_id` to a real DB-level FK + backfill (deferred — needs a batch ALTER, kept service-layer for now) | M | ⭐⭐ | 0.6 |
| 2.2 | **Agave lifecycle/maturity model**: stages (planting→maturation→jima/harvest), milestones per `AgavePassport`, year markers | L | ⭐⭐⭐ | 2.1 |
| 2.3 | **Multi-year carbon aggregation** per passport/lot/season (cumulative kgCO2e across the lifecycle) extending `carbon_report_service` | M | ⭐⭐⭐ | 2.1, 2.2 |
| 2.4 | **Lifecycle timeline view** in the chosen frontend (years-long history with evidence + carbon) | M | ⭐⭐ | 1.1, 2.2 |
| 2.5 | **Harvest/jima traceability** (link a harvest event back through the full work-order/execution/carbon chain to the passport) | M | ⭐⭐⭐ | 2.2 |

**Why:** this is the headline differentiator. The plumbing (immutable records,
locked carbon snapshots, evidence, audit) already exists; Phase 2 makes it
*longitudinal*.

---

## Phase 3 — Compliance & reporting depth
Goal: turn FDA-style principles into exportable, audit-ready artifacts.

| # | Item | Effort | Impact |
|---|---|---|---|
| 3.1 | **Exportable audit/traceability report** (per work order / passport / season → PDF or signed JSON bundle: records, evidence URLs, factor snapshots, reviewer identities) | L | ⭐⭐⭐ |
| 3.2 | **Reviewer SLA / correction-due tracking** surfaced as a queue (use existing `correction_due_date`) | S | ⭐⭐ |
| 3.3 | **Audit log integrity** (hash-chaining or periodic tamper-evidence on `audit_logs`) | M | ⭐⭐ |
| 3.4 | **Role expansion** (per-field-worker accounts beyond per-order tokens, optional) | M | ⭐ |

---

## Phase 4 — Scale & observability
| # | Item | Effort | Impact |
|---|---|---|---|
| 4.1 | Structured logging + error tracking (Sentry-style) across services | M | ⭐⭐ |
| 4.2 | Rate limiting / throttling on token + webhook endpoints | S | ⭐ |
| 4.3 | Background job runner for email/weather (decouple from request path; serverless-safe) | M | ⭐⭐ |
| 4.4 | Storage lifecycle (thumbnail verification, orphaned-evidence cleanup that respects "no hard delete of evidence") | M | ⭐ |

---

## Explicitly OUT of scope (per `CLAUDE.md`)
- ❌ LLM / computer-vision image analysis on upload (`ENABLE_AI_IMAGE_ANALYSIS`
  stays `false`). Revisit only in a "Version 2+" once enough human-labeled history
  exists — and as a *gated, additive* path, never the default.
- ❌ Framework/stack/ORM swap; no replacing FastAPI/SQLAlchemy/Streamlit.
- ❌ Hard deletes of execution/product/carbon/evidence records.
- ❌ Mutating historical carbon snapshots; fabricated factors; external carbon APIs.
- ❌ Whole-app rewrites — small, safe, reversible increments only.

## Suggested near-term sequence (the "do this next" list)
1. Phase 0.1 (env validation) + 0.2 (photo listing auth) + 0.3 (CI) — a one-PR
   security/quality hardening batch.
2. Phase 0.6 + 1.1 — resolve schema authority and frontend direction (decisions
   that unblock everything downstream).
3. Phase 2.1 → 2.3 — deliver the multi-year carbon/lifecycle story the mission
   promises.
