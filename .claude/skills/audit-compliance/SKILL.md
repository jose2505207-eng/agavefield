---
name: audit-compliance
description: Implement audit logs, revision history, soft deletes, reviewer approvals, immutable records, and FDA-style traceability behavior for Agave Field. Use for anything about accountability or record integrity.
---

# audit-compliance

## When to use
Adding audit logging, review/approval flows, soft deletes, or revision history.

## Instructions
- **Audit everything meaningful** via `audit_service.log(db, entity_type=, entity_id=,
  action=, old_values=, new_values=, changed_by=, reason=)`. Actions: create, update,
  submit, approve, reject, request_correction, send_email, upload_photo, calculate_carbon,
  override_carbon, deactivate, soft_delete.
- **Immutable executions:** never overwrite a submitted `ExecutionRecord`. A correction
  creates a NEW record with `is_revision_of_id` pointing at the original; keep both.
- **Review:** store reviewer identity + timestamp + notes + status (`pending, approved,
  partial, rejected, needs_correction`) in `Review`; do not mutate the execution's
  submitted fields.
- **Deletes:** never hard-delete records tied to execution/product/carbon/evidence;
  deactivate (`active=False`) or soft delete (`deleted_at`). `catalog_service` already
  enforces deactivate-when-referenced.
- Do not claim official FDA compliance — implement the principles (controlled records,
  required fields, approval, immutable history, evidence preservation, accountability).

## Constraints
- Audit log is append-only. Timestamps consistent (UTC). Snapshots preserved.

## Output
A defensible, reconstructable history for every record + visible audit trail.
