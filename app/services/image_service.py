"""Image intake: fetch bytes, generate a thumbnail, persist both.

Pillow is used for thumbnails when available; if it is missing we still store
the original and reuse it as the thumbnail so the flow never hard-fails.
"""
from __future__ import annotations

import io
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

import httpx

from app.integrations.storage_client import get_storage_client

logger = logging.getLogger("agave.image")

THUMBNAIL_SIZE = (480, 480)


@dataclass
class StoredImage:
    image_url: str
    thumbnail_url: str


def _make_thumbnail(data: bytes) -> Optional[bytes]:
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        logger.warning("Pillow not installed; skipping thumbnail generation")
        return None
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        img.thumbnail(THUMBNAIL_SIZE)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82)
        return buf.getvalue()
    except Exception as exc:
        logger.warning("Thumbnail generation failed: %s", exc)
        return None


def store_image_bytes(data: bytes, ext: str = "jpg") -> StoredImage:
    storage = get_storage_client()
    name = uuid.uuid4().hex
    image_url = storage.save(data, f"images/{name}.{ext}", content_type="image/jpeg")

    thumb = _make_thumbnail(data)
    if thumb is not None:
        thumbnail_url = storage.save(
            thumb, f"thumbnails/{name}.jpg", content_type="image/jpeg"
        )
    else:
        thumbnail_url = image_url
    return StoredImage(image_url=image_url, thumbnail_url=thumbnail_url)


def store_image_from_url(url: str, timeout: float = 30.0) -> StoredImage:
    """Download a remote image (e.g. a Telegram file URL) and store it."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.content
    ext = "jpg"
    ctype = resp.headers.get("content-type", "")
    if "png" in ctype:
        ext = "png"
    return store_image_bytes(data, ext=ext)
