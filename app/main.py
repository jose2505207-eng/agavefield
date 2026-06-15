"""Agave Field Copilot — FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    alert_routes,
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
from app.config import settings
from app.db import init_db
from app.integrations.storage_client import STORAGE_ROOT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("agave")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Best-effort schema ensure. Must never crash startup: on serverless
    # (Vercel) the filesystem is read-only and the DB schema already exists
    # (created via supabase_schema.sql), so a failure here is non-fatal.
    try:
        init_db()
    except Exception as exc:  # pragma: no cover - depends on runtime env
        logger.warning("Startup init_db skipped (%s); assuming schema already exists", exc)
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
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
