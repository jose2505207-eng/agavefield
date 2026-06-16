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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
