---
name: backend-api
description: Create FastAPI routes, SQLAlchemy models, Pydantic schemas, services, additive migrations, and provider abstractions for Agave Field. Use for any server-side work.
---

# backend-api

## When to use
Adding/altering models, services, schemas, routes, or provider integrations.

## Instructions
- **Layering:** route (`app/api/*`) → service (`app/services/*`) → model
  (`app/models/operations.py` / `database.py`). Routes orchestrate + commit; services hold
  logic; models are SQLAlchemy 2.0 `Mapped[...]`.
- **Schemas:** every request/response uses Pydantic v2 (`app/models/ops_schemas.py`).
  `Create`/`Update`/`Read` variants; `Read` uses `model_config = {"from_attributes": True}`.
- **Migrations:** additive only. New tables/columns via `Base.metadata.create_all`
  (startup) AND mirror DDL into `supabase_schema.sql` (`ADD COLUMN IF NOT EXISTS`). Apply
  to Supabase with a one-off psycopg2 script. Never drop/rename columns with live data.
- **Register** new routers in `app/main.py`; register new model modules in `app/db.py`
  `init_db` and `tests/conftest.py`.
- **Providers:** follow the existing abstraction pattern (storage/weather): an ABC +
  concrete providers + a `get_*()` selector driven by env, with a safe console/mock
  fallback for local dev.
- **Audit:** call `audit_service.log(...)` on every meaningful mutation.

## Constraints
- DB-agnostic columns (no PostGIS-only types) so SQLite tests pass.
- Fail gracefully when third-party creds are missing. No secrets in code.

## Output
Tested endpoints + services + schemas, registered and migration-safe.
