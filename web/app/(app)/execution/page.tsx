"use client";

import { useEffect, useState } from "react";
import { Tractor, MapPin, MapPinOff, Leaf, CloudRain, ClipboardCheck, AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { DemoBadge } from "@/components/demo-badge";
import { listExecutions } from "@/lib/api";
import { DEMO_EXECUTIONS } from "@/lib/demo";
import { kg } from "@/lib/utils";

// Compliance lanes — submitted field work flows left→right toward approval.
const LANES: { key: string; label: string; variant: any }[] = [
  { key: "pending_review", label: "Pending review", variant: "info" },
  { key: "needs_correction", label: "Needs correction", variant: "warn" },
  { key: "compliant", label: "Compliant", variant: "ok" },
];

function fmtDate(v?: string | null) {
  if (!v) return null;
  const d = new Date(v);
  return isNaN(+d) ? String(v).slice(0, 16).replace("T", " ") : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function ExecutionPage() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [isDemo, setIsDemo] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await listExecutions();
        if (Array.isArray(r) && r.length) { setRows(r); setIsDemo(false); }
        else { setRows(DEMO_EXECUTIONS); setIsDemo(true); }
      } catch { setRows(DEMO_EXECUTIONS); setIsDemo(true); }
    })();
  }, []);

  const lanes = LANES.map((l) => ({
    ...l,
    items: (rows ?? []).filter((r) => (r.compliance_status ?? "pending_review") === l.key),
  }));

  return (
    <>
      <PageHeader
        title="Field Execution"
        subtitle="Submitted field work with actual measurements, GPS, weather, and carbon — immutable evidence, reviewed by humans"
        actions={isDemo ? <DemoBadge /> : undefined}
      />

      {rows === null ? (
        <div className="grid gap-4 lg:grid-cols-3">
          {[0, 1, 2].map((i) => <div key={i} className="h-64 animate-pulse rounded-2xl border border-line bg-white" />)}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState icon={Tractor} title="No submissions yet"
          description="When workers complete and submit their assigned work orders, their records appear here for review." />
      ) : (
        <div className="grid gap-5 lg:grid-cols-3">
          {lanes.map((lane) => (
            <div key={lane.key} className="min-w-0">
              <div className="mb-3 flex items-center gap-2">
                <Badge variant={lane.variant}>{lane.label}</Badge>
                <span className="text-xs text-ink-muted">{lane.items.length}</span>
              </div>
              <div className="space-y-3">
                {lane.items.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-line bg-white/50 px-3 py-6 text-center text-xs text-ink-muted">Nothing here</p>
                ) : (
                  lane.items.map((e) => <ExecutionCard key={e.id} e={e} />)
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      {isDemo && <p className="mt-4 text-center text-xs text-ink-muted">Showing demo submissions — live records appear as workers submit.</p>}
    </>
  );
}

function ExecutionCard({ e }: { e: any }) {
  const carbonMissing = e.carbon_calculation_status === "missing_data" || e.actual_carbon_kgco2e == null;
  const submitted = fmtDate(e.submitted_at ?? e.execution_completed_at);
  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-xs text-ink-muted">Exec #{e.id}</span>
          <span className="text-xs text-ink-muted">WO {e.work_order_id}</span>
        </div>
        <p className="mt-2 line-clamp-2 text-sm text-ink">{e.manual_note || "No note provided"}</p>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-ink-muted">
          <span className="inline-flex items-center gap-1">
            <Leaf className={`h-3.5 w-3.5 ${carbonMissing ? "text-warn" : "text-agave"}`} />
            {carbonMissing ? "carbon pending" : `${kg(e.actual_carbon_kgco2e)} kgCO₂e`}
          </span>
          <span className="inline-flex items-center gap-1">
            {e.gps_latitude ? <MapPin className="h-3.5 w-3.5 text-agave" /> : <MapPinOff className="h-3.5 w-3.5 text-warn" />}
            {e.gps_latitude ? "GPS" : "no GPS"}
          </span>
          <span className="inline-flex items-center gap-1">
            <CloudRain className="h-3.5 w-3.5 text-info" />{e.weather_snapshot_status ?? "—"}
          </span>
        </div>
        {(e.actual_surface_area_value != null) && (
          <p className="mt-2 inline-flex items-center gap-1 text-xs text-ink-soft">
            <ClipboardCheck className="h-3.5 w-3.5" />
            {e.actual_surface_area_value} {e.actual_surface_area_unit || ""}
          </p>
        )}
        {carbonMissing && (
          <p className="mt-2 inline-flex items-center gap-1 text-xs text-warn">
            <AlertTriangle className="h-3.5 w-3.5" /> Carbon data incomplete
          </p>
        )}
        {submitted && <p className="mt-2 text-[11px] text-ink-muted">Submitted {submitted}</p>}
      </CardContent>
    </Card>
  );
}
