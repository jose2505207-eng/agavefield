"use client";

import { useEffect, useState } from "react";
import {
  ClipboardList, Users2, Mail, CheckSquare, Leaf, BarChart3, ScrollText,
  AlertTriangle, ImageOff,
} from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { DemoBadge } from "@/components/demo-badge";
import { DemoProfileSwitcher } from "@/components/demo-profile-switcher";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth";
import { listWorkOrders } from "@/lib/api";
import { DEMO_DASHBOARDS, type DemoWO, type Card as DemoCard } from "@/lib/demo-rbac";
import type { OrgRole } from "@/lib/rbac";

// Map a live API work order into the display shape used by the tables.
function toRow(w: any): DemoWO {
  return {
    code: w.work_order_code,
    title: w.title,
    status: w.status,
    lot: w.lot_id ? `Lot ${w.lot_id}` : "—",
    assignee: w.assigned_to_email || "—",
    due: w.due_date?.slice(0, 10) || "—",
    evidence: "partial",
  };
}

function Cards({ cards }: { cards: DemoCard[] }) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 xl:grid-cols-6">
      {cards.map((c) => (
        <MetricCard
          key={c.label}
          icon={ClipboardList}
          label={c.label}
          value={c.value}
          accent={c.accent}
          sublabel={c.sub}
        />
      ))}
    </div>
  );
}

function WorkOrderTable({ rows, title }: { rows: DemoWO[]; title: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <EmptyState icon={ClipboardList} title="No work orders" description="Work in your scope will appear here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                  <th className="py-2 pr-3 font-medium">Code</th>
                  <th className="py-2 pr-3 font-medium">Title</th>
                  <th className="py-2 pr-3 font-medium">Lot</th>
                  <th className="py-2 pr-3 font-medium">Assignee</th>
                  <th className="py-2 pr-3 font-medium">Due</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 font-medium">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((w) => (
                  <tr key={w.code} className="border-b border-line/60 last:border-0">
                    <td className="py-2.5 pr-3 font-mono text-xs text-ink-soft">{w.code}</td>
                    <td className="py-2.5 pr-3 text-ink">{w.title}</td>
                    <td className="py-2.5 pr-3 text-ink-soft">{w.lot}</td>
                    <td className="py-2.5 pr-3 text-ink-soft">{w.assignee}</td>
                    <td className="py-2.5 pr-3 text-ink-soft">{w.due}</td>
                    <td className="py-2.5 pr-3"><StatusBadge status={w.status as any} /></td>
                    <td className="py-2.5">
                      <Badge variant={w.evidence === "complete" ? "ok" : w.evidence === "missing" ? "danger" : "warn"}>
                        {w.evidence}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------------- //
// Role-specific extra panels (demo data only; honest empty otherwise)
// --------------------------------------------------------------------------- //
function LaborPanel({ role }: { role: OrgRole }) {
  const d = DEMO_DASHBOARDS[role];
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>Labor by activity</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {d.labor?.map((l) => (
            <div key={l.activity} className="flex items-center justify-between text-sm">
              <span className="text-ink">{l.activity}</span>
              <span className="text-ink-muted">{l.hours}h · {l.workers} workers</span>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Product usage & carbon</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {d.products?.map((p) => (
            <div key={p.product} className="flex items-center justify-between text-sm">
              <span className="text-ink">{p.product}</span>
              <span className="text-ink-muted">{p.used} · {p.carbon} kgCO₂e</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function AuditPanel({ role }: { role: OrgRole }) {
  const d = DEMO_DASHBOARDS[role];
  return (
    <Card>
      <CardHeader><CardTitle>Audit trail (recent)</CardTitle></CardHeader>
      <CardContent className="space-y-2">
        {d.audit?.map((a, i) => (
          <div key={i} className="flex items-center justify-between border-b border-line/60 py-2 text-sm last:border-0">
            <span className="text-ink">
              <span className="font-medium">{a.actor}</span>{" "}
              <span className="text-ink-muted">{a.action}</span>{" "}
              <span className="font-mono text-xs text-ink-soft">{a.entity}</span>
            </span>
            <span className="text-xs text-ink-muted">{a.at}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------------- //
// Dispatcher
// --------------------------------------------------------------------------- //
export function RoleBasedDashboard() {
  const { ctx, isDemo, loading } = useAuth();
  const role: OrgRole = ctx?.dashboard?.role ?? "worker";
  const [liveRows, setLiveRows] = useState<DemoWO[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (isDemo) {
      setLiveRows(null);
      return;
    }
    setError(false);
    listWorkOrders()
      .then((rows: any[]) => setLiveRows(Array.isArray(rows) ? rows.map(toRow) : []))
      .catch(() => setError(true));
  }, [loading, isDemo]);

  if (loading) {
    return <DashboardSkeleton title="Loading your workspace…" />;
  }

  const demo = DEMO_DASHBOARDS[role];
  const rows: DemoWO[] = isDemo ? demo.workOrders : liveRows ?? [];
  const title = ctx?.dashboard?.title ?? "My Field Work";

  // For real accounts, derive simple counts from the live (scoped) work orders.
  const liveCards: DemoCard[] = [
    { label: "Open", value: rows.filter((r) => ["draft", "scheduled", "sent", "in_progress"].includes(r.status)).length, accent: "agave" },
    { label: "Submitted", value: rows.filter((r) => r.status === "submitted").length, accent: "clay", sub: "awaiting review" },
    { label: "Approved", value: rows.filter((r) => ["approved", "completed"].includes(r.status)).length, accent: "info" },
    { label: "Needs correction", value: rows.filter((r) => r.status === "needs_correction").length, accent: "warn" },
  ];
  const cards = isDemo ? demo.cards : liveCards;

  const tableTitle =
    role === "worker" ? "My work orders"
    : role === "supervisor" ? "Team work orders"
    : role === "auditor" ? "Work order history"
    : "Work orders";

  return (
    <>
      <PageHeader
        title={title}
        subtitle={ctx?.organization?.name ?? "Agave field operations"}
        actions={
          <div className="flex items-center gap-2">
            {isDemo && <DemoBadge />}
            <DemoProfileSwitcher />
          </div>
        }
      />

      {error && !isDemo ? (
        <EmptyState icon={AlertTriangle} title="Couldn't load data"
          description="The API is unreachable. Check NEXT_PUBLIC_API_BASE_URL." />
      ) : (
        <div className="space-y-6">
          <Cards cards={cards} />

          {(role === "engineer" || role === "admin") && isDemo && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <SummaryStat icon={Leaf} label="Carbon planned" value={`${(demo.carbon!.plannedKg / 1000).toFixed(2)} t`} />
              <SummaryStat icon={Leaf} label="Carbon actual" value={`${(demo.carbon!.actualKg / 1000).toFixed(2)} t`} />
              <SummaryStat icon={BarChart3} label="Per hectare" value={`${demo.carbon!.perHa} kg`} />
              <SummaryStat icon={ImageOff} label="Missing carbon data" value={demo.carbon!.missing} />
            </div>
          )}

          <WorkOrderTable rows={rows} title={tableTitle} />

          {role === "engineer" && isDemo && <LaborPanel role={role} />}

          {role === "admin" && isDemo && (
            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader><CardTitle>Members</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {demo.members?.map((m) => (
                    <div key={m.name} className="flex items-center justify-between text-sm">
                      <span className="text-ink">{m.name}</span>
                      <span className="text-ink-muted">{m.role} · {m.scope}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Active invitations</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {demo.invites?.map((i) => (
                    <div key={i.email} className="flex items-center justify-between text-sm">
                      <span className="text-ink">{i.email}</span>
                      <span className="text-ink-muted">{i.role} · expires {i.expires}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          )}

          {(role === "admin" || role === "auditor") && isDemo && <AuditPanel role={role} />}

          {!isDemo && (
            <p className="text-xs text-ink-muted">
              Showing live data scoped to your role ({ctx?.dashboard?.data_scope}). Empty
              sections mean no records yet — nothing is fabricated.
            </p>
          )}
        </div>
      )}
    </>
  );
}

function SummaryStat({ icon: Icon, label, value }: { icon: any; label: string; value: string | number }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-ink-muted">
        <Icon className="h-4 w-4" />
        <span className="text-xs uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-1 text-xl font-semibold text-ink">{value}</p>
    </Card>
  );
}

function DashboardSkeleton({ title }: { title: string }) {
  return (
    <>
      <PageHeader title={title} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-2xl border border-line bg-white" />
        ))}
      </div>
      <div className="mt-6 h-80 animate-pulse rounded-2xl border border-line bg-white" />
    </>
  );
}
