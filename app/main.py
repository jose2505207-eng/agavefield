"""Agave Field Copilot — FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import require_reviewer, require_staff
from app.api import (
    alert_routes,
    assignee_routes,
    auth_routes,
    audit_routes,
    carbon_routes,
    catalog_routes,
    completion_routes,
    execution_routes,
    ops_photo_routes,
    review_routes,
    season_routes,
    system_routes,
    timeline_routes,
    work_order_routes,
    dashboard_routes,
    lot_routes,
    map_routes,
    observation_routes,
    passport_routes,
    report_routes,
    task_routes,
    telegram_routes,
    weather_routes,
    whatsapp_routes,
)
from app.config import settings, validate_runtime
from app.db import init_db
from app.integrations.storage_client import STORAGE_ROOT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("agave")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Fail fast on critical misconfiguration in production (insecure SECRET_KEY,
    # open RBAC). In dev/test this only logs warnings, so the app still boots on
    # empty defaults.
    validate_runtime(settings)
    # Best-effort schema ensure. Must never crash startup: on serverless
    # (Vercel) the filesystem is read-only and the DB schema already exists
    # (created via supabase_schema.sql), so a failure here is non-fatal.
    try:
        init_db()
    except Exception as exc:  # pragma: no cover - depends on runtime env
        logger.warning("Startup init_db skipped (%s); assuming schema already exists", exc)
    # Ensure the DEMO account (and a real admin if configured) exist. Best-effort:
    # a failure here (e.g. table not yet migrated) must never crash startup.
    try:
        from app.db import SessionLocal
        from app.services import auth_service

        with SessionLocal() as _db:
            auth_service.seed_users(_db)
    except Exception as exc:  # pragma: no cover - depends on runtime env
        logger.warning("Startup user seeding skipped (%s)", exc)
    logger.info(
        "Agave Field Copilot started (env=%s, telegram=%s, whatsapp=%s, vision=%s)",
        settings.app_env,
        settings.telegram_enabled,
        settings.whatsapp_enabled,
        settings.vision_provider,
    )
    yield


app = FastAPI(
    title="Agave Field Copilot",
    description="AI-powered field intelligence for agave agronomists in Jalisco.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Demo accounts are read-only. Enforced server-side (authoritative): any
# write request carrying a valid demo session token is refused, so the demo
# experience can never mutate the live dataset even if the UI guard is bypassed.
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def demo_readonly_guard(request: Request, call_next):
    if request.method not in _SAFE_METHODS and not request.url.path.startswith("/api/auth/"):
        from app.services import auth_service

        auth = request.headers.get("authorization") or ""
        scheme, _, token = auth.partition(" ")
        if scheme.lower() == "bearer" and token:
            payload = auth_service.decode_token(token.strip())
            if payload and payload.get("is_demo"):
                return JSONResponse(
                    {"detail": "Demo account is read-only."}, status_code=403
                )
    return await call_next(request)


# Serve locally-stored images/thumbnails for the dashboard and message links.
if settings.storage_provider.lower() == "local":
    Path(STORAGE_ROOT).mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(STORAGE_ROOT)), name="media")


@app.get("/health", tags=["system"])
def health():
    return {
        "status": "ok",
        "env": settings.app_env,
        "telegram_enabled": settings.telegram_enabled,
        "whatsapp_enabled": settings.whatsapp_enabled,
        "vision_provider": settings.vision_provider,
        "storage_provider": settings.storage_provider,
    }


app.include_router(auth_routes.router)  # public: login / me / logout
app.include_router(telegram_routes.router)
app.include_router(whatsapp_routes.router)
app.include_router(observation_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(lot_routes.router)
# MVP additions
app.include_router(passport_routes.router)
app.include_router(task_routes.router)
app.include_router(alert_routes.router)
app.include_router(weather_routes.router)
app.include_router(report_routes.router)
app.include_router(map_routes.router)
# Operations / traceability layer.
# RBAC: staff (admin/agronomist) for catalogs/assignees/work-orders/audit;
# reviewer+ for review/timeline/carbon reads. Open when no API keys are set.
# Public (token-based): ops_photo upload + mobile completion.
_staff = [Depends(require_staff)]
_reviewer = [Depends(require_reviewer)]
app.include_router(assignee_routes.router, dependencies=_staff)
app.include_router(catalog_routes.router, dependencies=_staff)
app.include_router(season_routes.router, dependencies=_staff)
app.include_router(audit_routes.router, dependencies=_staff)
app.include_router(work_order_routes.router, dependencies=_staff)
app.include_router(ops_photo_routes.router)          # upload is token-authorized
app.include_router(completion_routes.router)          # public worker page (token)
app.include_router(review_routes.router, dependencies=_reviewer)
app.include_router(timeline_routes.router, dependencies=_reviewer)
app.include_router(carbon_routes.router, dependencies=_reviewer)
app.include_router(execution_routes.router, dependencies=_staff)
app.include_router(system_routes.router, dependencies=_staff)
