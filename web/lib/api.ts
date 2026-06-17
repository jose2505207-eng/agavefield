import { DEMO_DASHBOARD } from "./demo";
import type { DashboardData, DashboardResult, WeatherStatus, WorkOrderStatus } from "./types";

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

const OPEN_STATUSES = new Set<WorkOrderStatus>(["draft", "scheduled", "sent", "in_progress"]);

function weatherStatus(rainProb: number | null, rainMm: number | null): WeatherStatus {
  if (rainProb == null && rainMm == null) return "unknown";
  if ((rainMm ?? 0) >= 15) return "storm";
  if ((rainProb ?? 0) >= 50 || (rainMm ?? 0) >= 5) return "rain_likely";
  return "dry";
}

// ---- Dashboard (with demo fallback) ----
export async function getDashboardData(): Promise<DashboardResult> {
  try {
    const [status, workOrders, carbon, queue] = await Promise.all([
      apiGet("/api/system/status"),
      apiGet("/api/work-orders"),
      apiGet("/api/carbon/summary"),
      apiGet("/api/review-queue"),
    ]);
    if (!(status?.counts?.work_orders ?? 0)) return { data: DEMO_DASHBOARD, isDemo: true };

    let weather = DEMO_DASHBOARD.weather;
    try {
      const ctx = await apiGet("/api/weather/context?lat=20.8806&lon=-103.8366");
      const cur = ctx?.current || {};
      const f0 = (ctx?.forecast || [])[0] || {};
      weather = {
        tempC: cur.temperature_c ?? null, rainProbability: f0.precip_prob ?? null,
        rainNext24h: f0.precip_mm ?? null,
        status: weatherStatus(f0.precip_prob ?? null, f0.precip_mm ?? null), updated: "live",
      };
    } catch { /* keep demo weather */ }

    const data: DashboardData = {
      todayOps: {
        scheduled: (workOrders as any[]).filter((w) => ["scheduled", "sent"].includes(w.status)).length,
        inProgress: (workOrders as any[]).filter((w) => w.status === "in_progress").length,
        submitted: status?.counts?.pending_review ?? 0,
      },
      completedToday: (workOrders as any[]).filter((w) => ["approved", "completed"].includes(w.status)).length,
      reviewCount: Array.isArray(queue) ? queue.length : 0,
      pendingWorkOrders: (workOrders as any[]).filter((w) => OPEN_STATUSES.has(w.status)).slice(0, 6).map((w) => ({
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
  } catch {
    return { data: DEMO_DASHBOARD, isDemo: true };
  }
}

// ---- Work Orders ----
export const listWorkOrders = () => apiGet("/api/work-orders");
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
