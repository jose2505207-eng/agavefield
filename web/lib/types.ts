// Frontend types mirroring the Agave Field API shapes used by the dashboard.

export type WorkOrderStatus =
  | "draft" | "scheduled" | "sent" | "in_progress" | "submitted"
  | "approved" | "rejected" | "needs_correction" | "completed" | "cancelled";

export type Risk = "low" | "medium" | "high";
export type WeatherStatus = "dry" | "rain_likely" | "storm" | "unknown";

export interface WorkOrderLite {
  code: string;
  title: string;
  status: WorkOrderStatus;
  lot?: string;
  due?: string;
  assignee?: string;
}

export interface LotStatus {
  code: string;
  field: string;
  openWorkOrders: number;
  lastActivity?: string;
  risk: Risk;
}

export interface WeatherCard {
  tempC: number | null;
  rainProbability: number | null;
  rainNext24h: number | null;
  status: WeatherStatus;
  updated?: string;
}

export interface CarbonSummary {
  plannedKg: number;
  actualKg: number;
  perHa: number | null;
  topActivity?: string;
  missingData: number;
}

export interface EvidencePhoto {
  id: number;
  url: string;
  lot?: string;
  capturedAt?: string;
  gps: boolean;
}

export interface TimelineItem {
  type: string;
  title: string;
  at: string;
  carbonKg?: number;
}

export interface DashboardData {
  todayOps: { scheduled: number; inProgress: number; submitted: number };
  completedToday: number;
  reviewCount: number;
  pendingWorkOrders: WorkOrderLite[];
  carbon: CarbonSummary;
  weather: WeatherCard;
  recentEvidence: EvidencePhoto[];
  lots: LotStatus[];
  timeline: TimelineItem[];
}

export interface DashboardResult {
  data: DashboardData;
  isDemo: boolean;
}

// Mirrors the backend WorkOrderRead (see app/models/ops_schemas.py). Only the
// fields the listing page needs are typed; the rest are ignored by the thin client.
export interface WorkOrderSummary {
  id: number;
  work_order_code: string;
  title: string;
  status: WorkOrderStatus;
  due_date?: string | null;
  field_id?: number | null;
  lot_id?: number | null;
  assigned_to_email?: string | null;
  created_at?: string | null;
}

export interface WorkOrdersResult {
  data: WorkOrderSummary[];
  isDemo: boolean;
}
