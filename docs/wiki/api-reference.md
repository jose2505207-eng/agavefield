# API Route Reference

Every router registered in `app/main.py` and the endpoints found in `app/api/*`.
Auth column reflects the router-level dependency applied at include time
(`require_staff` = admin/agronomist, `require_reviewer` = reviewer+, **open in dev
when no API keys are configured**). Token = per-work-order completion token.

## System / health
| Method · Path | Source | Auth |
|---|---|---|
| `GET /health` | `app/main.py` | public |
| `GET /api/system/status` | `system_routes.py` | staff |

## Catalogs (`catalog_routes.py`, prefix `/api`) — staff
| Method · Path |
|---|
| `GET /api/products`, `POST /api/products`, `PATCH /api/products/{id}`, `DELETE /api/products/{id}` |
| `GET /api/activities`, `POST /api/activities`, `PATCH /api/activities/{id}`, `DELETE /api/activities/{id}` |

`DELETE` is **deactivate-or-soft-delete** via `catalog_service`, not a hard delete.

## Assignees (`assignee_routes.py`) — staff
`GET ""`, `POST ""`, `PATCH /{assignee_id}`, `DELETE /{assignee_id}`

## Seasons (`season_routes.py`, prefix `/api/seasons`) — staff
`GET ""`, `POST ""`, `PATCH /{season_id}`, `DELETE /{season_id}` (history-safe:
deactivate-or-soft-delete via `season_service`, audit-logged). First-class season
records; `WorkOrder.season_id` references `seasons.id` at the service layer (no
DB-level FK yet — see [roadmap 2.1](future-scope-roadmap.md)).

## Work orders (`work_order_routes.py`) — staff
| Method · Path | Purpose |
|---|---|
| `GET ""` | list (excludes soft-deleted) |
| `GET /{id}` | detail (`WorkOrderDetail`) |
| `POST ""` | create with locked carbon snapshots |
| `PATCH /{id}` | update |
| `POST /{id}/duplicate` | clone to draft (re-snapshot carbon) |
| `POST /{id}/link` | **generate/refresh a shareable completion link (no email)** — for WhatsApp/QR/printout; rotates the token |
| `POST /{id}/send` | generate token, email assignee, mark sent |

## Worker completion (`completion_routes.py`) — public, token
| Method · Path | Purpose |
|---|---|
| `GET /work-orders/complete/{token}` | self-contained mobile HTML page |
| `GET /api/work-orders/complete/{token}/data` | token-validated JSON (for Next.js page) |
| `POST /api/work-orders/complete/{token}/submit` | create immutable execution records |

## Photo evidence (`ops_photo_routes.py`, prefix `/api/photos`)
| Method · Path | Auth | Note |
|---|---|---|
| `POST /api/photos/upload` | token (form field) | stores to object storage + `PhotoEvidence` |
| `GET /api/photos` | **staff** (route-level `require_staff`) | listing by work_order/execution/lot |

## Execution (`execution_routes.py`) — staff
`GET ""`, `GET /{id}`, `POST /{id}/carbon-override`

## Review (`review_routes.py`, prefix `/api`) — reviewer+
| Method · Path |
|---|
| `GET /api/review-queue` |
| `POST /api/review/{id}/approve` |
| `POST /api/review/{id}/reject` |
| `POST /api/review/{id}/request-correction` (opt-in `?notify=true` re-emails the worker a fresh link) |
| `GET /api/review/{id}/revisions` |

## Timeline (`timeline_routes.py`) — reviewer+
`GET /api/timeline`, `GET /api/fields/{id}/timeline`, `GET /api/lots/{id}/timeline`,
`GET /api/zones/{id}/timeline`

## Carbon (`carbon_routes.py`, prefix `/api/carbon`) — reviewer+
`/summary`, `/by-season`, `/by-activity`, `/by-product`, `/by-lot`, `/by-field`,
`/missing-data`, `/overrides`

## Audit (`audit_routes.py`, prefix `/api/audit`) — staff
`GET /api/audit/{entity_type}/{entity_id}`

---

## Older intake / agronomy layer (registered without RBAC deps)

### Telegram / WhatsApp webhooks
- `POST /webhooks/telegram` (`telegram_routes.py`)
- `GET /webhooks/whatsapp` (verify), `POST /webhooks/whatsapp` (`whatsapp_routes.py`)

### Observations (`observation_routes.py`)
`GET ""`, `GET /{id}`, `POST ""`, `GET /queue/review`, `PATCH /{id}/review`,
`PATCH /{id}/verify`, `GET /queue/needs-review`, `PATCH /{id}/validate`,
`PATCH /{id}/correct`, `POST /{id}/escalate`

### Lots (`lot_routes.py`)
`GET ""`, `POST ""`, `GET /{id}`, `GET /{id}/observations`

### Passports (`passport_routes.py`)
`GET ""`, `POST ""`, `GET /{id}`, `PATCH /{id}`, `GET /{id}/photos/compare`,
`GET /{id}/timeline`

### Tasks (`task_routes.py`)
`GET ""`, `POST ""`, `PATCH /{id}`, `GET /queue/overdue`

### Alerts (`alert_routes.py`)
`GET ""`, `POST /escalate`, `PATCH /{id}/read`

### Weather (`weather_routes.py`)
`GET /current`, `GET /forecast`, `GET /context`

### Map (`map_routes.py`)
`GET /zones`

### Reports (`report_routes.py`)
`GET /weekly`, `POST /weekly/generate`

### Dashboard (`dashboard_routes.py`)
`GET /summary`, `GET /recent-observations`, `GET /gallery`, `GET /lot-risk-ranking`,
`GET /map-points`

> Interactive OpenAPI docs are available at `/docs` (FastAPI default) when the API
> runs. Request/response schemas live in `app/models/ops_schemas.py` (ops layer)
> and `app/models/schemas.py` (agronomy layer).
