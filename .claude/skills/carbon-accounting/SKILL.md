---
name: carbon-accounting
description: Implement carbon factor snapshots, planned vs actual carbon calculations, carbon reports, missing-data states, and manual overrides for Agave Field. Use for anything touching kgCO2e.
---

# carbon-accounting

## When to use
Computing/reporting carbon, snapshotting factors, or building carbon dashboards.

## Instructions
- Factors are **manually defined** in the Activity/Product catalogs. Never invent them,
  never use AI, never call external carbon APIs.
- Use `app/services/carbon_service.py`:
  `compute_carbon(activity_factor_*, product_factor_*, surface_*, total_product_*)`
  → `(total_kgco2e, status, snapshot)`. Units: `kgCO2e_per_ha|_m2|_kg_product|_liter|_event`.
- **Snapshot at write time:** copy the factor + inputs into `WorkOrderItem`
  (planned) and `ExecutionRecord` (actual). Historical records must NOT change when the
  catalog factor changes later.
- Status values: `calculated`, `missing_data` (factor present but input absent),
  `no_factor`. Surface KPIs for `missing_data` records.
- **Manual override** only with value + reason + user + timestamp; audit-log it
  (`override_carbon`).

## Constraints
- No recomputation of old records. No fabricated factors. No external carbon calls.

## Output
Deterministic carbon math, preserved snapshots, and reports (by season/field/lot/zone/
activity/product/date, planned vs actual, per-hectare, top contributors, missing-data).
