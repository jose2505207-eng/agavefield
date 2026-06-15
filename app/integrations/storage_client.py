"""Pluggable object storage.

`local` writes to ./storage and serves through FastAPI's /media mount.
`s3` uses any S3-compatible endpoint (AWS S3, MinIO, Supabase Storage) via
boto3. The provider is chosen by STORAGE_PROVIDER; missing credentials fall
back to local so the MVP always runs.
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings

logger = logging.getLogger("agave.storage")

STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", "storage")).resolve()


class StorageClient(ABC):
    @abstractmethod
    def save(self, data: bytes, key: str, content_type: str = "image/jpeg") -> str:
        """Persist bytes under `key` and return a publicly resolvable URL."""


class LocalStorageClient(StorageClient):
    def __init__(self, root: Path = STORAGE_ROOT):
        self.root = root
        (self.root / "images").mkdir(parents=True, exist_ok=True)
        (self.root / "thumbnails").mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, key: str, content_type: str = "image/jpeg") -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        url = f"{settings.public_base_url.rstrip('/')}/media/{key}"
        logger.info("Stored %d bytes -> %s", len(data), url)
        return url


class S3StorageClient(StorageClient):
    def __init__(self):
        import boto3  # imported lazily so boto3 is optional
        from botocore.config import Config

        self.bucket = settings.storage_bucket
        # Supabase Storage (and most S3-compatibles) require SigV4 + a region.
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint or None,
            region_name=settings.storage_region or None,
            aws_access_key_id=settings.storage_access_key or None,
            aws_secret_access_key=settings.storage_secret_key or None,
            config=Config(signature_version="s3v4"),
        )

    def save(self, data: bytes, key: str, content_type: str = "image/jpeg") -> str:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )
        # Prefer the public object URL (renders in the dashboard / messages).
        if settings.storage_public_base:
            base = settings.storage_public_base.rstrip("/")
            url = f"{base}/{self.bucket}/{key}"
        elif settings.storage_endpoint:
            url = f"{settings.storage_endpoint.rstrip('/')}/{self.bucket}/{key}"
        else:
            url = f"s3://{self.bucket}/{key}"
        logger.info("Stored %d bytes -> %s", len(data), url)
        return url


def get_storage_client() -> StorageClient:
    provider = settings.storage_provider.lower()
    if provider == "s3" and settings.storage_bucket:
        try:
            return S3StorageClient()
        except Exception as exc:  # pragma: no cover - depends on env
            logger.warning("S3 storage unavailable (%s); falling back to local", exc)
    return LocalStorageClient()
