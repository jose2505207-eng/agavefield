"use client";

import { useState } from "react";
import { Users, ChevronDown, Check } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { DEMO_PROFILES, ROLE_LABELS } from "@/lib/rbac";
import { cn } from "@/lib/utils";

// Demo-only control: lets a reviewer hop between the five seeded read-only
// profiles to see how the dashboard, navigation, and permissions change by role.
// It re-authenticates as the selected demo account — VISIBILITY changes, write
// ability does not (every demo account is blocked from mutations server-side).
export function DemoProfileSwitcher() {
  const { isDemo, ctx, switchDemoProfile } = useAuth();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  if (!isDemo) return null;

  const currentRole = ctx?.dashboard?.role;

  async function pick(username: string) {
    setBusy(username);
    try {
      await switchDemoProfile(username);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 rounded-xl border border-clay/40 bg-clay-light px-3 py-1.5 text-xs font-medium text-clay"
      >
        <Users className="h-3.5 w-3.5" />
        Demo profile: {currentRole ? ROLE_LABELS[currentRole] : "—"}
        <ChevronDown className="h-3.5 w-3.5" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-40 mt-2 w-72 rounded-2xl border border-line bg-white p-2 shadow-lift">
            <p className="px-3 py-2 text-[11px] uppercase tracking-wide text-ink-muted">
              Switch demo profile (read-only)
            </p>
            {DEMO_PROFILES.map((p) => {
              const active = currentRole === p.role;
              return (
                <button
                  key={p.username}
                  onClick={() => pick(p.username)}
                  disabled={busy !== null}
                  className={cn(
                    "flex w-full items-start gap-2 rounded-xl px-3 py-2 text-left transition-colors hover:bg-sand disabled:opacity-50",
                    active && "bg-agave-light",
                  )}
                >
                  <span className="mt-0.5 h-4 w-4 shrink-0">
                    {active && <Check className="h-4 w-4 text-agave" />}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-ink">
                      {p.name} · {ROLE_LABELS[p.role]}
                    </span>
                    <span className="block text-xs text-ink-muted">{p.blurb}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
