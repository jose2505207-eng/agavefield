"use client";

import { useEffect, useState } from "react";
import { CheckSquare, MapPin, MapPinOff, Leaf, CloudRain, Check, X, RotateCcw } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { DemoBadge } from "@/components/demo-badge";
import { listReviewQueue, reviewAction } from "@/lib/api";
import { DEMO_REVIEW } from "@/lib/demo";
import { kg } from "@/lib/utils";

export default function ReviewPage() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [isDemo, setIsDemo] = useState(false);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  async function load() {
    try {
      const q = await listReviewQueue();
      if (Array.isArray(q) && q.length) { setRows(q); setIsDemo(false); }
      else { setRows(DEMO_REVIEW); setIsDemo(true); }
    } catch { setRows(DEMO_REVIEW); setIsDemo(true); }
  }
  useEffect(() => { load(); }, []);

  async function act(id: number, action: "approve" | "reject" | "request-correction") {
    try {
      await reviewAction(id, action, { reviewer_name: "dashboard", reviewer_notes: notes[id] || null });
      setMsg({ text: `Execution #${id}: ${action.replace("-", " ")} recorded`, ok: true });
      load();
    } catch (e: any) { setMsg({ text: e.message, ok: false }); }
  }

  return (
    <>
      <PageHeader
        title="Review Queue"
        subtitle="Approve, reject, or request corrections — submitted records are never overwritten"
        actions={isDemo ? <DemoBadge /> : undefined}
      />

      {msg && (
        <div className={`mb-4 rounded-xl border p-3 text-sm ${msg.ok ? "border-agave/30 bg-agave-light text-agave-deep" : "border-danger/30 bg-[#F7E0E0] text-danger"}`}>
          {msg.text}
        </div>
      )}

      {rows === null ? (
        <div className="space-y-3">{[0, 1].map((i) => <div key={i} className="h-40 animate-pulse rounded-2xl border border-line bg-white" />)}</div>
      ) : rows.length === 0 ? (
        <EmptyState icon={CheckSquare} title="Queue empty" description="All submitted field work has been reviewed." />
      ) : (
        <div className="space-y-4">
          {rows.map((e) => (
            <Card key={e.id}>
              <CardContent className="py-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-ink-muted">Execution #{e.id}</span>
                    <Badge variant={e.compliance_status === "needs_correction" ? "warn" : "info"}>
                      {String(e.compliance_status).replace("_", " ")}
                    </Badge>
                    <span className="text-xs text-ink-muted">WO {e.work_order_id}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-ink-muted">
                    <span className="inline-flex items-center gap-1"><Leaf className="h-3.5 w-3.5 text-agave" />{kg(e.actual_carbon_kgco2e)} kgCO₂e ({e.carbon_calculation_status})</span>
                    <span className="inline-flex items-center gap-1">{e.gps_latitude ? <MapPin className="h-3.5 w-3.5 text-agave" /> : <MapPinOff className="h-3.5 w-3.5 text-warn" />}{e.gps_latitude ? "GPS" : "no GPS"}</span>
                    <span className="inline-flex items-center gap-1"><CloudRain className="h-3.5 w-3.5 text-info" />{e.weather_snapshot_status}</span>
                  </div>
                </div>
                <p className="mt-2 text-sm text-ink">📝 {e.manual_note || "—"}</p>
                <p className="mt-1 text-xs text-ink-muted">
                  Surface: {e.actual_surface_area_value ?? "—"} {e.actual_surface_area_unit || ""}
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <input
                    className="min-w-0 flex-1 rounded-xl border border-line bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-agave-ring"
                    placeholder="Reviewer notes (optional)"
                    value={notes[e.id] || ""}
                    onChange={(ev) => setNotes((n) => ({ ...n, [e.id]: ev.target.value }))}
                  />
                  <Button size="sm" disabled={isDemo} onClick={() => act(e.id, "approve")}><Check className="h-4 w-4" /> Approve</Button>
                  <Button size="sm" variant="secondary" disabled={isDemo} onClick={() => act(e.id, "request-correction")}><RotateCcw className="h-4 w-4" /> Correction</Button>
                  <Button size="sm" variant="ghost" disabled={isDemo} onClick={() => act(e.id, "reject")}><X className="h-4 w-4" /> Reject</Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {isDemo && <p className="mt-4 text-center text-xs text-ink-muted">Showing demo submissions — actions activate with live data.</p>}
    </>
  );
}
