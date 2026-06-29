"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Leaf, LogOut, User } from "lucide-react";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user, isDemo, logout } = useAuth();
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-agave text-white">
          <Leaf className="h-5 w-5" />
        </span>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-ink">Agave Field</p>
          <p className="text-[11px] text-ink-muted">Field Operations</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {NAV.map((item) => {
          const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                active ? "bg-agave-light text-agave-deep" : "text-ink-soft hover:bg-sand",
              )}
            >
              <item.icon className={cn("h-[18px] w-[18px]", active ? "text-agave" : "text-ink-muted")} />
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
                <p className="truncate text-xs font-medium text-ink">{user.username}</p>
                <p className="truncate text-[11px] text-ink-muted">
                  {isDemo ? "Demo · read-only" : user.role}
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
