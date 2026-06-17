import { FlaskConical } from "lucide-react";

export function DemoBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-clay/30 bg-clay-light px-2.5 py-1 text-xs font-medium text-clay">
      <FlaskConical className="h-3.5 w-3.5" />
      Demo data
    </span>
  );
}
