---
name: agave-traceability
description: Model agave-specific field records — lots, zones, seasons, activities, products, work orders, executions, photo evidence, weather, and timeline events. Use when shaping domain data or the field history.
---

# agave-traceability

## When to use
Designing/extending domain records or the timeline/passport history.

## Instructions
- Entity mapping: field=`farms`, lot=`lots`, zone=`field_zones`, passport=`agave_passports`,
  season=`work_orders.season_id` (no Season table yet — optional int).
- A `WorkOrder` groups `WorkOrderItem`s (activity + optional product + planned
  dose/surface/carbon). A worker submits an `ExecutionRecord` per item with actuals,
  GPS, weather, photos, carbon.
- The **timeline** (`TimelineEvent`) is the permanent life history of a field/lot/zone/
  passport: write an event for work_order_created/sent, activity_submitted/approved,
  product_applied, photo_uploaded, weather_captured, carbon_calculated,
  correction_requested, follow_up_created, note.
- Evidence (`PhotoEvidence`) must stay linked to its execution + work order + location.
  Preserve `gps_source` (device|exif|manual|unavailable).

## Constraints
- No AI interpretation of photos. Humans + structured fields are the source of truth.
- Never detach evidence or rewrite history; corrections create revisions.

## Output
Domain models/queries that keep a faithful, immutable field history.
