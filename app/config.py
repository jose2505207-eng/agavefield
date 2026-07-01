"""Application configuration loaded from environment variables.

All settings have safe defaults so the MVP can boot with an empty .env.
Missing third-party credentials degrade gracefully (see integrations/).
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/agave_copilot"

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    # Process inbound photos inline (true) instead of in a BackgroundTask.
    # Set true on serverless hosts (e.g. Vercel) where background work after the
    # response can be killed; keep false locally for snappy acks.
    telegram_webhook_sync: bool = False

    # --- WhatsApp Cloud API (optional) ---
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_default_escalation_recipients: str = ""

    # --- Vision model ---
    vision_provider: str = "openai_compatible"  # openai_compatible | stub
    vision_api_key: str = ""
    vision_base_url: str = "https://api.openai.com/v1"
    vision_model: str = "gpt-4o-mini"

    # MVP is a human-centered record system: NO LLM/CV runs on photo upload.
    # Photos are stored as historical evidence with manual notes. Any AI image
    # analysis (Hermes) is gated behind this flag and is OFF by default.
    # Version 2+ may enable it once enough human-labeled history exists.
    enable_ai_image_analysis: bool = False

    # --- Storage ---
    storage_provider: str = "local"  # local | s3
    storage_bucket: str = ""
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_endpoint: str = ""
    storage_region: str = ""  # required for Supabase S3 (e.g. "us-east-1")
    # Public object URL base, e.g. https://<ref>.supabase.co/storage/v1/object/public
    storage_public_base: str = ""

    # Public base URL used to build image links in messages/dashboard.
    public_base_url: str = "http://localhost:8000"

    # CORS: comma-separated allowed origins, or "*" for any (dev default).
    # Set explicit origins (e.g. the dashboard + web frontend URLs) in production.
    cors_allow_origins: str = "*"

    # --- Operations / work orders ---
    # Signs admin login session tokens (HMAC). Rotating it invalidates all live
    # sessions. NOT used for work-order link hashing (those use keyless sha256).
    secret_key: str = "dev-insecure-change-me"  # override in prod
    app_base_url: str = "http://localhost:8000"  # used for secure work-order links
    # Public URL of the Next.js `web/` frontend. When set, emailed work-order
    # links open the polished web worker page (`{web_app_base_url}/complete/{token}`);
    # when empty they fall back to the backend's self-contained HTML page
    # (`{app_base_url}/work-orders/complete/{token}`), which needs no frontend deploy.
    web_app_base_url: str = ""

    # Role-based access (API keys). If ALL are empty, auth is OPEN (dev mode);
    # set at least one in production to enforce RBAC on the ops admin endpoints.
    admin_api_key: str = ""
    agronomist_api_key: str = ""
    reviewer_api_key: str = ""
    work_order_link_expiry_days: int = 14

    # --- Admin login (web UI accounts; separate from the API-key RBAC above) ---
    # Stateless sessions are signed with SECRET_KEY. The DEMO account is always
    # seeded (read-only demo data). A real admin is seeded only if both creds
    # are set. Passwords are stored as pbkdf2 hashes, never in plaintext.
    session_ttl_hours: int = 12
    demo_username: str = "DEMO"
    demo_password: str = "DEMO"
    auth_admin_username: str = ""
    auth_admin_password: str = ""

    # When true AND a live email provider is configured, invitations carrying an
    # `invited_email` require a one-time verification code (emailed to that
    # address) at acceptance. Off by default; when email is not configured the
    # flow degrades gracefully to plain email-match binding (never crashes).
    require_invite_email_verification: bool = False
    # Lifetime of a password-reset token (hash + expiry stored on the AppUser).
    password_reset_ttl_hours: int = 2

    # Email delivery for work-order links.
    email_provider: str = "console"  # console | smtp | sendgrid | resend
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Agave Field"
    sendgrid_api_key: str = ""
    resend_api_key: str = ""

    # --- Weather ---
    # auto -> Open-Meteo (no key) if reachable, else mock. mock | openmeteo | openweather
    weather_provider: str = "auto"
    weather_api_key: str = ""  # required only for openweather

    # --- Escalation ---
    escalation_cooldown_hours: int = 24

    @property
    def whatsapp_recipients(self) -> List[str]:
        raw = self.whatsapp_default_escalation_recipients or ""
        return [r.strip() for r in raw.split(",") if r.strip()]

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_access_token and self.whatsapp_phone_number_id)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in {"production", "prod", "staging"}

    @property
    def cors_origins(self) -> List[str]:
        raw = (self.cors_allow_origins or "*").strip()
        if raw == "*" or not raw:
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


# Values that must never survive into a production deployment.
_INSECURE_SECRETS = {"", "dev-insecure-change-me", "change-me-in-production"}


def config_problems(s: "Settings") -> tuple[list[str], list[str]]:
    """Inspect settings for misconfiguration.

    Returns (critical, warnings). `critical` issues should block a production
    boot (they weaken security or guarantee broken behavior); `warnings` are
    surfaced but non-fatal. In non-production envs everything is a warning so
    local dev / tests keep booting on defaults.
    """
    critical: list[str] = []
    warnings: list[str] = []

    if s.secret_key.strip() in _INSECURE_SECRETS:
        critical.append(
            "SECRET_KEY is unset or a known default — work-order tokens would be "
            "hashed with a publicly known secret. Set a strong random SECRET_KEY."
        )
    if "localhost" in s.database_url or s.database_url.startswith(
        "postgresql://postgres:postgres@localhost"
    ):
        warnings.append("DATABASE_URL still points at a local/default database.")
    if "localhost" in s.app_base_url:
        warnings.append(
            "APP_BASE_URL is localhost — secure work-order links will be unreachable "
            "for field workers."
        )
    if s.email_provider.lower() == "smtp" and not s.smtp_host:
        warnings.append("EMAIL_PROVIDER=smtp but SMTP_HOST is blank; emails fall back to console.")
    if s.email_provider.lower() == "sendgrid" and not s.sendgrid_api_key:
        warnings.append("EMAIL_PROVIDER=sendgrid but SENDGRID_API_KEY is blank; emails fall back to console.")
    if s.email_provider.lower() == "resend" and not s.resend_api_key:
        warnings.append("EMAIL_PROVIDER=resend but RESEND_API_KEY is blank; emails fall back to console.")
    if s.storage_provider.lower() == "s3" and not s.storage_bucket:
        warnings.append("STORAGE_PROVIDER=s3 but STORAGE_BUCKET is blank; storage falls back to local.")
    if s.is_production and s.cors_origins == ["*"]:
        warnings.append(
            "CORS_ALLOW_ORIGINS is '*' in production — set explicit origins "
            "(dashboard + web frontend URLs)."
        )
    if s.is_production and not (s.admin_api_key or s.agronomist_api_key or s.reviewer_api_key):
        critical.append(
            "No RBAC API keys configured in production — the admin/ops endpoints are "
            "open to the public. Set ADMIN_API_KEY (and others)."
        )
    if s.is_production and not (s.auth_admin_username and s.auth_admin_password):
        warnings.append(
            "No real admin login configured in production — only the read-only DEMO "
            "account exists. Set AUTH_ADMIN_USERNAME and AUTH_ADMIN_PASSWORD."
        )
    return critical, warnings


def validate_runtime(s: "Settings") -> None:
    """Fail fast on critical misconfiguration in production; warn otherwise.

    Safe to call at startup: in development/test envs nothing is raised, so the
    app still boots on empty defaults.
    """
    import logging

    log = logging.getLogger("agave.config")
    critical, warnings = config_problems(s)
    for w in warnings:
        log.warning("Config warning: %s", w)
    if not critical:
        return
    if s.is_production:
        raise RuntimeError(
            "Refusing to start in production with critical configuration problems:\n  - "
            + "\n  - ".join(critical)
        )
    for c in critical:
        log.warning("Config issue (non-prod, not blocking): %s", c)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
