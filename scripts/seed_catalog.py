"""Bulk-load REAL product & activity catalogs from CSV.

This tool does NOT invent data. Carbon factors must be YOUR values (from your own
methodology). Empty cells are skipped. Run against your configured DATABASE_URL.

Usage:
  python -m scripts.seed_catalog --products my_products.csv --activities my_activities.csv

Templates: scripts/catalog_products.template.csv, scripts/catalog_activities.template.csv
"""
from __future__ import annotations

import argparse
import csv

from app.db import SessionLocal, init_db
from app.services import catalog_service

_FLOAT = {"carbon_factor_value", "default_dose_value", "min_dose_value", "max_dose_value"}
_BOOL = {"allowed", "restricted", "prohibited", "active", "requires_product",
         "requires_photo_evidence", "requires_geolocation", "requires_surface_area",
         "requires_dose", "requires_weather_snapshot"}
_INT = {"default_required_photo_count", "default_follow_up_days"}


def _clean(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if v is None or str(v).strip() == "":
            continue
        v = str(v).strip()
        if k in _FLOAT:
            out[k] = float(v)
        elif k in _INT:
            out[k] = int(v)
        elif k in _BOOL:
            out[k] = v.lower() in ("1", "true", "yes", "y")
        else:
            out[k] = v
    return out


def _load(path: str, creator) -> int:
    n = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            data = _clean(row)
            if not data:
                continue
            creator(data)
            n += 1
    return n


def run(products: str | None, activities: str | None) -> None:
    init_db()
    db = SessionLocal()
    try:
        if products:
            n = _load(products, lambda d: catalog_service.create_product(db, d, actor="seed"))
            print(f"Loaded {n} products")
        if activities:
            n = _load(activities, lambda d: catalog_service.create_activity(db, d, actor="seed"))
            print(f"Loaded {n} activities")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--products")
    ap.add_argument("--activities")
    args = ap.parse_args()
    if not args.products and not args.activities:
        ap.error("provide --products and/or --activities")
    run(args.products, args.activities)
