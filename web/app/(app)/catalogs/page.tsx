"use client";

import { useEffect, useRef, useState } from "react";
import { BookOpen, Upload, Leaf, Package, Users, Sprout } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { DemoBadge } from "@/components/demo-badge";
import {
  listProducts, listActivities, listAssignees, importCatalogCsv,
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

  return (
    <>
      <PageHeader
        title="Catalogs"
        subtitle="Products, activities, and assignees — with your own carbon factors"
        actions={
          <div className="flex items-center gap-2">
            {isDemo && <DemoBadge />}
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
            onClick={() => setTab(t.key)}
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

      {tab === "products" && <ProductsTable rows={products} />}
      {tab === "activities" && <ActivitiesTable rows={activities} />}
      {tab === "assignees" && <AssigneesTable rows={assignees} />}
    </>
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
