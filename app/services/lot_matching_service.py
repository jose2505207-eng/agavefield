"""Match an observation's coordinates to a known lot.

Strategy (pure-Python, no PostGIS dependency required):
1. If a lot has a GeoJSON polygon and the point falls inside it -> match.
2. Otherwise pick the nearest lot centroid within MAX_MATCH_KM.

When the schema is later promoted to PostGIS, this can become a single
``ST_Contains`` / ``ST_DWithin`` query without changing callers.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import Lot

logger = logging.getLogger("agave.lotmatch")

MAX_MATCH_KM = 2.0  # nearest-centroid fallback radius


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def _ring_contains(point, ring) -> bool:
    """Ray-casting point-in-polygon. point=(lon,lat), ring=[[lon,lat],...]."""
    x, y = point
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def _polygon_contains(geojson: dict, lat: float, lon: float) -> bool:
    if not geojson:
        return False
    geom = geojson.get("geometry", geojson)
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return False
    point = (lon, lat)  # GeoJSON is [lon, lat]
    try:
        if gtype == "Polygon":
            return _ring_contains(point, coords[0])
        if gtype == "MultiPolygon":
            return any(_ring_contains(point, poly[0]) for poly in coords)
    except (IndexError, TypeError):
        return False
    return False


def match_lot(db: Session, latitude: Optional[float], longitude: Optional[float]) -> Optional[Lot]:
    if latitude is None or longitude is None:
        return None

    lots = db.execute(select(Lot)).scalars().all()

    # 1) polygon containment
    for lot in lots:
        if lot.polygon_geojson and _polygon_contains(lot.polygon_geojson, latitude, longitude):
            logger.info("Observation matched lot %s by polygon", lot.lot_code)
            return lot

    # 2) nearest centroid within radius
    best, best_dist = None, MAX_MATCH_KM
    for lot in lots:
        if lot.centroid_latitude is None or lot.centroid_longitude is None:
            continue
        d = _haversine_km(latitude, longitude, lot.centroid_latitude, lot.centroid_longitude)
        if d <= best_dist:
            best, best_dist = lot, d
    if best:
        logger.info("Observation matched lot %s by centroid (%.2f km)", best.lot_code, best_dist)
    return best
