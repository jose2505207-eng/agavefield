---
name: field-workorders
description: Implement work-order generation, checklist items, assignee links, secure email delivery, mobile completion forms, and worker submission flows for Agave Field. Use for the core work-order lifecycle.
---

# field-workorders

## When to use
Building work-order creation, sending links, mobile completion, or submission/review.

## Instructions
- **Create:** `WorkOrder` + N `WorkOrderItem`s. On item create, snapshot the activity/
  product carbon factor and compute `planned_carbon_kgco2e` if planned surface/product
  given. Generate `work_order_code` (e.g. `WO-YYYY-####`). Audit `create`.
- **Send:** generate a random token, store only `secure_access_token_hash` (sha256), set
  `secure_link_expires_at` (optional), build `APP_BASE_URL/work-orders/complete/{token}`,
  send via `EmailService` (provider abstraction: console/smtp/sendgrid/resend; console is
  dev-only), set `sent_at`, status→`sent`, audit `send_email`.
- **Complete (mobile):** `GET /work-orders/complete/{token}` validates the hashed token +
  expiry, renders only that work order. Worker enters actuals, captures photo+GPS, app
  pulls weather; `POST .../submit` creates an immutable `ExecutionRecord`, links photos +
  `OpsWeatherSnapshot`, computes `actual_carbon_kgco2e`, status→`submitted`, audit `submit`.
- Respect per-item requirement flags (photo count, geolocation, weather, manual note).
  If a required item is missing → block submission or mark `needs_correction` per config.

## Constraints
- Workers never see the admin dashboard. Token is hashed at rest. No AI on photos.
- Execution records are immutable; corrections create revisions.

## Output
A working order → email → mobile checklist → submission → review-ready pipeline.
