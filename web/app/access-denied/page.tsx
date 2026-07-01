import Link from "next/link";
import { ShieldAlert, ArrowLeft } from "lucide-react";

export default function AccessDeniedPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-md text-center">
        <span className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#FBEFD9] text-warn">
          <ShieldAlert className="h-7 w-7" />
        </span>
        <h1 className="text-xl font-semibold text-ink">Access restricted</h1>
        <p className="mt-2 text-sm text-ink-muted">
          Your role doesn&apos;t have permission to view that area. If you believe this is a
          mistake, contact an organization admin.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex items-center gap-2 rounded-xl bg-agave px-4 py-2 text-sm font-medium text-white hover:bg-agave-deep"
        >
          <ArrowLeft className="h-4 w-4" /> Back to dashboard
        </Link>
      </div>
    </div>
  );
}
