"use client";

import { useEffect, useRef, useState } from "react";
import { Upload, Leaf, Package, Users, Sprout, Plus } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { DemoBadge } from "@/components/demo-badge";
import {
  listProducts, listActivities, listAssignees, importCatalogCsv,
  createProduct, createActivity,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Tab = "products" | "activities" | "assignees";

export default function CatalogsPage() {
  const { isDemo, loading: authLoading } = useAuth();
  const [tab, setTab] = useState<Tab>("products");
  const [products, setProducts] = useState<any[] | null>(null);
  const [activities, setActivities] = useState<any[] | null>(null);
  const [assignees, setAssignees] = useState<any[] | null>(null);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    try {
      const [p, a, s] = await Promise.all([listProducts(), listActivities(), listAssignees()]);
      setProducts(Array.isArray(p) ? p : []);
      setActivities(Array.isArray(a) ? a : []);
      setAssignees(Array.isArray(s) ? s : []);
    } catch {
      setProducts([]); setActivities([]); setAssignees([]);
      setMsg({ text: "Couldn't load catalogs — the API is unreachable.", ok: false });
    }
  }
  useEffect(() => { if (!authLoading) load(); }, [authLoading]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setMsg(null);
    try {
      const kind = tab === "activities" ? "activities" : "products";
      const r = await importCatalogCsv(kind, file);
      const errs = r.errors?.length ? ` · ${r.errors.length} error(s)` : "";
      setMsg({ text: `Imported ${r.imported} ${kind}, skipped ${r.skipped}${errs}`, ok: true });
      load();
    } catch (err: any) {
      setMsg({ text: err.message, ok: false });
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const TABS: { key: Tab; label: string; icon: any }[] = [
    { key: "products", label: "Products", icon: Package },
    { key: "activities", label: "Activities", icon: Sprout },
    { key: "assignees", label: "Assignees", icon: Users },
  ];
  const canImport = tab !== "assignees" && !isDemo;
  const canCreate = tab !== "assignees" && !isDemo;

  async function onCreated(kind: "product" | "activity") {
    setShowForm(false);
    setMsg({ text: `${kind === "product" ? "Product" : "Activity"} added to the catalog`, ok: true });
    await load();
  }

  return (
    <>
      <PageHeader
        title="Catalogs"
        subtitle="Products, activities, and assignees — with your own carbon factors"
        actions={
          <div className="flex items-center gap-2">
            {isDemo && <DemoBadge />}
            {canCreate && (
              <Button variant="secondary" onClick={() => setShowForm((s) => !s)}>
                <Plus className="h-4 w-4" /> Add {tab === "activities" ? "activity" : "product"}
              </Button>
            )}
            {canImport && (
              <>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={onUpload}
                />
                <Button disabled={busy} onClick={() => fileRef.current?.click()}>
                  <Upload className="h-4 w-4" /> {busy ? "Importing…" : `Import ${tab} CSV`}
                </Button>
              </>
            )}
          </div>
        }
      />

      {msg && (
        <div className={`mb-4 rounded-xl border p-3 text-sm ${msg.ok ? "border-agave/30 bg-agave-light text-agave-deep" : "border-danger/30 bg-[#F7E0E0] text-danger"}`}>
          {msg.text}
        </div>
      )}

      <div className="mb-5 flex gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setShowForm(false); }}
            className={`inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.key ? "bg-agave-light text-agave-deep" : "text-ink-soft hover:bg-sand"
            }`}
          >
            <t.icon className="h-4 w-4" /> {t.label}
          </button>
        ))}
      </div>

      {canImport && (
        <p className="mb-4 text-xs text-ink-muted">
          CSV columns follow <span className="font-mono">scripts/catalog_{tab}.template.csv</span>.
          Blank cells are skipped — carbon factors must be your own values; nothing is invented.
        </p>
      )}

      {showForm && tab === "products" && (
        <AddProductForm onCancel={() => setShowForm(false)} onCreated={() => onCreated("product")} onError={(t) => setMsg({ text: t, ok: false })} />
      )}
      {showForm && tab === "activities" && (
        <AddActivityForm onCancel={() => setShowForm(false)} onCreated={() => onCreated("activity")} onError={(t) => setMsg({ text: t, ok: false })} />
      )}

      {tab === "products" && <ProductsTable rows={products} />}
      {tab === "activities" && <ActivitiesTable rows={activities} />}
      {tab === "assignees" && <AssigneesTable rows={assignees} />}
    </>
  );
}

// value = backend CarbonFactorUnit enum, label = human-friendly
const CARBON_UNITS: { value: string; label: string }[] = [
  { value: "kgCO2e_per_ha", label: "kgCO2e / ha" },
  { value: "kgCO2e_per_m2", label: "kgCO2e / m²" },
  { value: "kgCO2e_per_kg_product", label: "kgCO2e / kg" },
  { value: "kgCO2e_per_liter", label: "kgCO2e / liter" },
  { value: "kgCO2e_per_event", label: "kgCO2e / event" },
];
const fieldInput = "w-full rounded-xl border border-line bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-agave-ring";
const fieldLabel = "mb-1 block text-xs font-medium text-ink-soft";

function AddProductForm({ onCancel, onCreated, onError }: {
  onCancel: () => void; onCreated: () => void; onError: (t: string) => void;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState("fertilizer");
  const [ingredient, setIngredient] = useState("");
  const [dose, setDose] = useState("");
  const [doseUnit, setDoseUnit] = useState("kg/ha");
  const [carbonVal, setCarbonVal] = useState("");
  const [carbonUnit, setCarbonUnit] = useState("kgCO2e_per_kg_product");
  const [restricted, setRestricted] = useState(false);
  const [prohibited, setProhibited] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await createProduct({
        product_name: name, product_type: type,
        active_ingredient: ingredient || null,
        default_dose_value: dose ? Number(dose) : null,
        default_dose_unit: dose ? doseUnit : null,
        carbon_factor_value: carbonVal ? Number(carbonVal) : null,
        carbon_factor_unit: carbonVal ? carbonUnit : null,
        restricted, prohibited, allowed: !prohibited,
      });
      onCreated();
    } catch (e: any) { onError(e.message); } finally { setBusy(false); }
  }

  return (
    <Card className="mb-5">
      <CardContent className="py-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2"><label className={fieldLabel}>Product name</label>
            <input className={fieldInput} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Compost blend A" /></div>
          <div><label className={fieldLabel}>Type</label>
            <select className={fieldInput} value={type} onChange={(e) => setType(e.target.value)}>
              {["fertilizer", "amendment", "pesticide", "herbicide", "biological", "other"].map((t) => <option key={t} value={t}>{t}</option>)}
            </select></div>
          <div><label className={fieldLabel}>Active ingredient</label>
            <input className={fieldInput} value={ingredient} onChange={(e) => setIngredient(e.target.value)} placeholder="(optional)" /></div>
          <div><label className={fieldLabel}>Default dose</label>
            <div className="flex gap-2">
              <input className={fieldInput} value={dose} onChange={(e) => setDose(e.target.value)} type="number" step="any" />
              <input className="w-28 rounded-xl border border-line bg-white px-2 text-sm" value={doseUnit} onChange={(e) => setDoseUnit(e.target.value)} />
            </div></div>
          <div><label className={fieldLabel}>Carbon factor</label>
            <div className="flex gap-2">
              <input className={fieldInput} value={carbonVal} onChange={(e) => setCarbonVal(e.target.value)} type="number" step="any" placeholder="your own value" />
              <select className="w-40 rounded-xl border border-line bg-white px-2 text-sm" value={carbonUnit} onChange={(e) => setCarbonUnit(e.target.value)}>
                {CARBON_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div></div>
          <div className="flex items-center gap-4 pt-6">
            <label className="inline-flex items-center gap-2 text-sm text-ink-soft"><input type="checkbox" checked={restricted} onChange={(e) => setRestricted(e.target.checked)} /> Restricted</label>
            <label className="inline-flex items-center gap-2 text-sm text-ink-soft"><input type="checkbox" checked={prohibited} onChange={(e) => setProhibited(e.target.checked)} /> Prohibited</label>
          </div>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button disabled={!name || busy} onClick={submit}>{busy ? "Saving…" : "Save product"}</Button>
        </div>
      </CardContent>
    </Card>
  );
}

function AddActivityForm({ onCancel, onCreated, onError }: {
  onCancel: () => void; onCreated: () => void; onError: (t: string) => void;
}) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("application");
  const [carbonVal, setCarbonVal] = useState("");
  const [carbonUnit, setCarbonUnit] = useState("kgCO2e_per_ha");
  const [requiresProduct, setRequiresProduct] = useState(false);
  const [requiresPhoto, setRequiresPhoto] = useState(true);
  const [photoCount, setPhotoCount] = useState("1");
  const [requiresGeo, setRequiresGeo] = useState(true);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await createActivity({
        activity_name: name, activity_category: category,
        requires_product: requiresProduct,
        requires_photo_evidence: requiresPhoto,
        default_required_photo_count: Number(photoCount) || 0,
        requires_geolocation: requiresGeo,
        carbon_factor_value: carbonVal ? Number(carbonVal) : null,
        carbon_factor_unit: carbonVal ? carbonUnit : null,
      });
      onCreated();
    } catch (e: any) { onError(e.message); } finally { setBusy(false); }
  }

  return (
    <Card className="mb-5">
      <CardContent className="py-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2"><label className={fieldLabel}>Activity name</label>
            <input className={fieldInput} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Compost application" /></div>
          <div><label className={fieldLabel}>Category</label>
            <select className={fieldInput} value={category} onChange={(e) => setCategory(e.target.value)}>
              {["application", "planting", "harvest", "irrigation", "pruning", "monitoring", "soil", "other"].map((c) => <option key={c} value={c}>{c}</option>)}
            </select></div>
          <div><label className={fieldLabel}>Carbon factor</label>
            <div className="flex gap-2">
              <input className={fieldInput} value={carbonVal} onChange={(e) => setCarbonVal(e.target.value)} type="number" step="any" placeholder="your own value" />
              <select className="w-40 rounded-xl border border-line bg-white px-2 text-sm" value={carbonUnit} onChange={(e) => setCarbonUnit(e.target.value)}>
                {CARBON_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div></div>
          <div><label className={fieldLabel}>Required photos</label>
            <input className={fieldInput} value={photoCount} onChange={(e) => setPhotoCount(e.target.value)} type="number" min="0" /></div>
          <div className="flex flex-wrap items-center gap-4 pt-6 sm:col-span-2">
            <label className="inline-flex items-center gap-2 text-sm text-ink-soft"><input type="checkbox" checked={requiresProduct} onChange={(e) => setRequiresProduct(e.target.checked)} /> Requires product</label>
            <label className="inline-flex items-center gap-2 text-sm text-ink-soft"><input type="checkbox" checked={requiresPhoto} onChange={(e) => setRequiresPhoto(e.target.checked)} /> Requires photo</label>
            <label className="inline-flex items-center gap-2 text-sm text-ink-soft"><input type="checkbox" checked={requiresGeo} onChange={(e) => setRequiresGeo(e.target.checked)} /> Requires GPS</label>
          </div>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button disabled={!name || busy} onClick={submit}>{busy ? "Saving…" : "Save activity"}</Button>
        </div>
      </CardContent>
    </Card>
  );
}

function Loading() {
  return <div className="space-y-2">{[0, 1, 2].map((i) => <div key={i} className="h-12 animate-pulse rounded-xl border border-line bg-white" />)}</div>;
}

function carbonLabel(v: any, unit?: string) {
  if (v == null) return <span className="text-ink-muted">no factor</span>;
  return <span className="inline-flex items-center gap-1"><Leaf className="h-3.5 w-3.5 text-agave" />{v} {unit || ""}</span>;
}

function ProductsTable({ rows }: { rows: any[] | null }) {
  if (rows === null) return <Loading />;
  if (rows.length === 0)
    return <EmptyState icon={Package} title="No products yet" description="Import a products CSV to populate the catalog. Until then, this stays empty." />;
  return (
    <Card>
      <CardContent className="divide-y divide-line p-0">
        {rows.map((p) => (
          <div key={p.id} className="flex items-center justify-between gap-3 px-4 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink">{p.product_name}</p>
              <p className="text-xs text-ink-muted">{p.product_type}{p.active_ingredient ? ` · ${p.active_ingredient}` : ""}</p>
            </div>
            <div className="flex items-center gap-3 text-xs text-ink-muted">
              {p.prohibited ? <Badge variant="warn">prohibited</Badge> : p.restricted ? <Badge variant="info">restricted</Badge> : <Badge variant="ok">allowed</Badge>}
              {carbonLabel(p.carbon_factor_value, p.carbon_factor_unit)}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function ActivitiesTable({ rows }: { rows: any[] | null }) {
  if (rows === null) return <Loading />;
  if (rows.length === 0)
    return <EmptyState icon={Sprout} title="No activities yet" description="Import an activities CSV to populate the catalog. Until then, this stays empty." />;
  return (
    <Card>
      <CardContent className="divide-y divide-line p-0">
        {rows.map((a) => (
          <div key={a.id} className="flex items-center justify-between gap-3 px-4 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink">{a.activity_name}</p>
              <p className="text-xs text-ink-muted">{a.requires_photo_evidence ? "photo required" : "no photo"}{a.requires_geolocation ? " · GPS" : ""}</p>
            </div>
            {carbonLabel(a.carbon_factor_value, a.carbon_factor_unit)}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function AssigneesTable({ rows }: { rows: any[] | null }) {
  if (rows === null) return <Loading />;
  if (rows.length === 0)
    return <EmptyState icon={Users} title="No assignees yet" description="Field workers and supervisors you assign work orders to will appear here." />;
  return (
    <Card>
      <CardContent className="divide-y divide-line p-0">
        {rows.map((a) => (
          <div key={a.id} className="flex items-center justify-between gap-3 px-4 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink">{a.full_name}</p>
              <p className="text-xs text-ink-muted">{a.email}{a.phone ? ` · ${a.phone}` : ""}</p>
            </div>
            <Badge variant="info">{a.role}</Badge>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
