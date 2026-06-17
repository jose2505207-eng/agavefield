import { StatusBadge } from "@/components/status-badge";
import { MapPin, CalendarClock, User } from "lucide-react";
import type { WorkOrderLite } from "@/lib/types";

export function WorkOrderCard({ wo }: { wo: WorkOrderLite }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-line bg-white p-4 transition-shadow hover:shadow-card">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-ink-muted">{wo.code}</span>
          <StatusBadge status={wo.status} />
        </div>
        <p className="mt-1 truncate text-sm font-medium text-ink">{wo.title}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
          {wo.lot && <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{wo.lot}</span>}
          {wo.due && <span className="inline-flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" />{wo.due}</span>}
          {wo.assignee && <span className="inline-flex items-center gap-1"><User className="h-3.5 w-3.5" />{wo.assignee}</span>}
        </div>
      </div>
    </div>
  );
}
