"use client";

import { useEffect, useState } from "react";
import {
  Leaf, MapPin, Loader2, Camera, CheckCircle2, AlertTriangle, Sprout,
} from "lucide-react";
import { getCompletionData, uploadCompletionPhoto, submitCompletion } from "@/lib/api";

// Standalone mobile-first worker page. Rendered bare (no admin shell — see the
// chrome-free root layout). The worker only ever sees their assigned work order.

type Gps = { lat: number; lon: number; acc: number; at: string } | null;
type ItemState = { surface: string; surfaceUnit: string; product: string; productUnit: string; note: string; photoIds: number[]; thumbs: string[] };

export default function CompletePage({ params }: { params: { token: string } }) {
  const token = params.token;
  const [wo, setWo] = useState<any>(null);
  const [items, setItems] = useState<any[]>([]);
  const [state, setState] = useState<Record<number, ItemState>>({});
  const [who, setWho] = useState("");
  const [gps, setGps] = useState<Gps>(null);
  const [gpsMsg, setGpsMsg] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await getCompletionData(token);
        setWo(data.work_order);
        setItems(data.items || []);
        const init: Record<number, ItemState> = {};
        (data.items || []).forEach((it: any) => {
          init[it.id] = { surface: "", surfaceUnit: it.planned_surface_unit || "ha", product: "", productUnit: "kg", note: "", photoIds: [], thumbs: [] };
        });
        setState(init);
      } catch (e: any) {
        setError(e.message || "Could not load this work order");
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  function patch(id: number, p: Partial<ItemState>) {
    setState((s) => ({ ...s, [id]: { ...s[id], ...p } }));
  }

  function captureLocation() {
    if (!navigator.geolocation) { setGpsMsg("Geolocation not supported on this device."); return; }
    setGpsMsg("Getting location…");
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setGps({ lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy, at: new Date().toISOString() });
        setGpsMsg("");
      },
      (e) => setGpsMsg(`Could not get location: ${e.message}`),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  async function onPhoto(id: number, file: File | undefined) {
    if (!file) return;
    try {
      const j = await uploadCompletionPhoto(token, file, id, gps ? { lat: gps.lat, lon: gps.lon, acc: gps.acc } : undefined);
      if (j.id) patch(id, { photoIds: [...state[id].photoIds, j.id], thumbs: [...state[id].thumbs, j.thumbnail_url || j.file_url] });
    } catch (e: any) {
      alert(`Photo upload failed: ${e.message}`);
    }
  }

  async function submit() {
    setSubmitting(true);
    try {
      const payload = {
        responsible_person: who || null,
        submitted_by_name: who || null,
        gps_latitude: gps?.lat ?? null, gps_longitude: gps?.lon ?? null,
        gps_accuracy: gps?.acc ?? null, gps_captured_at: gps?.at ?? null,
        execution_completed_at: new Date().toISOString(),
        items: items.map((it) => {
          const s = state[it.id];
          return {
            work_order_item_id: it.id,
            actual_surface_area_value: s.surface ? Number(s.surface) : null,
            actual_surface_area_unit: s.surfaceUnit || null,
            actual_total_product_value: s.product ? Number(s.product) : null,
            actual_total_product_unit: s.productUnit || null,
            manual_note: s.note || null,
            evidence_photo_ids: s.photoIds,
          };
        }),
      };
      const j = await submitCompletion(token, payload);
      const warns = [...new Set((j.executions || []).flatMap((e: any) => e.warnings || []))];
      setDone(warns.length ? `Submitted with notes: ${warns.join(", ")}. A reviewer will follow up.` : "Your work was submitted for review. Thank you.");
    } catch (e: any) {
      alert(`Submit failed: ${e.message}`);
    } finally {
      setSubmitting(false);
    }
  }

  // ---- States ----
  if (loading) {
    return (
      <Screen>
        <div className="flex flex-col items-center gap-3 py-24 text-agave-deep">
          <Loader2 className="h-8 w-8 animate-spin" />
          <p className="text-sm text-ink-muted">Loading your work order…</p>
        </div>
      </Screen>
    );
  }

  if (error) {
    return (
      <Screen>
        <div className="flex flex-col items-center gap-3 px-6 py-24 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#F7E0E0] text-danger"><AlertTriangle className="h-7 w-7" /></span>
          <h1 className="text-lg font-semibold text-ink">Link not valid</h1>
          <p className="max-w-xs text-sm text-ink-muted">{error}. Please contact your agronomist.</p>
        </div>
      </Screen>
    );
  }

  if (done) {
    return (
      <Screen>
        <div className="flex flex-col items-center gap-3 px-6 py-24 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-agave-light text-agave-deep"><CheckCircle2 className="h-7 w-7" /></span>
          <h1 className="text-lg font-semibold text-ink">Submitted</h1>
          <p className="max-w-xs text-sm text-ink-muted">{done}</p>
        </div>
      </Screen>
    );
  }

  const inputCls = "w-full rounded-xl border border-line bg-white px-3 py-2.5 text-base focus:outline-none focus:ring-2 focus:ring-agave-ring";
  const labelCls = "mb-1 mt-3 block text-xs font-semibold text-ink-soft";

  return (
    <Screen>
      <header className="bg-agave px-4 py-5 text-white">
        <h1 className="flex items-center gap-2 text-base font-semibold"><Leaf className="h-5 w-5" /> {wo?.title || "Work Order"}</h1>
        <p className="mt-1 text-xs text-white/85">
          {wo?.code} · Field/Lot/Zone: {[wo?.field_id, wo?.lot_id, wo?.zone_id].filter(Boolean).join(" / ") || "—"}
          {wo?.due_date ? ` · Due ${String(wo.due_date).slice(0, 10)}` : ""}
        </p>
      </header>

      <main className="mx-auto max-w-2xl px-4 pb-28 pt-4">
        {/* Location */}
        <div className="rounded-xl border border-line bg-white p-3">
          <div className="flex items-center justify-between gap-3">
            <span className="inline-flex items-center gap-2 text-sm text-ink">
              <MapPin className={`h-4 w-4 ${gps ? "text-agave" : "text-ink-muted"}`} />
              {gps ? `Location captured (±${Math.round(gps.acc)}m)` : "Location not captured"}
            </span>
            <button type="button" onClick={captureLocation}
              className="rounded-xl border border-agave bg-white px-3 py-1.5 text-sm font-medium text-agave-deep">
              {gps ? "Update" : "Use location"}
            </button>
          </div>
          {gps && <p className="mt-1 text-xs text-ink-muted">{gps.lat.toFixed(5)}, {gps.lon.toFixed(5)}</p>}
          {gpsMsg && <p className="mt-1 text-xs text-warn">{gpsMsg}</p>}
        </div>

        {/* Checklist items */}
        {items.map((it) => {
          const s = state[it.id];
          return (
            <div key={it.id} className="mt-3 rounded-xl border border-line bg-white p-4">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-ink"><Sprout className="h-4 w-4 text-agave" /> {it.activity_name}</h2>
              {it.product_name && <p className="mt-0.5 text-xs text-ink-muted">Product: {it.product_name}</p>}
              {it.instructions && <p className="mt-1 text-xs text-ink-muted">{it.instructions}</p>}
              {it.planned_surface && <p className="mt-1 text-xs text-ink-muted">Planned: {it.planned_surface} {it.planned_surface_unit || ""}</p>}

              <div className="flex gap-2">
                <div className="flex-1">
                  <label className={labelCls}>Actual surface</label>
                  <input className={inputCls} type="number" inputMode="decimal" value={s.surface} onChange={(e) => patch(it.id, { surface: e.target.value })} />
                </div>
                <div className="w-24">
                  <label className={labelCls}>Unit</label>
                  <input className={inputCls} value={s.surfaceUnit} onChange={(e) => patch(it.id, { surfaceUnit: e.target.value })} />
                </div>
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className={labelCls}>Total product</label>
                  <input className={inputCls} type="number" inputMode="decimal" value={s.product} onChange={(e) => patch(it.id, { product: e.target.value })} />
                </div>
                <div className="w-24">
                  <label className={labelCls}>Unit</label>
                  <input className={inputCls} value={s.productUnit} onChange={(e) => patch(it.id, { productUnit: e.target.value })} />
                </div>
              </div>

              <label className={labelCls}>Note {it.requires_manual_note ? "(required)" : ""}</label>
              <textarea className={inputCls} rows={2} value={s.note} onChange={(e) => patch(it.id, { note: e.target.value })} />

              <label className={labelCls}>Photos {it.required_photo_count ? `(need ${it.required_photo_count})` : ""}</label>
              <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-line bg-sand px-3 py-3 text-sm text-ink-soft">
                <Camera className="h-4 w-4" /> Take / choose photo
                <input type="file" accept="image/*" capture="environment" className="hidden"
                  onChange={(e) => { onPhoto(it.id, e.target.files?.[0]); e.currentTarget.value = ""; }} />
              </label>
              {s.thumbs.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {s.thumbs.map((t, i) => (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img key={i} src={t} alt="evidence" className="h-14 w-14 rounded-lg object-cover" />
                  ))}
                </div>
              )}
            </div>
          );
        })}

        <label className={labelCls}>Your name</label>
        <input className={inputCls} placeholder="Who completed this work?" value={who} onChange={(e) => setWho(e.target.value)} />

        <p className="mt-4 text-center text-xs text-ink-muted">Photos are evidence. A reviewer will approve your submission.</p>
      </main>

      {/* Sticky submit */}
      <div className="fixed inset-x-0 bottom-0 border-t border-line bg-white/95 p-3 backdrop-blur">
        <button type="button" disabled={submitting} onClick={submit}
          className="mx-auto flex w-full max-w-2xl items-center justify-center gap-2 rounded-xl bg-agave px-4 py-3.5 text-base font-semibold text-white disabled:opacity-50">
          {submitting ? <><Loader2 className="h-5 w-5 animate-spin" /> Submitting…</> : "Submit for review"}
        </button>
      </div>
    </Screen>
  );
}

function Screen({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-canvas text-ink">{children}</div>;
}
