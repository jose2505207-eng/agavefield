"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Leaf, LogOut, User, LayoutDashboard, ClipboardList, Tractor, Images, CalendarCheck,
  BookOpen, CheckSquare, Settings, Users2, Mail, ScrollText, BarChart3, MapPinned,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { ROLE_LABELS } from "@/lib/rbac";

// Icon per nav `key` returned by the backend dashboard config.
const ICONS: Record<string, LucideIcon> = {
  dashboard: LayoutDashboard,
  "my-work": CalendarCheck,
  "work-orders": ClipboardList,
  execution: Tractor,
  review: CheckSquare,
  timeline: Images,
  carbon: Leaf,
  analytics: BarChart3,
  fields: MapPinned,
  catalogs: BookOpen,
  members: Users2,
  invitations: Mail,
  audit: ScrollText,
  settings: Settings,
};

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user, isDemo, ctx, logout } = useAuth();

  // Permission-aware navigation: rendered from the backend-resolved config so
  // items only appear for roles/permissions that allow them. De-dupe by href so
  // overlapping keys (e.g. carbon/analytics) don't render twice.
  const navItems = ctx?.dashboard?.nav ?? [
    { key: "dashboard", label: "Dashboard", href: "/" },
    { key: "settings", label: "Settings", href: "/settings" },
  ];
  // Legacy-admin fallback: an AppUser with no organization membership gets a
  // role-derived context, so org-only nav (members/invitations) would appear but
  // the /api/org/* endpoints answer 403. Hide those entries so we don't lead the
  // user into a dead end (they see a friendly notice if they deep-link anyway).
  const orgOnlyKeys = new Set(["members", "invitations"]);
  const seen = new Set<string>();
  const nav = navItems.filter((n) => {
    if (ctx && ctx.has_membership === false && orgOnlyKeys.has(n.key)) return false;
    if (seen.has(n.href + n.label)) return false;
    seen.add(n.href + n.label);
    return true;
  });

  const roleLabel = ctx?.dashboard?.role ? ROLE_LABELS[ctx.dashboard.role] : user?.role;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-agave text-white">
          <Leaf className="h-5 w-5" />
        </span>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-ink">Agave Field</p>
          <p className="text-[11px] text-ink-muted">
            {ctx?.organization?.name ?? "Field Operations"}
          </p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3">
        {nav.map((item) => {
          const Icon = ICONS[item.key] ?? LayoutDashboard;
          const active =
            pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.key + item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                active ? "bg-agave-light text-agave-deep" : "text-ink-soft hover:bg-sand",
              )}
            >
              <Icon className={cn("h-[18px] w-[18px]", active ? "text-agave" : "text-ink-muted")} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-2 border-t border-line px-3 py-3">
        {user ? (
          <div className="flex items-center justify-between gap-2 rounded-xl px-2 py-1.5">
            <div className="flex min-w-0 items-center gap-2">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sand text-ink-soft">
                <User className="h-4 w-4" />
              </span>
              <div className="min-w-0 leading-tight">
                <p className="truncate text-xs font-medium text-ink">
                  {ctx?.user?.full_name || user.username}
                </p>
                <p className="truncate text-[11px] text-ink-muted">
                  {isDemo ? `Demo · ${roleLabel} · read-only` : roleLabel}
                </p>
              </div>
            </div>
            <button
              onClick={logout}
              className="rounded-lg p-1.5 text-ink-muted hover:bg-sand hover:text-ink"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <div className="px-2 py-1.5 text-[11px] text-ink-muted">Tequila · Jalisco</div>
        )}
      </div>
    </div>
  );
}
