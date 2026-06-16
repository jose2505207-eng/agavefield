---
name: product-architect
description: Plan product flows, data architecture, module boundaries, and phased delivery for Agave Field. Use when scoping a feature, deciding what to build next, or designing how work orders, evidence, review, and carbon reporting fit together.
---

# product-architect

## When to use
Planning a new module or flow; deciding the smallest safe slice; designing data/
service boundaries; sequencing phased delivery. Use before writing code.

## Instructions
- Keep the product focused on the core equation: Work Order → Assigned Checklist →
  Product/Activity control → Dose/Surface → Photo/GPS evidence → Weather snapshot →
  Carbon factor → Review approval → Audit trail.
- Map domain to existing entities: field=`farms`, lot=`lots`, zone=`field_zones`,
  passport=`agave_passports`. Reuse `app/models/operations.py` models — they already
  cover the whole flow.
- Define vertical slices (model → service → schema → route → dashboard) that ship one
  capability end-to-end, not horizontal layers that can't be demoed.
- Phase order: catalogs/assignees (done) → work-order generation + email send →
  mobile completion (photo/GPS/weather/carbon) → review queue → timeline → carbon
  dashboard + evidence gallery → audit views.

## Constraints
- No LLM image analysis. No stack change. No big-bang rewrites.
- Every plan must preserve immutability of executions and carbon snapshots.

## Output
A short plan: the slice, files touched, data/service changes, the test that proves it,
and what is explicitly deferred.
