"use client";

import { RoleBasedDashboard } from "@/components/role-dashboards";

// The dashboard is now role-aware: it renders the worker / supervisor / engineer
// / admin / auditor view based on the backend-resolved membership + permissions
// (see /api/org/context). All five share one shell; the cards, tables, and
// panels differ by role. Data visibility is enforced server-side.
export default function DashboardPage() {
  return <RoleBasedDashboard />;
}
