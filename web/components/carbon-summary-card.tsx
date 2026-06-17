import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Leaf } from "lucide-react";
import { kg } from "@/lib/utils";
import type { CarbonSummary } from "@/lib/types";

export function CarbonSummaryCard({ carbon }: { carbon: CarbonSummary }) {
  const pct = carbon.plannedKg > 0
    ? Math.min(100, Math.round((carbon.actualKg / carbon.plannedKg) * 100))
    : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Carbon footprint</CardTitle>
        <Badge variant="agave"><Leaf className="h-3.5 w-3.5" /> traceability</Badge>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between">
          <div>
            <p className="text-3xl font-semibold text-ink">{kg(carbon.actualKg)}</p>
            <p className="text-xs text-ink-muted">kgCO₂e actual · planned {kg(carbon.plannedKg)}</p>
          </div>
          <div className="text-right">
            <p className="text-lg font-semibold text-agave-deep">{carbon.perHa != null ? kg(carbon.perHa) : "—"}</p>
            <p className="text-xs text-ink-muted">kgCO₂e / ha</p>
          </div>
        </div>
        <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-sand">
          <div className="h-full rounded-full bg-agave" style={{ width: `${pct}%` }} />
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-ink-muted">
          <span>Top: {carbon.topActivity ?? "—"}</span>
          {carbon.missingData > 0
            ? <Badge variant="warn">{carbon.missingData} missing data</Badge>
            : <span className="text-agave-deep">complete</span>}
        </div>
      </CardContent>
    </Card>
  );
}
