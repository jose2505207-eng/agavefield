"use client";

import { useEffect, useState } from "react";
import {
  Images, Leaf, MapPin, MapPinOff, ClipboardList, Send, CheckCircle2,
  RotateCcw, Sprout, Clock,
} from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { DemoBadge } from "@/components/demo-badge";
import { listTimeline, listPhotos } from "@/lib/api";
import { DEMO_TIMELINE, DEMO_PHOTOS } from "@/lib/demo";
import { kg } from "@/lib/utils";

// Agave takes up to ~7 years from planting to harvest. This page is the
// long-horizon, immutable history: every process applied to the plant and the
// carbon it carried, kept in chronological order and never overwritten.
const EVENT_META: Record<string, { icon: any; variant: any; label: string }> = {
  work_order_created: { icon: ClipboardList, variant: "muted", label: "Created" },
  work_order_sent: { icon: Send, variant: "info", label: "Sent" },
  activity_submitted: { icon: Sprout, variant: "warn", label: "Submitted" },
  activity_approved: { icon: CheckCircle2, variant: "ok", label: "Approved" },
  correction_requested: { icon: RotateCcw, variant: "warn", label: "Correction" },
};

function meta(type: string) {
  return EVENT_META[type] ?? { icon: Clock, variant: "muted", label: type?.replace(/_/g, " ") ?? "Event" };
}

function periodKey(v?: string | null) {
  if (!v) return "Undated";
  const d = new Date(v);
  if (isNaN(+d)) return "Undated";
  return d.toLocaleString(undefined, { month: "long", year: "numeric" });
}

function fmtTime(v?: string | null) {
  if (!v) return "";
  const d = new Date(v);
  if (isNaN(+d)) return String(v).slice(0, 16).replace("T", " ");
  return d.toLocaleString(undefined, { day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function TimelinePage() {
  const [events, setEvents] = useState<any[] | null>(null);
  const [photos, setPhotos] = useState<any[]>([]);
  const [isDemo, setIsDemo] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [ev, ph] = await Promise.all([listTimeline(), listPhotos()]);
        const hasEvents = Array.isArray(ev) && ev.length;
        if (hasEvents) {
          setEvents(ev);
          setPhotos(Array.isArray(ph) ? ph : []);
          setIsDemo(false);
        } else {
          setEvents(DEMO_TIMELINE); setPhotos(DEMO_PHOTOS); setIsDemo(true);
        }
      } catch {
        setEvents(DEMO_TIMELINE); setPhotos(DEMO_PHOTOS); setIsDemo(true);
      }
    })();
  }, []);

  // Group chronologically (newest first) by month/year — the spine of the
  // multi-year record.
  const groups: { period: string; items: any[] }[] = [];
  (events ?? [])
    .slice()
    .sort((a, b) => +new Date(b.event_datetime ?? 0) - +new Date(a.event_datetime ?? 0))
    .forEach((e) => {
      const p = periodKey(e.event_datetime);
      const g = groups.find((x) => x.period === p);
      if (g) g.items.push(e); else groups.push({ period: p, items: [e] });
    });

  const totalCarbon = (events ?? []).reduce((s, e) => s + (e.carbon_kgco2e ?? 0), 0);

  return (
    <>
      <PageHeader
        title="Evidence Timeline"
        subtitle="Long-horizon record of every process applied to the agave and its carbon footprint — agave can take up to 7 years to harvest, so this history is permanent and append-only"
        actions={isDemo ? <DemoBadge /> : undefined}
      />

      {events === null ? (
        <div className="space-y-3">{[0, 1, 2, 3].map((i) => <div key={i} className="h-16 animate-pulse rounded-xl border border-line bg-white" />)}</div>
      ) : events.length === 0 ? (
        <EmptyState icon={Images} title="No history yet"
          description="As work orders are sent, submitted, and reviewed, a permanent chronological record builds here." />
      ) : (
        <>
          {/* Cumulative carbon banner — the running footprint across the record. */}
          <Card className="mb-5">
            <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
              <div className="inline-flex items-center gap-2 text-sm text-ink">
                <Leaf className="h-4 w-4 text-agave" />
                <span className="font-medium">{kg(totalCarbon)} kgCO₂e</span>
                <span className="text-ink-muted">cumulative across {events.length} recorded events</span>
              </div>
              <span className="text-xs text-ink-muted">Records are immutable — corrections add new events, never overwrite.</span>
            </CardContent>
          </Card>

          <div className="space-y-8">
            {groups.map((g) => (
              <section key={g.period}>
                <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">{g.period}</h2>
                <ol className="relative space-y-3 border-l border-line pl-5">
                  {g.items.map((e) => {
                    const m = meta(e.event_type);
                    const Icon = m.icon;
                    return (
                      <li key={e.id} className="relative">
                        <span className="absolute -left-[1.6rem] top-1 flex h-6 w-6 items-center justify-center rounded-full border border-line bg-white">
                          <Icon className="h-3.5 w-3.5 text-agave" />
                        </span>
                        <Card>
                          <CardContent className="flex flex-wrap items-center justify-between gap-2 py-3">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <Badge variant={m.variant}>{m.label}</Badge>
                                <span className="text-xs text-ink-muted">{fmtTime(e.event_datetime)}</span>
                              </div>
                              <p className="mt-1 truncate text-sm text-ink">{e.title}</p>
                            </div>
                            {e.carbon_kgco2e != null && (
                              <span className="inline-flex items-center gap-1 text-xs text-ink-soft">
                                <Leaf className="h-3.5 w-3.5 text-agave" />{kg(e.carbon_kgco2e)} kgCO₂e
                              </span>
                            )}
                          </CardContent>
                        </Card>
                      </li>
                    );
                  })}
                </ol>
              </section>
            ))}
          </div>

          {/* Georeferenced photo evidence gallery. */}
          {photos.length > 0 && (
            <section className="mt-10">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">Photo evidence</h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {photos.map((p) => {
                  const hasGps = p.gps_source && p.gps_source !== "unavailable";
                  return (
                    <div key={p.id} className="group relative overflow-hidden rounded-xl border border-line bg-sand">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={p.thumbnail_url || p.file_url} alt={`Lot ${p.lot_id ?? ""}`} className="aspect-square w-full object-cover" />
                      <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-ink/70 to-transparent p-2 text-[11px] text-white">
                        <span className="font-medium">{p.lot_id ? `Lot ${p.lot_id}` : "—"}</span>
                        <span className="inline-flex items-center gap-1">
                          {hasGps ? <MapPin className="h-3 w-3" /> : <MapPinOff className="h-3 w-3 opacity-70" />}
                          {fmtTime(p.captured_at)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </>
      )}
      {isDemo && <p className="mt-6 text-center text-xs text-ink-muted">Showing demo history — the live timeline builds as field work is recorded.</p>}
    </>
  );
}
