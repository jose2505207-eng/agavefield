"use client";

import { useState } from "react";
import { Leaf, Menu, X } from "lucide-react";
import { SidebarNav } from "@/components/sidebar";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen bg-canvas">
      {/* Desktop fixed sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-line bg-white md:block">
        <SidebarNav />
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-white/90 px-4 py-3 backdrop-blur md:hidden">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-agave text-white">
            <Leaf className="h-4 w-4" />
          </span>
          <span className="text-sm font-semibold text-ink">Agave Field</span>
        </div>
        <button onClick={() => setOpen(true)} className="rounded-lg p-2 text-ink-soft hover:bg-sand" aria-label="Open menu">
          <Menu className="h-5 w-5" />
        </button>
      </header>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85%] bg-white shadow-lift">
            <button onClick={() => setOpen(false)} className="absolute right-3 top-4 rounded-lg p-1.5 text-ink-soft hover:bg-sand" aria-label="Close menu">
              <X className="h-5 w-5" />
            </button>
            <SidebarNav onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      <main className={cn("md:pl-64")}>
        <div className="mx-auto max-w-7xl px-4 py-6 md:px-8 md:py-8">{children}</div>
      </main>
    </div>
  );
}
