"""Email delivery with a provider abstraction.

Providers: console (local dev — prints to log), smtp, sendgrid, resend.
Selected by EMAIL_PROVIDER. Missing credentials degrade to console so the app
never hard-fails when email isn't configured (the work order is still created).
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.config import settings

logger = logging.getLogger("agave.email")


class EmailProvider(ABC):
    name = "base"

    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> bool:
        ...


class ConsoleEmailProvider(EmailProvider):
    """Local-dev only: logs the email instead of sending it."""

    name = "console"

    def send(self, to: str, subject: str, body: str) -> bool:
        logger.info("[CONSOLE EMAIL] to=%s | subject=%s\n%s", to, subject, body)
        return True


class SMTPEmailProvider(EmailProvider):
    name = "smtp"

    def send(self, to: str, subject: str, body: str) -> bool:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        from_addr = settings.smtp_from_email or settings.smtp_username
        msg["From"] = f"{settings.smtp_from_name} <{from_addr}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
                s.starttls()
                if settings.smtp_username:
                    s.login(settings.smtp_username, settings.smtp_password)
                s.send_message(msg)
            return True
        except Exception as exc:
            logger.error("SMTP send failed to %s: %s", to, exc)
            return False


class SendGridEmailProvider(EmailProvider):
    name = "sendgrid"

    def send(self, to: str, subject: str, body: str) -> bool:
        import httpx

        from_addr = settings.smtp_from_email or "no-reply@agavefield.app"
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": from_addr, "name": settings.smtp_from_name},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
                )
                r.raise_for_status()
            return True
        except Exception as exc:
            logger.error("SendGrid send failed to %s: %s", to, exc)
            return False


class ResendEmailProvider(EmailProvider):
    name = "resend"

    def send(self, to: str, subject: str, body: str) -> bool:
        import httpx

        from_addr = settings.smtp_from_email or "onboarding@resend.dev"
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.post(
                    "https://api.resend.com/emails",
                    json={
                        "from": f"{settings.smtp_from_name} <{from_addr}>",
                        "to": [to],
                        "subject": subject,
                        "text": body,
                    },
                    headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                )
                r.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Resend send failed to %s: %s", to, exc)
            return False


def get_email_provider() -> EmailProvider:
    choice = (settings.email_provider or "console").lower()
    if choice == "smtp" and settings.smtp_host:
        return SMTPEmailProvider()
    if choice == "sendgrid" and settings.sendgrid_api_key:
        return SendGridEmailProvider()
    if choice == "resend" and settings.resend_api_key:
        return ResendEmailProvider()
    if choice != "console":
        logger.warning("Email provider '%s' not fully configured; using console", choice)
    return ConsoleEmailProvider()


def send_email(to: str, subject: str, body: str) -> tuple[bool, str]:
    """Send via the configured provider. Returns (delivered, provider_name)."""
    provider = get_email_provider()
    try:
        delivered = provider.send(to, subject, body)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Email send error: %s", exc)
        delivered = False
    return delivered, provider.name
