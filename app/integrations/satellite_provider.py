"""Satellite / vegetation-index providers — VERSION 2 PLACEHOLDER ONLY.

Satellite/NDVI monitoring is intentionally NOT implemented in the MVP. This
module exists solely to define a stable extension point so V2 can plug in
without touching the rest of the system.

TODO(v2): implement concrete providers for:
  - NDVI / vegetation indices (e.g. Sentinel-2 via Sentinel Hub, Planet, etc.)
  - satellite imagery tiles
  - vegetation health maps
  - drought-stress detection
  - regional field monitoring

There is no hard dependency here and nothing in the MVP imports a concrete
implementation, so this cannot break local development or the dashboard.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class VegetationIndexService(ABC):
    """V2 interface for vegetation-index lookups (e.g. NDVI)."""

    @abstractmethod
    def get_ndvi(self, latitude: float, longitude: float, date_iso: Optional[str] = None) -> dict:
        ...


class SatelliteProvider(ABC):
    """V2 interface for satellite imagery + derived health maps."""

    @abstractmethod
    def get_imagery(self, bbox: list[float], date_iso: Optional[str] = None) -> dict:
        ...

    @abstractmethod
    def get_vegetation_health_map(self, bbox: list[float]) -> dict:
        ...


# Deliberately no factory / no default implementation in the MVP.
def get_satellite_provider():  # pragma: no cover - V2
    raise NotImplementedError(
        "Satellite/NDVI monitoring is planned for Version 2 and is not available in the MVP."
    )
