"""Before/after photo comparison for a passport/zone.

MVP scope: fetch historical photos and pair the two most recent for a
side-by-side view. An AI change summary is produced by a placeholder that can
later call a multimodal model (Hermes) to reason over the two images.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.services import passport_service

logger = logging.getLogger("agave.compare")


def _photo_dict(obs) -> dict:
    return {
        "observation_id": obs.id,
        "image_url": obs.image_url,
        "thumbnail_url": obs.thumbnail_url,
        "observed_at": obs.observed_at,
        "severity": obs.severity,
        "diagnosis": obs.diagnosis or obs.suspected_issue,
        "summary": obs.ai_summary,
    }


def generate_change_summary(before: dict, after: dict) -> str:
    """Placeholder change summary.

    TODO(v2): pass both image URLs to a multimodal model for a real visual diff.
    For now we produce a deterministic, honest summary from stored metadata.
    """
    sev_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4, "unknown": 0}
    b = sev_rank.get(before.get("severity", "unknown"), 0)
    a = sev_rank.get(after.get("severity", "unknown"), 0)
    if a > b:
        trend = "The condition appears to have worsened since the previous inspection."
    elif a < b:
        trend = "The condition appears to have improved since the previous inspection."
    else:
        trend = "The condition appears broadly similar to the previous inspection."
    return (
        f"{trend} Previous: {before.get('diagnosis') or 'n/a'} "
        f"(severity {before.get('severity')}). "
        f"Current: {after.get('diagnosis') or 'n/a'} (severity {after.get('severity')}). "
        "[Placeholder summary — enable a vision model for a true visual diff.]"
    )


def compare_passport_photos(db: Session, passport_id: int) -> Optional[dict]:
    photos = passport_service.get_photos(db, passport_id)
    history = [_photo_dict(p) for p in photos]
    if len(photos) < 2:
        return {
            "passport_id": passport_id,
            "comparison_available": False,
            "history": history,
            "before": history[0] if history else None,
            "after": None,
            "change_summary": None,
        }
    before, after = history[-2], history[-1]
    return {
        "passport_id": passport_id,
        "comparison_available": True,
        "history": history,
        "before": before,
        "after": after,
        "change_summary": generate_change_summary(before, after),
    }
