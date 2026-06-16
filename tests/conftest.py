"""Test fixtures.

Forces a file-based SQLite DB and a credential-free environment BEFORE any app
module is imported, so the suite runs offline with the stub vision client.
"""
from __future__ import annotations

import os
import tempfile

# --- must run before importing app.* ---
_TMP_DB = os.path.join(tempfile.gettempdir(), "agave_test.db")
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["VISION_PROVIDER"] = "openai_compatible"
os.environ["VISION_API_KEY"] = ""  # -> stub analyzer
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_WEBHOOK_SECRET"] = ""  # don't inherit a real .env secret
os.environ["WHATSAPP_ACCESS_TOKEN"] = ""

import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import database as _models  # noqa: E402,F401
from app.models import operations as _ops  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
