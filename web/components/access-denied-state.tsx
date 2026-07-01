import Link from "next/link";
import { ShieldAlert, ArrowRight, type LucideIcon } from "lucide-react";

// Reusable in-page restricted/empty state. Used both for genuine permission
// denials (auditor/worker) and for the friendlier "legacy admin without an org
// membership" case (see Task 6 / docs/RBAC.md), where an action link points the
// user at a next step instead of a dead end.
export function AccessDeniedState({
  title = "Access restricted",
  description = "Your role doesn't have permission to view this area. Contact an organization admin if you need access.",
  icon: Icon = ShieldAlert,
  action,
}: {
  title?: string;
  description?: string;
  icon?: LucideIcon;
  action?: { label: string; href: string };
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-line bg-white/60 px-6 py-16 text-center">
      <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#FBEFD9] text-warn">
        <Icon className="h-6 w-6" />
      </span>
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-ink-muted">{description}</p>
      {action && (
        <Link
          href={action.href}
          className="mt-5 inline-flex items-center gap-1.5 rounded-xl bg-agave px-4 py-2 text-sm font-medium text-white hover:bg-agave-deep"
        >
          {action.label} <ArrowRight className="h-4 w-4" />
        </Link>
      )}
    </div>
  );
}

// Standalone helper for the legacy-admin (no org membership) case, so the
// members/invitations pages render one consistent, friendly explanation.
export function LegacyAdminNotice() {
  return (
    <AccessDeniedState
      title="No organization membership"
      description="You are signed in as a legacy admin without an organization membership, so organization roster and invitations aren't available yet. Ask an existing org admin to add you, or create your own organization to start managing members."
      action={{ label: "Create an organization", href: "/signup" }}
    />
  );
}
