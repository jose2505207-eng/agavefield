"""Aggregations powering the dashboard endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.database import Escalation, FieldObservation, Lot
from app.models.schemas import MapPoint


def summary(db: Session) -> dict:
    total = db.scalar(select(func.count(FieldObservation.id))) or 0

    by_severity = dict(
        db.execute(
            select(FieldObservation.severity, func.count(FieldObservation.id)).group_by(
                FieldObservation.severity
            )
        ).all()
    )
    by_issue = dict(
        db.execute(
            select(FieldObservation.suspected_issue, func.count(FieldObservation.id))
            .where(FieldObservation.suspected_issue.is_not(None))
            .group_by(FieldObservation.suspected_issue)
        ).all()
    )
    needs_review = (
        db.scalar(
            select(func.count(FieldObservation.id)).where(
                FieldObservation.needs_human_review.is_(True)
            )
        )
        or 0
    )
    escalations_sent = (
        db.scalar(select(func.count(Escalation.id)).where(Escalation.status == "sent")) or 0
    )
    verified = (
        db.scalar(
            select(func.count(FieldObservation.id)).where(
                FieldObservation.human_verified.is_(True)
            )
        )
        or 0
    )
    verification_rate = round(verified / total, 3) if total else 0.0

    # --- Human-centered (MVP) aggregates ---
    by_event_type = dict(
        db.execute(
            select(FieldObservation.event_type, func.count(FieldObservation.id)).group_by(
                FieldObservation.event_type
            )
        ).all()
    )
    photo_count = (
        db.scalar(
            select(func.count(FieldObservation.id)).where(FieldObservation.image_url.is_not(None))
        )
        or 0
    )
    pending_review = (
        db.scalar(
            select(func.count(FieldObservation.id)).where(
                FieldObservation.review_status == "pending_review"
            )
        )
        or 0
    )
    follow_ups_pending = (
        db.scalar(
            select(func.count(FieldObservation.id)).where(
                FieldObservation.follow_up_needed.is_(True)
            )
        )
        or 0
    )

    return {
        "total_observations": total,
        "photo_count": photo_count,
        "observations_by_event_type": by_event_type,
        "pending_review": pending_review,
        "follow_ups_pending": follow_ups_pending,
        "approved_records": verified,
        # Retained for the optional AI (V2) path; 0 in the human-centered MVP.
        "observations_by_severity": by_severity,
        "observations_by_suspected_issue": by_issue,
        "needs_human_review": needs_review,
        "escalations_sent": escalations_sent,
        "human_verified": verified,
        "human_verification_rate": verification_rate,
    }


def recent_observations(db: Session, limit: int = 20) -> list[FieldObservation]:
    return list(
        db.execute(
            select(FieldObservation)
            .order_by(FieldObservation.observed_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def gallery(
    db: Session,
    *,
    lot_id: Optional[int] = None,
    severity: Optional[str] = None,
    suspected_issue: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 60,
) -> list[FieldObservation]:
    stmt = select(FieldObservation).where(
        (FieldObservation.thumbnail_url.is_not(None))
        | (FieldObservation.image_url.is_not(None))
    )
    if lot_id:
        stmt = stmt.where(FieldObservation.lot_id == lot_id)
    if severity:
        stmt = stmt.where(FieldObservation.severity == severity)
    if suspected_issue:
        stmt = stmt.where(FieldObservation.suspected_issue == suspected_issue)
    if date_from:
        stmt = stmt.where(FieldObservation.observed_at >= date_from)
    if date_to:
        stmt = stmt.where(FieldObservation.observed_at <= date_to)
    stmt = stmt.order_by(FieldObservation.observed_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


_SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}


def lot_risk_ranking(db: Session, limit: int = 20) -> list[dict]:
    """Rank lots by a simple risk score = sum of severity weights."""
    rows = db.execute(
        select(
            FieldObservation.lot_id,
            FieldObservation.severity,
            func.count(FieldObservation.id),
            func.max(FieldObservation.observed_at),
        )
        .where(FieldObservation.lot_id.is_not(None))
        .group_by(FieldObservation.lot_id, FieldObservation.severity)
    ).all()

    agg: dict[int, dict] = {}
    for lot_id, severity, count, last_seen in rows:
        entry = agg.setdefault(
            lot_id, {"lot_id": lot_id, "risk_score": 0, "observation_count": 0, "last_observed_at": None}
        )
        entry["risk_score"] += _SEVERITY_WEIGHT.get(severity, 0) * count
        entry["observation_count"] += count
        if last_seen and (entry["last_observed_at"] is None or last_seen > entry["last_observed_at"]):
            entry["last_observed_at"] = last_seen

    # Attach lot codes.
    for lot_id, entry in agg.items():
        lot = db.get(Lot, lot_id)
        entry["lot_code"] = lot.lot_code if lot else None
        entry["farm_id"] = lot.farm_id if lot else None

    ranked = sorted(agg.values(), key=lambda e: e["risk_score"], reverse=True)
    return ranked[:limit]


def map_points(db: Session) -> list[MapPoint]:
    rows = (
        db.execute(
            select(FieldObservation).where(
                FieldObservation.latitude.is_not(None),
                FieldObservation.longitude.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    return [
        MapPoint(
            observation_id=o.id,
            latitude=o.latitude,
            longitude=o.longitude,
            severity=o.severity,
            suspected_issue=o.suspected_issue,
            thumbnail_url=o.thumbnail_url,
            ai_summary=o.ai_summary,
        )
        for o in rows
    ]


def lot_detail(db: Session, lot_id: int) -> Optional[dict]:
    lot = db.get(Lot, lot_id)
    if not lot:
        return None
    obs = list(
        db.execute(
            select(FieldObservation)
            .where(FieldObservation.lot_id == lot_id)
            .order_by(FieldObservation.observed_at.desc())
        )
        .scalars()
        .all()
    )
    issues: dict[str, int] = {}
    for o in obs:
        if o.suspected_issue:
            issues[o.suspected_issue] = issues.get(o.suspected_issue, 0) + 1
    repeated = {k: v for k, v in issues.items() if v > 1}
    return {
        "lot_id": lot.id,
        "lot_code": lot.lot_code,
        "farm_id": lot.farm_id,
        "crop_type": lot.crop_type,
        "observation_count": len(obs),
        "last_inspection_at": obs[0].observed_at if obs else None,
        "repeated_issues": repeated,
        "severity_breakdown": {
            sev: sum(1 for o in obs if o.severity == sev)
            for sev in ("critical", "high", "medium", "low", "unknown")
        },
    }
