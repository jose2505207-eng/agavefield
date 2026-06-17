import type { DashboardData } from "./types";

// Realistic agave-field demo data (Tequila, Jalisco). Used when the API is
// empty or unreachable so the UI is meaningful during development/preview.
export const DEMO_DASHBOARD: DashboardData = {
  todayOps: { scheduled: 4, inProgress: 2, submitted: 3 },
  completedToday: 5,
  reviewCount: 3,
  pendingWorkOrders: [
    { code: "WO-2026-0042", title: "Compost application — rows 12–18", status: "in_progress", lot: "TEQ-01", due: "2026-06-18", assignee: "Juan Pérez" },
    { code: "WO-2026-0041", title: "Weed control — perimeter", status: "sent", lot: "TEQ-03", due: "2026-06-18", assignee: "María López" },
    { code: "WO-2026-0040", title: "Drip irrigation check", status: "scheduled", lot: "TEQ-02", due: "2026-06-19", assignee: "Carlos Ruiz" },
    { code: "WO-2026-0039", title: "Pest scouting — agave weevil", status: "sent", lot: "TEQ-05", due: "2026-06-20", assignee: "Ana Gómez" },
  ],
  carbon: { plannedKg: 1840, actualKg: 1612.5, perHa: 96.4, topActivity: "Fertilization", missingData: 1 },
  weather: { tempC: 27.3, rainProbability: 65, rainNext24h: 8.0, status: "rain_likely", updated: "today 09:40" },
  recentEvidence: [
    { id: 1, url: "https://picsum.photos/seed/agaveA/400/400", lot: "TEQ-01", capturedAt: "today 08:12", gps: true },
    { id: 2, url: "https://picsum.photos/seed/agaveB/400/400", lot: "TEQ-03", capturedAt: "today 07:55", gps: true },
    { id: 3, url: "https://picsum.photos/seed/agaveC/400/400", lot: "TEQ-02", capturedAt: "yest 17:30", gps: false },
    { id: 4, url: "https://picsum.photos/seed/agaveD/400/400", lot: "TEQ-05", capturedAt: "yest 16:02", gps: true },
  ],
  lots: [
    { code: "TEQ-01", field: "Rancho El Agave", openWorkOrders: 2, lastActivity: "Compost · today", risk: "low" },
    { code: "TEQ-02", field: "Rancho El Agave", openWorkOrders: 1, lastActivity: "Irrigation · 2d", risk: "medium" },
    { code: "TEQ-03", field: "Rancho El Agave", openWorkOrders: 1, lastActivity: "Weed control · today", risk: "low" },
    { code: "TEQ-05", field: "Loma Alta", openWorkOrders: 2, lastActivity: "Pest scouting · 1d", risk: "high" },
  ],
  timeline: [
    { type: "activity_approved", title: "Fertilization approved — TEQ-01", at: "today 10:15", carbonKg: 240 },
    { type: "activity_submitted", title: "Compost submitted — TEQ-01", at: "today 08:20", carbonKg: 96 },
    { type: "work_order_sent", title: "Weed control sent — TEQ-03", at: "today 07:30" },
    { type: "correction_requested", title: "Correction requested — TEQ-05", at: "yest 18:10" },
  ],
};

// API-shaped demo rows for the Work Orders + Review pages (read-only fallback).
export const DEMO_WORK_ORDERS = [
  { id: 1, work_order_code: "WO-2026-0042", title: "Compost application — rows 12–18", status: "in_progress", lot_id: 1, due_date: "2026-06-18", assigned_to_email: "juan@rancho.mx" },
  { id: 2, work_order_code: "WO-2026-0041", title: "Weed control — perimeter", status: "sent", lot_id: 3, due_date: "2026-06-18", assigned_to_email: "maria@rancho.mx" },
  { id: 3, work_order_code: "WO-2026-0040", title: "Drip irrigation check", status: "draft", lot_id: 2, due_date: "2026-06-19", assigned_to_email: "carlos@rancho.mx" },
  { id: 4, work_order_code: "WO-2026-0038", title: "Fertilization — north block", status: "approved", lot_id: 1, due_date: "2026-06-15", assigned_to_email: "ana@rancho.mx" },
];

export const DEMO_REVIEW = [
  { id: 91, work_order_id: 1, compliance_status: "pending_review", manual_note: "Compost spread on rows 12–18, soil moist.", actual_surface_area_value: 2.0, actual_surface_area_unit: "ha", actual_carbon_kgco2e: 96.0, carbon_calculation_status: "calculated", gps_latitude: 20.8806, weather_snapshot_status: "captured" },
  { id: 92, work_order_id: 2, compliance_status: "needs_correction", manual_note: "Weeding done, photo blurry.", actual_surface_area_value: 1.2, actual_surface_area_unit: "ha", actual_carbon_kgco2e: null, carbon_calculation_status: "missing_data", gps_latitude: null, weather_snapshot_status: "unavailable" },
];
