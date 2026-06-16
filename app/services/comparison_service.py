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
        "event_type": obs.event_type,
        "manual_note": obs.manual_note or obs.original_caption,
        "process_type": obs.process_type,
        "responsible_person": obs.responsible_person,
    }


def generate_change_summary(before: dict, after: dict) -> str:
    """Human comparison context — NO AI evaluation.

    Surfaces the two human-selected records (dates + manual notes) for a person
    to compare side by side. The judgement stays with the agronomist.
    """
    def _d(x):
        return str(x.get("observed_at"))[:10] if x.get("observed_at") else "n/a"

    return (
        f"Before ({_d(before)}): {before.get('manual_note') or 'no note'} "
        f"[{before.get('event_type')}]. "
        f"After ({_d(after)}): {after.get('manual_note') or 'no note'} "
        f"[{after.get('event_type')}]. "
        "Compare the two photos manually — the agronomist decides what changed."
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
