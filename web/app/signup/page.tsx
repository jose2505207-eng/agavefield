"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Leaf, Building2, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { registerOrganization, loginRequest } from "@/lib/api";

const input =
  "w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-agave-ring";

// New-tenant self-signup: creates a BRAND-NEW organization with the signer as its
// first admin. Joining an existing organization is invite-only (see /invite).
export default function SignupPage() {
  const router = useRouter();
  const [orgName, setOrgName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await registerOrganization({
        organization_name: orgName.trim(),
        username: username.trim(),
        password,
        full_name: fullName.trim() || undefined,
        email: email.trim() || undefined,
      });
      // Establish a real session by logging in (the httpOnly cookie is set by the
      // server-side /api/login handler, mirroring the normal login flow). If that
      // fails — e.g. the backend requires email verification first — fall back to
      // the login screen so the user can sign in once ready.
      try {
        await loginRequest(username.trim(), password);
        router.replace("/");
        router.refresh();
      } catch {
        router.replace("/login");
      }
    } catch (err: any) {
      setError(err.message || "Could not create your organization");
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-agave text-white">
            <Leaf className="h-6 w-6" />
          </span>
          <h1 className="text-xl font-semibold text-ink">Create your organization</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Start a new Agave Field workspace. You&apos;ll be its first admin.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-line bg-white p-6 shadow-sm">
          {error && (
            <div className="rounded-xl border border-danger/30 bg-[#F7E0E0] p-3 text-sm text-danger">{error}</div>
          )}
          <div className="rounded-xl border border-agave/30 bg-agave-light p-3 text-xs text-agave-deep">
            This creates a <span className="font-semibold">new organization</span>. To join an
            existing one, ask an admin for an invite link.
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-soft">Organization name</label>
            <input
              className={input}
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder="Hacienda Verde"
              autoFocus
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-soft">Your name (optional)</label>
            <input className={input} value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Your name" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-soft">Email (optional)</label>
            <input
              className={input}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@ranch.mx"
              autoComplete="email"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-soft">Username</label>
            <input
              className={input}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-soft">Password</label>
            <input
              className={input}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </div>
          <Button type="submit" disabled={busy || !orgName || !username || !password} className="w-full justify-center">
            <Building2 className="h-4 w-4" /> {busy ? "Creating…" : "Create organization"}
          </Button>
          <Link
            href="/login"
            className="flex items-center justify-center gap-1.5 text-xs font-medium text-ink-muted hover:text-ink"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Already have an account? Sign in
          </Link>
        </form>
      </div>
    </div>
  );
}
