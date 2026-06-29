"use client";

import { useEffect, useState } from "react";
import { ClipboardList, Plus, Send, MapPin, CalendarClock, User } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status-badge";
import { EmptyState } from "@/components/empty-state";
import { DemoBadge } from "@/components/demo-badge";
import {
  getWorkOrders, listActivities, listAssignees, createWorkOrder, sendWorkOrder,
} from "@/lib/api";
import { DEMO_WORK_ORDERS } from "@/lib/demo";

const OPEN = ["draft", "scheduled", "sent", "in_progress"];

export default function WorkOrdersPage() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [isDemo, setIsDemo] = useState(false);
  const [activities, setActivities] = useState<any[]>([]);
  const [assignees, setAssignees] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  async function load() {
    try {
      const [wo, acts, asg] = await Promise.all([getWorkOrders(), listActivities(), listAssignees()]);
      setActivities(Array.isArray(acts) ? acts : []);
      setAssignees(Array.isArray(asg) ? asg : []);
      setRows(wo.data);
      setIsDemo(wo.isDemo);
    } catch {
      setRows(DEMO_WORK_ORDERS); setIsDemo(true);
    }
  }
  useEffect(() => { load(); }, []);

  async function onSend(id: number) {
    try {
      const r = await sendWorkOrder(id);
      setMsg({ text: `Sent to ${r.recipient || "assignee"}${r.dev_link ? ` · ${r.dev_link}` : ""}`, ok: true });
      load();
    } catch (e: any) { setMsg({ text: e.message, ok: false }); }
  }

  return (
    <>
      <PageHeader
        title="Work Orders"
        subtitle="Plan, assign, and send checklist work orders to the field"
        actions={
          <div className="flex items-center gap-2">
            {isDemo && <DemoBadge />}
            <Button onClick={() => setShowForm((s) => !s)}><Plus className="h-4 w-4" /> New work order</Button>
          </div>
        }
      />

      {msg && (
        <div className={`mb-4 rounded-xl border p-3 text-sm ${msg.ok ? "border-agave/30 bg-agave-light text-agave-deep" : "border-danger/30 bg-[#F7E0E0] text-danger"}`}>
          {msg.text}
        </div>
      )}

      {showForm && (
        <NewWorkOrderForm
          activities={activities}
          assignees={assignees}
          onCancel={() => setShowForm(false)}
          onCreated={(code) => { setShowForm(false); setMsg({ text: `Created ${code}`, ok: true }); load(); }}
          onError={(t) => setMsg({ text: t, ok: false })}
        />
      )}

      {rows === null ? (
        <div className="space-y-3">{[0, 1, 2].map((i) => <div key={i} className="h-20 animate-pulse rounded-xl border border-line bg-white" />)}</div>
      ) : rows.length === 0 ? (
        <EmptyState icon={ClipboardList} title="No work orders yet" description="Create your first work order to assign field activities." />
      ) : (
        <div className="space-y-3">
          {rows.map((w) => (
            <Card key={w.id ?? w.work_order_code}>
              <CardContent className="flex items-center justify-between gap-3 py-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-ink-muted">{w.work_order_code}</span>
                    <StatusBadge status={w.status} />
                  </div>
                  <p className="mt-1 truncate text-sm font-medium text-ink">{w.title}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
                    {w.lot_id && <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />Lot {w.lot_id}</span>}
                    {w.due_date && <span className="inline-flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" />{String(w.due_date).slice(0, 10)}</span>}
                    {w.assigned_to_email && <span className="inline-flex items-center gap-1"><User className="h-3.5 w-3.5" />{w.assigned_to_email}</span>}
                  </div>
                </div>
                {OPEN.includes(w.status) && w.status !== "in_progress" && (
                  <Button variant="secondary" size="sm" disabled={isDemo} onClick={() => onSend(w.id)}>
                    <Send className="h-4 w-4" /> Send
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

function NewWorkOrderForm({ activities, assignees, onCancel, onCreated, onError }: {
  activities: any[]; assignees: any[];
  onCancel: () => void; onCreated: (code: string) => void; onError: (t: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [lot, setLot] = useState("");
  const [due, setDue] = useState("");
  const [activityId, setActivityId] = useState(activities[0]?.id ? String(activities[0].id) : "");
  const [assigneeId, setAssigneeId] = useState("");
  const [surface, setSurface] = useState("");
  const [surfaceUnit, setSurfaceUnit] = useState("ha");
  const [photos, setPhotos] = useState("1");
  const [busy, setBusy] = useState(false);

  const canSubmit = title && activityId && !busy;

  async function submit() {
    setBusy(true);
    try {
      const asg = assignees.find((a) => String(a.id) === assigneeId);
      const payload = {
        title, lot_id: lot ? Number(lot) : null,
        due_date: due ? `${due}T00:00:00` : null,
        assigned_to_id: asg?.id ?? null, assigned_to_email: asg?.email ?? null,
        items: [{
          activity_id: Number(activityId),
          planned_surface_area_value: surface ? Number(surface) : null,
          planned_surface_area_unit: surfaceUnit,
          required_photo_count: Number(photos) || 0,
        }],
      };
      const r = await createWorkOrder(payload);
      onCreated(r.work_order_code);
    } catch (e: any) { onError(e.message); } finally { setBusy(false); }
  }

  const input = "w-full rounded-xl border border-line bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-agave-ring";
  const label = "mb-1 block text-xs font-medium text-ink-soft";

  return (
    <Card className="mb-5">
      <CardContent className="py-5">
        {activities.length === 0 && (
          <p className="mb-4 rounded-xl bg-[#FBEFD9] p-3 text-sm text-warn">
            No activities in the catalog yet — add activities (with carbon factors) before creating work orders.
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2"><label className={label}>Title</label>
            <input className={input} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Compost application — rows 12–18" /></div>
          <div><label className={label}>Lot ID</label><input className={input} value={lot} onChange={(e) => setLot(e.target.value)} type="number" /></div>
          <div><label className={label}>Due date</label><input className={input} value={due} onChange={(e) => setDue(e.target.value)} type="date" /></div>
          <div><label className={label}>Activity</label>
            <select className={input} value={activityId} onChange={(e) => setActivityId(e.target.value)}>
              <option value="">Select…</option>
              {activities.map((a) => <option key={a.id} value={a.id}>{a.activity_name}</option>)}
            </select></div>
          <div><label className={label}>Assign to</label>
            <select className={input} value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}>
              <option value="">(unassigned)</option>
              {assignees.map((a) => <option key={a.id} value={a.id}>{a.full_name} — {a.email}</option>)}
            </select></div>
          <div><label className={label}>Planned surface</label>
            <div className="flex gap-2">
              <input className={input} value={surface} onChange={(e) => setSurface(e.target.value)} type="number" step="any" />
              <select className="rounded-xl border border-line bg-white px-2 text-sm" value={surfaceUnit} onChange={(e) => setSurfaceUnit(e.target.value)}>
                <option value="ha">ha</option><option value="m2">m²</option>
              </select>
            </div></div>
          <div><label className={label}>Required photos</label><input className={input} value={photos} onChange={(e) => setPhotos(e.target.value)} type="number" min="0" /></div>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button disabled={!canSubmit} onClick={submit}>{busy ? "Creating…" : "Create work order"}</Button>
        </div>
      </CardContent>
    </Card>
  );
}
