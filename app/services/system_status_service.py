"""Production readiness / environment status — booleans + counts only.

Never returns secret values: it reports whether providers are configured, whether
RBAC is enforced, and live record counts, so an operator can confirm go-live
readiness from the dashboard.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.auth import auth_enabled
from app.config import settings
from app.models.operations import (
    Activity,
    Assignee,
    ExecutionRecord,
    Product,
    WorkOrder,
)

logger = logging.getLogger("agave.status")


def status(db: Session, wo_ids: Optional[list] = None) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("DB health check failed: %s", exc)
        db_ok = False

    storage = settings.storage_provider.lower()
    storage_configured = True if storage == "local" else bool(
        settings.storage_bucket and settings.storage_access_key
    )
    email = settings.email_provider.lower()
    email_configured = (
        email == "console"
        or (email == "smtp" and bool(settings.smtp_host))
        or (email == "sendgrid" and bool(settings.sendgrid_api_key))
        or (email == "resend" and bool(settings.resend_api_key))
    )

    def _count(model, **f):
        stmt = select(func.count(model.id))
        for k, v in f.items():
            stmt = stmt.where(getattr(model, k) == v)
        return db.scalar(stmt) or 0

    # Org/data-scope-aware counts. ``wo_ids is None`` → no membership resolved
    # (open / API-key / legacy) → unscoped totals, unchanged behaviour. A list
    # restricts the work-order / execution counts to what the caller may see.
    def _wo_count():
        stmt = select(func.count(WorkOrder.id))
        if wo_ids is not None:
            stmt = stmt.where(WorkOrder.id.in_(wo_ids))
        return db.scalar(stmt) or 0

    def _exec_count(**f):
        stmt = select(func.count(ExecutionRecord.id))
        for k, v in f.items():
            stmt = stmt.where(getattr(ExecutionRecord, k) == v)
        if wo_ids is not None:
            stmt = stmt.where(ExecutionRecord.work_order_id.in_(wo_ids))
        return db.scalar(stmt) or 0

    return {
        "app_env": settings.app_env,
        "app_base_url": settings.app_base_url,
        "database": {"connected": db_ok, "host": settings.database_url.split("@")[-1].split("/")[0]},
        "storage": {"provider": storage, "configured": storage_configured},
        "email": {"provider": email, "configured": email_configured, "live": email != "console"},
        "weather": {"provider": settings.weather_provider},
        "rbac_enforced": auth_enabled(),
        "ai_image_analysis_enabled": settings.enable_ai_image_analysis,
        "counts": {
            "products": _count(Product),
            "activities": _count(Activity),
            "assignees": _count(Assignee),
            "work_orders": _wo_count(),
            "executions": _exec_count(),
            "pending_review": _exec_count(compliance_status="pending_review"),
        },
        "go_live_ready": all([
            db_ok, storage_configured, email_configured,
            _count(Product) > 0, _count(Activity) > 0,
        ]),
    }
