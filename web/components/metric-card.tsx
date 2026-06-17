import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

export function MetricCard({
  icon: Icon,
  label,
  value,
  sublabel,
  accent = "agave",
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  sublabel?: string;
  accent?: "agave" | "clay" | "info" | "warn";
}) {
  const tint = {
    agave: "bg-agave-light text-agave-deep",
    clay: "bg-clay-light text-clay",
    info: "bg-[#E1EEF4] text-info",
    warn: "bg-[#FBEFD9] text-warn",
  }[accent];
  return (
    <Card className="p-5">
      <div className="flex items-center gap-3">
        <span className={cn("flex h-10 w-10 items-center justify-center rounded-xl", tint)}>
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</p>
          <p className="text-2xl font-semibold leading-tight text-ink">{value}</p>
          {sublabel && <p className="truncate text-xs text-ink-muted">{sublabel}</p>}
        </div>
      </div>
    </Card>
  );
}
