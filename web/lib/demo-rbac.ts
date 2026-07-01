// Curated, clearly-labelled demo datasets for the five role dashboards.
//
// These power the DEMO experience only (rendered when ctx.user.is_demo). Real
// accounts get genuine API data + honest empty states. Server-side scope
// enforcement is real (and tested); this is presentation data so each profile
// visibly differs without seeding fake rows into the shared database.
import type { OrgRole } from "./rbac";

export interface DemoWO {
  code: string;
  title: string;
  status: string;
  lot: string;
  assignee: string;
  due: string;
  evidence: "complete" | "missing" | "partial";
}

const ALL_WOS: DemoWO[] = [
  { code: "WO-2026-0042", title: "Compost application — rows 12–18", status: "in_progress", lot: "TEQ-01", assignee: "Juan Martinez", due: "2026-07-02", evidence: "partial" },
  { code: "WO-2026-0041", title: "Weed control — perimeter", status: "submitted", lot: "TEQ-03", assignee: "Juan Martinez", due: "2026-07-01", evidence: "complete" },
  { code: "WO-2026-0040", title: "Drip irrigation check", status: "approved", lot: "TEQ-02", assignee: "Juan Martinez", due: "2026-06-28", evidence: "complete" },
  { code: "WO-2026-0039", title: "Pest scouting — agave weevil", status: "needs_correction", lot: "TEQ-05", assignee: "Pedro Sanchez", due: "2026-06-30", evidence: "missing" },
  { code: "WO-2026-0038", title: "Fertilization — north block", status: "sent", lot: "TEQ-01", assignee: "Pedro Sanchez", due: "2026-07-03", evidence: "missing" },
  { code: "WO-2026-0037", title: "Soil sampling — east terrace", status: "approved", lot: "TEQ-07", assignee: "Marta Reyes", due: "2026-06-26", evidence: "complete" },
  { code: "WO-2026-0036", title: "Hijuelo removal — block C", status: "submitted", lot: "TEQ-09", assignee: "Marta Reyes", due: "2026-07-04", evidence: "partial" },
];

const JUAN_WOS = ALL_WOS.filter((w) => w.assignee === "Juan Martinez");
const TEAM_WOS = ALL_WOS.filter((w) =>
  ["Juan Martinez", "Pedro Sanchez"].includes(w.assignee),
);

export interface Card {
  label: string;
  value: string | number;
  accent?: "agave" | "clay" | "info" | "warn";
  sub?: string;
}

export interface RoleDemo {
  cards: Card[];
  workOrders: DemoWO[];
  // role-specific extra panels
  labor?: { activity: string; hours: number; workers: number }[];
  products?: { product: string; used: string; carbon: number }[];
  members?: { name: string; role: string; scope: string; active: boolean }[];
  invites?: { email: string; role: string; status: string; expires: string }[];
  audit?: { actor: string; action: string; entity: string; at: string }[];
  carbon?: { plannedKg: number; actualKg: number; perHa: number; missing: number };
}

export const DEMO_DASHBOARDS: Record<OrgRole, RoleDemo> = {
  worker: {
    cards: [
      { label: "Pending", value: 1, accent: "info", sub: "to start" },
      { label: "In progress", value: 1, accent: "agave" },
      { label: "Submitted", value: 1, accent: "clay", sub: "awaiting review" },
      { label: "Approved", value: 1, accent: "agave" },
      { label: "Needs correction", value: 0, accent: "warn" },
    ],
    workOrders: JUAN_WOS,
  },
  supervisor: {
    cards: [
      { label: "Team pending", value: 2, accent: "info" },
      { label: "Overdue", value: 1, accent: "warn", sub: "past due date" },
      { label: "Ready for review", value: 2, accent: "clay" },
      { label: "Missing evidence", value: 2, accent: "warn" },
    ],
    workOrders: TEAM_WOS,
  },
  engineer: {
    cards: [
      { label: "Work completed", value: 3, accent: "agave", sub: "this week" },
      { label: "Evidence completion", value: "71%", accent: "info" },
      { label: "Carbon estimate", value: "1.84 t", accent: "agave", sub: "CO₂e planned" },
      { label: "Review queue", value: 2, accent: "clay" },
    ],
    workOrders: ALL_WOS,
    labor: [
      { activity: "Fertilization", hours: 42, workers: 3 },
      { activity: "Weed control", hours: 28, workers: 2 },
      { activity: "Irrigation", hours: 16, workers: 1 },
      { activity: "Pest scouting", hours: 12, workers: 2 },
    ],
    products: [
      { product: "Compost (organic)", used: "3.2 t", carbon: 96.0 },
      { product: "Urea 46-0-0", used: "180 kg", carbon: 360.0 },
      { product: "Bordeaux mixture", used: "40 L", carbon: 7.5 },
    ],
    carbon: { plannedKg: 1840, actualKg: 1612.5, perHa: 96.4, missing: 2 },
  },
  admin: {
    cards: [
      { label: "Members", value: 5, accent: "agave" },
      { label: "Active invites", value: 2, accent: "info" },
      { label: "Work orders", value: 7, accent: "agave" },
      { label: "Pending reviews", value: 2, accent: "clay" },
      { label: "Missing evidence", value: 2, accent: "warn" },
      { label: "Carbon (t CO₂e)", value: "1.61", accent: "agave" },
    ],
    workOrders: ALL_WOS,
    members: [
      { name: "Juan Martinez", role: "Worker", scope: "Own work only", active: true },
      { name: "Ana Lopez", role: "Supervisor", scope: "Their team / ranch", active: true },
      { name: "Ing. Camila Torres", role: "Engineer", scope: "Whole organization", active: true },
      { name: "Jose Admin", role: "Admin", scope: "Whole organization", active: true },
      { name: "Compliance Viewer", role: "Auditor", scope: "Whole organization", active: true },
    ],
    invites: [
      { email: "nuevo.peon@demo.mx", role: "Worker", status: "pending", expires: "2026-07-14" },
      { email: "agronomo2@demo.mx", role: "Engineer", status: "pending", expires: "2026-07-10" },
    ],
    audit: [
      { actor: "Jose Admin", action: "role_changed", entity: "member #3", at: "today 09:40" },
      { actor: "Ana Lopez", action: "invite_created", entity: "invitation #7", at: "today 08:15" },
      { actor: "Ing. Camila Torres", action: "approve", entity: "execution #90", at: "yest 17:30" },
    ],
    carbon: { plannedKg: 1840, actualKg: 1612.5, perHa: 96.4, missing: 2 },
  },
  auditor: {
    cards: [
      { label: "Records on file", value: 7, accent: "agave" },
      { label: "Evidence complete", value: "71%", accent: "info" },
      { label: "Audit entries", value: 34, accent: "agave" },
      { label: "Corrections", value: 1, accent: "warn" },
    ],
    workOrders: ALL_WOS,
    audit: [
      { actor: "Jose Admin", action: "approve", entity: "execution #90", at: "2026-06-28 10:15" },
      { actor: "Ing. Camila Torres", action: "request_correction", entity: "execution #92", at: "2026-06-27 18:10" },
      { actor: "system", action: "carbon_snapshot", entity: "work_order #40", at: "2026-06-26 11:00" },
      { actor: "Ana Lopez", action: "send_email", entity: "work_order #38", at: "2026-06-26 09:30" },
    ],
    carbon: { plannedKg: 1840, actualKg: 1612.5, perHa: 96.4, missing: 2 },
  },
};
