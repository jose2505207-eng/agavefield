"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Leaf, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { loginRequest } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await loginRequest(username.trim(), password);
      router.replace(next);
      router.refresh();
    } catch (err: any) {
      setError(err.message || "Login failed");
      setBusy(false);
    }
  }

  const input =
    "w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-agave-ring";

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-agave text-white">
            <Leaf className="h-6 w-6" />
          </span>
          <h1 className="text-xl font-semibold text-ink">Agave Field</h1>
          <p className="mt-1 text-sm text-ink-muted">Sign in to the operations console</p>
        </div>

        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-line bg-white p-6 shadow-sm">
          {error && (
            <div className="rounded-xl border border-danger/30 bg-[#F7E0E0] p-3 text-sm text-danger">
              {error}
            </div>
          )}
          <div>
            <label className="mb-1 block text-xs font-medium text-ink-soft">Username</label>
            <input
              className={input}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="block text-xs font-medium text-ink-soft">Password</label>
              <Link href="/reset-password" className="text-xs font-medium text-agave hover:text-agave-deep">
                Forgot password?
              </Link>
            </div>
            <input
              className={input}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <Button type="submit" disabled={busy || !username || !password} className="w-full justify-center">
            <LogIn className="h-4 w-4" /> {busy ? "Signing in…" : "Sign in"}
          </Button>
          <p className="text-center text-xs text-ink-muted">
            New here?{" "}
            <Link href="/signup" className="font-medium text-agave hover:text-agave-deep">
              Create an organization
            </Link>{" "}
            — joining an existing org is invite-only.
          </p>
          <p className="text-center text-xs text-ink-muted">
            Demo access: <span className="font-mono">DEMO</span> / <span className="font-mono">DEMO</span> (read-only).
            After signing in, use the demo profile switcher to explore the worker,
            supervisor, engineer, admin and auditor roles.
          </p>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
