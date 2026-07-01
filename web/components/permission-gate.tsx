"use client";

import { useAuth } from "@/lib/auth";
import type { PermissionKey } from "@/lib/rbac";

// COSMETIC permission gate: hides UI a user lacks permission for. This is NOT a
// security boundary — the FastAPI services + middleware enforce permissions
// server-side regardless of what the UI shows.
export function PermissionGate({
  perm,
  anyOf,
  children,
  fallback = null,
}: {
  perm?: PermissionKey;
  anyOf?: PermissionKey[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const { can } = useAuth();
  const keys = anyOf ?? (perm ? [perm] : []);
  const allowed = keys.length === 0 || keys.some((k) => can(k));
  return <>{allowed ? children : fallback}</>;
}
