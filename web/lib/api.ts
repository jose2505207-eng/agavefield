import { DEMO_DASHBOARD, DEMO_WORK_ORDERS } from "./demo";
import type {
  DashboardData, DashboardResult, WeatherStatus, WorkOrderStatus,
  WorkOrderSummary, WorkOrdersResult,
} from "./types";

// All calls go through the same-origin Next.js proxy (/proxy/...), which injects
// the RBAC API key server-side. Demo fallback keeps read views meaningful.
async function apiGet(path: string): Promise<any> {
  const res = await fetch(`/proxy${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

async function apiSend(method: string, path: string, body?: unknown): Promise<any> {
  const res = await fetch(`/proxy${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.detail || `${path} → ${res.status}`);
  return json;
}

// ---- Auth ----
export type AuthUser = { username: string; full_name?: string; role: string; is_demo: boolean };

export async function getMe(): Promise<AuthUser> {
  const res = await fetch("/proxy/api/auth/me", { cache: "no-store" });
  if (!res.ok) throw new Error("unauthenticated");
  return res.json();
}

export async function loginRequest(username: string, password: string): Promise<AuthUser> {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.detail || "Login failed");
  return json.user as AuthUser;
}

export async function logoutRequest(): Promise<void> {
  await fetch("/api/logout", { method: "POST" });
}

// ---- Catalog CSV import (multipart; goes through the proxy) ----
export async function importCatalogCsv(
  kind: "products" | "activities",
  file: File,
): Promise<{ imported: number; skipped: number; errors: string[] }> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`/proxy/api/catalog/import?kind=${kind}`, { method: "POST", body: fd });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.detail || `import failed (${res.status})`);
  return json;
}

const OPEN_STATUSES = new Set<WorkOrderStatus>(["draft", "scheduled", "sent", "in_progress"]);

function weatherStatus(rainProb: number | null, rainMm: number | null): WeatherStatus {
  if (rainProb == null && rainMm == null) return "unknown";
  if ((rainMm ?? 0) >= 15) return "storm";
  if ((rainProb ?? 0) >= 50 || (rainMm ?? 0) >= 5) return "rain_likely";
  return "dry";
}

const UNKNOWN_WEATHER: DashboardData["weather"] = {
  tempC: null, rainProbability: null, rainNext24h: null, status: "unknown", updated: "unavailable",
};

// ---- Dashboard ----
// Demo data is shown ONLY for the demo account (isDemo=true). Real accounts get
// live data and genuine empty states (zeros / "no data") — never fake records.
// On a real backend error the promise rejects so the page shows an error state.
export async function getDashboardData(isDemo: boolean): Promise<DashboardResult> {
  if (isDemo) return { data: DEMO_DASHBOARD, isDemo: true };

  const [status, workOrders, carbon, queue] = await Promise.all([
    apiGet("/api/system/status"),
    apiGet("/api/work-orders"),
    apiGet("/api/carbon/summary"),
    apiGet("/api/review-queue"),
  ]);

  let weather = UNKNOWN_WEATHER;
  try {
    const ctx = await apiGet("/api/weather/context?lat=20.8806&lon=-103.8366");
    const cur = ctx?.current || {};
    const f0 = (ctx?.forecast || [])[0] || {};
    weather = {
      tempC: cur.temperature_c ?? null, rainProbability: f0.precip_prob ?? null,
      rainNext24h: f0.precip_mm ?? null,
      status: weatherStatus(f0.precip_prob ?? null, f0.precip_mm ?? null), updated: "live",
    };
  } catch { /* weather is best-effort; leave as unknown */ }

  const wos = Array.isArray(workOrders) ? (workOrders as any[]) : [];
  const data: DashboardData = {
    todayOps: {
      scheduled: wos.filter((w) => ["scheduled", "sent"].includes(w.status)).length,
      inProgress: wos.filter((w) => w.status === "in_progress").length,
      submitted: status?.counts?.pending_review ?? 0,
    },
    completedToday: wos.filter((w) => ["approved", "completed"].includes(w.status)).length,
    reviewCount: Array.isArray(queue) ? queue.length : 0,
    pendingWorkOrders: wos.filter((w) => OPEN_STATUSES.has(w.status)).slice(0, 6).map((w) => ({
      code: w.work_order_code, title: w.title, status: w.status,
      lot: w.lot_id ? `Lot ${w.lot_id}` : undefined, due: w.due_date?.slice(0, 10), assignee: w.assigned_to_email,
    })),
    carbon: {
      plannedKg: carbon?.total_planned_kgco2e ?? 0, actualKg: carbon?.total_actual_kgco2e ?? 0,
      perHa: carbon?.kgco2e_per_hectare ?? null, topActivity: carbon?.top_activities?.[0]?.activity_name,
      missingData: carbon?.records_missing_carbon_data ?? 0,
    },
    weather, recentEvidence: [], lots: [], timeline: [],
  };
  return { data, isDemo: false };
}

// ---- Work Orders ----
// Demo rows only for the demo account; real accounts get live rows (possibly
// empty). Errors reject so the caller can show an error state.
export async function getWorkOrders(isDemo: boolean): Promise<WorkOrdersResult> {
  if (isDemo) return { data: DEMO_WORK_ORDERS as WorkOrderSummary[], isDemo: true };
  const rows = await apiGet("/api/work-orders");
  return { data: (Array.isArray(rows) ? rows : []) as WorkOrderSummary[], isDemo: false };
}

export const listWorkOrders = () => apiGet("/api/work-orders");
export const listProducts = () => apiGet("/api/products?include_inactive=false");
export const listActivities = () => apiGet("/api/activities?include_inactive=false");
export const listAssignees = () => apiGet("/api/assignees?include_inactive=false");
export const createWorkOrder = (body: unknown) => apiSend("POST", "/api/work-orders", body);
export const sendWorkOrder = (id: number) => apiSend("POST", `/api/work-orders/${id}/send`);

// ---- Review ----
export const listReviewQueue = () => apiGet("/api/review-queue");
export const reviewAction = (
  id: number,
  action: "approve" | "reject" | "request-correction",
  body: unknown,
) => apiSend("POST", `/api/review/${id}/${action}`, body);

// ---- Executions / timeline / evidence (Phase 3) ----
export const listExecutions = (status?: string) =>
  apiGet(`/api/executions${status ? `?compliance_status=${status}` : ""}`);
export const listTimeline = () => apiGet("/api/timeline");
export const listPhotos = () => apiGet("/api/photos");

// ---- Public worker completion (token-based; calls the backend DIRECTLY, not
// the proxy — multipart photo uploads can't pass through the text proxy, and
// these endpoints are public so no API key is needed). ----
const DIRECT_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "https://agavefield-nu.vercel.app";

export async function getCompletionData(token: string): Promise<any> {
  const res = await fetch(`${DIRECT_BASE}/api/work-orders/complete/${token}/data`, { cache: "no-store" });
  if (!res.ok) throw new Error(res.status === 404 ? "Invalid or expired link" : `error ${res.status}`);
  return res.json();
}

export async function uploadCompletionPhoto(
  token: string, file: File, workOrderItemId: number,
  gps?: { lat: number; lon: number; acc?: number },
): Promise<any> {
  const fd = new FormData();
  fd.append("token", token);
  fd.append("file", file);
  fd.append("work_order_item_id", String(workOrderItemId));
  if (gps) {
    fd.append("gps_latitude", String(gps.lat));
    fd.append("gps_longitude", String(gps.lon));
    if (gps.acc != null) fd.append("gps_accuracy", String(gps.acc));
    fd.append("captured_at", new Date().toISOString());
  }
  const res = await fetch(`${DIRECT_BASE}/api/photos/upload`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`photo upload failed (${res.status})`);
  return res.json();
}

export async function submitCompletion(token: string, payload: unknown): Promise<any> {
  const res = await fetch(`${DIRECT_BASE}/api/work-orders/complete/${token}/submit`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.detail || `submit failed (${res.status})`);
  return json;
}
