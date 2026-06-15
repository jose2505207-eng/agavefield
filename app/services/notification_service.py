"""Notification abstraction with a provider pattern.

Channels: whatsapp, telegram, dashboard (in-app), console (local dev fallback).
No real credentials are required to run locally — providers degrade to the
console/log fallback and the Alert is still recorded for the dashboard.

This is the single entry point for raising alerts; the escalation service and
the Hermes flow both call ``create_alert``.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.integrations import telegram_client, whatsapp_client
from app.models.database import Alert, FieldObservation

logger = logging.getLogger("agave.notify")


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
class NotificationProvider(ABC):
    name = "base"

    @abstractmethod
    def send(self, recipient: Optional[str], title: str, message: str) -> bool:
        ...


class ConsoleProvider(NotificationProvider):
    name = "console"

    def send(self, recipient, title, message) -> bool:
        logger.info("[CONSOLE ALERT] to=%s | %s | %s", recipient, title, message)
        return True


class DashboardProvider(NotificationProvider):
    """In-app only: nothing to send externally; the Alert row IS the delivery."""

    name = "dashboard"

    def send(self, recipient, title, message) -> bool:
        return True


class TelegramProvider(NotificationProvider):
    name = "telegram"

    def send(self, recipient, title, message) -> bool:
        if not recipient:
            return False
        return telegram_client.send_message(recipient, f"<b>{title}</b>\n{message}")


class WhatsAppProvider(NotificationProvider):
    name = "whatsapp"

    def send(self, recipient, title, message) -> bool:
        if not recipient:
            return False
        return whatsapp_client.send_text(recipient, f"*{title}*\n{message}")


_PROVIDERS = {
    "console": ConsoleProvider(),
    "dashboard": DashboardProvider(),
    "telegram": TelegramProvider(),
    "whatsapp": WhatsAppProvider(),
}


def _default_channel() -> str:
    """Prefer WhatsApp, then Telegram, then console (local dev safe)."""
    if settings.whatsapp_enabled:
        return "whatsapp"
    if settings.telegram_enabled:
        return "telegram"
    return "console"


def _default_recipient(channel: str) -> Optional[str]:
    if channel == "whatsapp" and settings.whatsapp_recipients:
        return settings.whatsapp_recipients[0]
    return None


def get_provider(channel: str) -> NotificationProvider:
    return _PROVIDERS.get(channel, _PROVIDERS["console"])


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def create_alert(
    db: Session,
    *,
    title: str,
    message: str,
    severity: str = "medium",
    reason: Optional[str] = None,
    channel: Optional[str] = None,
    recipient: Optional[str] = None,
    passport_id: Optional[int] = None,
    observation_id: Optional[int] = None,
    also_dashboard: bool = True,
) -> Alert:
    """Dispatch an alert via the chosen channel and persist it.

    Always records the alert so it shows on the dashboard, even if external
    delivery fails or no credentials are configured.
    """
    channel = channel or _default_channel()
    recipient = recipient or _default_recipient(channel)

    provider = get_provider(channel)
    delivered = False
    try:
        delivered = provider.send(recipient, title, message)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Provider %s failed: %s", channel, exc)

    alert = Alert(
        passport_id=passport_id,
        observation_id=observation_id,
        recipient=recipient,
        channel=channel,
        title=title,
        message=message,
        severity=severity,
        reason=reason,
        delivery_status="sent" if delivered else "failed",
    )
    db.add(alert)
    db.flush()
    logger.info(
        "Alert #%s '%s' via %s (delivered=%s)", alert.id, title, channel, delivered
    )
    return alert


# --------------------------------------------------------------------------- #
# Alert rules
# --------------------------------------------------------------------------- #
HIGH_SEVERITIES = {"high", "critical", "urgent"}


def should_alert(
    db: Session,
    observation: FieldObservation,
    *,
    repeated_issue: bool = False,
    weather_risk: bool = False,
) -> tuple[bool, Optional[str]]:
    """Decide whether an observation warrants an alert (pure rules)."""
    if observation.severity in HIGH_SEVERITIES:
        return True, f"Severity is {observation.severity}"
    # Low confidence but high severity is covered above; also flag the inverse:
    if observation.severity in HIGH_SEVERITIES and observation.confidence < 0.5:
        return True, "High severity with low confidence"
    if repeated_issue:
        return True, "Repeated issue in this zone"
    if weather_risk:
        return True, "Weather risk for this observation"
    return False, None
