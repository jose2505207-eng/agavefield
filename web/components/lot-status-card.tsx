import { Badge } from "@/components/ui/badge";
import { Sprout } from "lucide-react";
import type { LotStatus } from "@/lib/types";

const RISK = {
  low: { label: "Low risk", variant: "ok" as const },
  medium: { label: "Watch", variant: "warn" as const },
  high: { label: "High risk", variant: "danger" as const },
};

export function LotStatusCard({ lot }: { lot: LotStatus }) {
  const r = RISK[lot.risk];
  return (
    <div className="rounded-xl border border-line bg-white p-4 transition-shadow hover:shadow-card">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-agave-light text-agave-deep">
            <Sprout className="h-4 w-4" />
          </span>
          <div>
            <p className="text-sm font-semibold text-ink">{lot.code}</p>
            <p className="text-xs text-ink-muted">{lot.field}</p>
          </div>
        </div>
        <Badge variant={r.variant}>{r.label}</Badge>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-ink-muted">
        <span>{lot.openWorkOrders} open WO</span>
        <span>{lot.lastActivity ?? "—"}</span>
      </div>
    </div>
  );
}
