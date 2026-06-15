"""Weekly report generation (on-demand; no queue infrastructure).

Aggregates the last 7 days (configurable window) by farm / lot / zone / all and
returns a structured payload the dashboard can render, including image
thumbnails. Reports can optionally be persisted to ``weekly_reports``.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import (
    AgavePassport,
    FieldObservation,
    HumanValidation,
    Task,
    WeeklyReport,
)
from app.services import task_service

logger = logging.getLogger("agave.report")


def _scope_filter(stmt, scope_type: str, scope_id: Optional[int]):
    if scope_type == "farm" and scope_id:
        return stmt.where(FieldObservation.farm_id == scope_id)
    if scope_type == "lot" and scope_id:
        return stmt.where(FieldObservation.lot_id == scope_id)
    if scope_type == "zone" and scope_id:
        return stmt.where(FieldObservation.passport_id == scope_id)
    return stmt


def generate_weekly_report(
    db: Session,
    *,
    scope_type: str = "all",
    scope_id: Optional[int] = None,
    days: int = 7,
    persist: bool = False,
) -> dict:
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)

    stmt = select(FieldObservation).where(FieldObservation.observed_at >= period_start)
    stmt = _scope_filter(stmt, scope_type, scope_id)
    observations = list(db.execute(stmt).scalars().all())

    photos = [o for o in observations if o.image_url]
    issue_counter = Counter(o.diagnosis or o.suspected_issue for o in observations if (o.diagnosis or o.suspected_issue))
    top_issues = [{"issue": k, "count": v} for k, v in issue_counter.most_common(5)]

    # High-risk zones from passports.
    high_risk = list(
        db.execute(
            select(AgavePassport).where(AgavePassport.risk_level.in_(("high", "critical")))
        )
        .scalars()
        .all()
    )

    all_tasks = list(db.execute(select(Task)).scalars().all())
    open_tasks = [t for t in all_tasks if t.status in ("open", "in_progress")]
    completed_tasks = [t for t in all_tasks if t.status == "completed"]
    overdue = task_service.overdue_tasks(db)

    corrections = list(
        db.execute(
            select(HumanValidation).where(
                HumanValidation.created_at >= period_start,
                HumanValidation.status == "corrected",
            )
        )
        .scalars()
        .all()
    )

    follow_ups = [
        {"observation_id": o.id, "next_step": o.recommended_next_step, "severity": o.severity}
        for o in observations
        if o.severity in ("high", "critical") and o.recommended_next_step
    ][:10]

    payload = {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "observation_count": len(observations),
        "photo_count": len(photos),
        "top_issues": top_issues,
        "high_risk_zones": [
            {"passport_id": p.id, "passport_code": p.passport_code, "risk_level": p.risk_level,
             "lot_name": p.lot_name}
            for p in high_risk
        ],
        "open_tasks": len(open_tasks),
        "overdue_tasks": len(overdue),
        "completed_tasks": len(completed_tasks),
        "weather_warnings": _weather_warnings(observations),
        "recommended_follow_ups": follow_ups,
        "human_validation_corrections": [
            {"observation_id": c.observation_id, "from": c.original_diagnosis,
             "to": c.corrected_label, "by": c.validated_by}
            for c in corrections
        ],
        "thumbnails": [o.thumbnail_url or o.image_url for o in photos[:12]],
        "generated_at": period_end.isoformat(),
    }

    if persist:
        report = WeeklyReport(
            scope_type=scope_type,
            scope_id=scope_id,
            period_start=period_start,
            period_end=period_end,
            payload_json=payload,
        )
        db.add(report)
        db.flush()
        payload["report_id"] = report.id
        logger.info("Persisted weekly report #%s (%s)", report.id, scope_type)

    return payload


def _weather_warnings(observations: list[FieldObservation]) -> list[str]:
    warnings = []
    for o in observations:
        for w in o.weather_snapshots:
            if w.heat_risk == "high":
                warnings.append(f"Extreme heat risk near observation #{o.id}")
            if w.drought_risk == "high":
                warnings.append(f"Drought risk near observation #{o.id}")
    return list(dict.fromkeys(warnings))[:10]  # dedupe, cap


def latest_report(db: Session, scope_type: str = "all", scope_id: Optional[int] = None) -> Optional[dict]:
    stmt = select(WeeklyReport).where(WeeklyReport.scope_type == scope_type)
    if scope_id is not None:
        stmt = stmt.where(WeeklyReport.scope_id == scope_id)
    stmt = stmt.order_by(WeeklyReport.created_at.desc()).limit(1)
    report = db.execute(stmt).scalars().first()
    return report.payload_json if report else None
