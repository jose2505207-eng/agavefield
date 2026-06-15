"""Seed a sample farm + lots in Jalisco for local testing.

Usage: python -m scripts.seed
"""
from __future__ import annotations

from app.db import SessionLocal, init_db
from app.models.database import Farm, Lot


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.query(Farm).first():
            print("Seed data already present; skipping.")
            return
        farm = Farm(
            name="Rancho El Agave",
            municipality="Tequila",
            state="Jalisco",
            owner_name="Cooperativa Demo",
        )
        db.add(farm)
        db.flush()
        lots = [
            Lot(
                farm_id=farm.id,
                lot_code="TEQ-01",
                crop_type="agave_azul",
                estimated_age_months=36,
                centroid_latitude=20.8806,
                centroid_longitude=-103.8366,
            ),
            Lot(
                farm_id=farm.id,
                lot_code="TEQ-02",
                crop_type="agave_azul",
                estimated_age_months=18,
                centroid_latitude=20.8901,
                centroid_longitude=-103.8412,
            ),
        ]
        db.add_all(lots)
        db.commit()
        print(f"Seeded farm '{farm.name}' with {len(lots)} lots.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
