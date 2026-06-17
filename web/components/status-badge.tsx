import { Badge } from "@/components/ui/badge";
import type { WorkOrderStatus } from "@/lib/types";

const MAP: Record<WorkOrderStatus, { label: string; variant: any }> = {
  draft: { label: "Draft", variant: "muted" },
  scheduled: { label: "Scheduled", variant: "info" },
  sent: { label: "Sent", variant: "info" },
  in_progress: { label: "In progress", variant: "agave" },
  submitted: { label: "Submitted", variant: "warn" },
  approved: { label: "Approved", variant: "ok" },
  rejected: { label: "Rejected", variant: "danger" },
  needs_correction: { label: "Needs correction", variant: "warn" },
  completed: { label: "Completed", variant: "ok" },
  cancelled: { label: "Cancelled", variant: "muted" },
};

export function StatusBadge({ status }: { status: WorkOrderStatus }) {
  const s = MAP[status] ?? { label: status, variant: "muted" };
  return <Badge variant={s.variant}>{s.label}</Badge>;
}
