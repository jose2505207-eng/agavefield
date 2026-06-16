"""Carbon footprint traceability.

Carbon factors are MANUALLY defined in the Activity/Product catalogs — never
AI-estimated and never invented here. This module only applies stored factors
to actual surface / product / event data, and preserves the exact factor used
as an immutable snapshot on the work-order item and execution record.

Supported factor units:
  kgCO2e_per_ha, kgCO2e_per_m2, kgCO2e_per_kg_product, kgCO2e_per_liter, kgCO2e_per_event
"""
from __future__ import annotations

from typing import Optional, Tuple

HECTARE_IN_M2 = 10_000.0


def _normalize_surface(value: Optional[float], unit: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Return (ha, m2) from a surface value+unit."""
    if value is None or unit is None:
        return None, None
    u = unit.lower()
    if u == "ha":
        return value, value * HECTARE_IN_M2
    if u == "m2":
        return value / HECTARE_IN_M2, value
    return None, None


def _normalize_product(value: Optional[float], unit: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Return (kg, liters) from a total-product value+unit."""
    if value is None or unit is None:
        return None, None
    u = unit.lower()
    if u in ("kg", "kilogram", "kilograms"):
        return value, None
    if u in ("l", "liter", "liters", "litre", "litres"):
        return None, value
    return None, None


def calculate_single(
    factor_value: Optional[float],
    factor_unit: Optional[str],
    *,
    surface_ha: Optional[float] = None,
    surface_m2: Optional[float] = None,
    total_product_kg: Optional[float] = None,
    total_product_l: Optional[float] = None,
) -> Tuple[Optional[float], str]:
    """Apply one factor. Returns (kgCO2e | None, status)."""
    if factor_value is None or not factor_unit:
        return None, "no_factor"
    u = factor_unit.lower()
    if u == "kgco2e_per_ha":
        return (factor_value * surface_ha, "calculated") if surface_ha is not None else (None, "missing_data")
    if u == "kgco2e_per_m2":
        return (factor_value * surface_m2, "calculated") if surface_m2 is not None else (None, "missing_data")
    if u == "kgco2e_per_kg_product":
        return (factor_value * total_product_kg, "calculated") if total_product_kg is not None else (None, "missing_data")
    if u == "kgco2e_per_liter":
        return (factor_value * total_product_l, "calculated") if total_product_l is not None else (None, "missing_data")
    if u == "kgco2e_per_event":
        return factor_value, "calculated"
    return None, "unknown_unit"


def compute_carbon(
    *,
    activity_factor_value: Optional[float] = None,
    activity_factor_unit: Optional[str] = None,
    product_factor_value: Optional[float] = None,
    product_factor_unit: Optional[str] = None,
    surface_value: Optional[float] = None,
    surface_unit: Optional[str] = None,
    total_product_value: Optional[float] = None,
    total_product_unit: Optional[str] = None,
) -> Tuple[Optional[float], str, dict]:
    """Compute total kgCO2e = activity contribution + product contribution.

    Returns (total | None, status, snapshot). Status is:
      - "calculated": at least one factor applied and no required data was missing
      - "missing_data": a factor exists but its required input is absent
      - "no_factor": neither activity nor product has a carbon factor
    """
    surface_ha, surface_m2 = _normalize_surface(surface_value, surface_unit)
    total_kg, total_l = _normalize_product(total_product_value, total_product_unit)

    act_co2, act_status = calculate_single(
        activity_factor_value, activity_factor_unit,
        surface_ha=surface_ha, surface_m2=surface_m2,
        total_product_kg=total_kg, total_product_l=total_l,
    )
    prod_co2, prod_status = calculate_single(
        product_factor_value, product_factor_unit,
        surface_ha=surface_ha, surface_m2=surface_m2,
        total_product_kg=total_kg, total_product_l=total_l,
    )

    contributions = [c for c in (act_co2, prod_co2) if c is not None]
    statuses = {s for s in (act_status, prod_status)}

    if act_status == "no_factor" and prod_status == "no_factor":
        status = "no_factor"
        total = None
    elif "missing_data" in statuses and not contributions:
        status = "missing_data"
        total = None
    elif "missing_data" in statuses:
        # Some computed, some missing — flag for review but keep partial total.
        status = "missing_data"
        total = round(sum(contributions), 4)
    else:
        status = "calculated"
        total = round(sum(contributions), 4)

    snapshot = {
        "activity_factor_value": activity_factor_value,
        "activity_factor_unit": activity_factor_unit,
        "activity_co2e": act_co2,
        "product_factor_value": product_factor_value,
        "product_factor_unit": product_factor_unit,
        "product_co2e": prod_co2,
        "surface_value": surface_value,
        "surface_unit": surface_unit,
        "total_product_value": total_product_value,
        "total_product_unit": total_product_unit,
    }
    return total, status, snapshot
