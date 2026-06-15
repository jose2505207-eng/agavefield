"""Tool layer for Hermes.

Hermes orchestrates via these named tools rather than reaching into
integrations directly. Each tool is a thin, typed wrapper around a service or
integration, which keeps the agent loop swappable and testable and makes it
straightforward to later expose them as actual LLM function-calling tools.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.integrations.vision_client import get_vision_client
from app.models.database import FieldObservation
from app.models.schemas import HermesOutput
from app.services import (
    escalation_service,
    lot_matching_service,
    observation_service,
    weather_service,
)

logger = logging.getLogger("agave.hermes.tools")


def tool_analyze_image(
    image_url: str,
    caption: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
) -> tuple[HermesOutput, str, dict]:
    """Run the vision model and validate output against the strict schema."""
    client = get_vision_client()
    raw = client.analyze(image_url, caption, latitude, longitude)
    # Validation is the safety gate: nothing unvalidated reaches the DB.
    validated = HermesOutput.model_validate(raw)
    return validated, client.model_name, raw


def tool_fetch_weather(latitude: float, longitude: float, ts: Optional[datetime] = None):
    return weather_service.fetch_weather(latitude, longitude, ts)


def tool_match_lot(db: Session, latitude: Optional[float], longitude: Optional[float]):
    return lot_matching_service.match_lot(db, latitude, longitude)


def tool_create_observation(db: Session, **kwargs) -> FieldObservation:
    return observation_service.create_observation(db, **kwargs)


def tool_maybe_escalate(
    db: Session,
    observation: FieldObservation,
    hermes: HermesOutput,
    caption: Optional[str],
    force: bool = False,
):
    return escalation_service.maybe_escalate(db, observation, hermes, caption, force)
