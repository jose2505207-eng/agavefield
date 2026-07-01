"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Leaf, KeyRound, CheckCircle2, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { requestPasswordReset, confirmPasswordReset } from "@/lib/api";

const input =
  "w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-agave-ring";

// Request view: enter a username to receive a reset link/code. To avoid user
// enumeration we ALWAYS show the same neutral confirmation regardless of whether
// the account exists or the endpoint errors.
function RequestView() {
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    await requestPasswordReset(username.trim());
    setBusy(false);
    setSent(true);
  }

  if (sent) {
    return (
      <div className="flex flex-col items-center py-4 text-center">
        <CheckCircle2 className="mb-2 h-10 w-10 text-agave" />
        <p className="text-sm font-medium text-ink">Check your inbox</p>
        <p className="mt-1 text-xs text-ink-muted">
          If an account matches that username, we&apos;ve sent password-reset instructions.
          Follow the link in the message to choose a new password.
        </p>
        <Link
          href="/login"
          className="mt-5 inline-flex items-center gap-1.5 text-xs font-medium text-agave hover:text-agave-deep"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-ink-muted">
        Enter your username and we&apos;ll send instructions to reset your password.
      </p>
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
      <Button type="submit" disabled={busy || !username} className="w-full justify-center">
        <KeyRound className="h-4 w-4" /> {busy ? "Sending…" : "Send reset link"}
      </Button>
      <Link
        href="/login"
        className="flex items-center justify-center gap-1.5 text-xs font-medium text-ink-muted hover:text-ink"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to sign in
      </Link>
    </form>
  );
}

// Confirm view: reached from the emailed link (?token=...). Sets a new password.
function ConfirmView({ token }: { token: string }) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError("Passwords don't match");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
      setTimeout(() => router.replace("/login"), 1800);
    } catch (err: any) {
      setError(err.message || "This reset link is invalid or has expired.");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="flex flex-col items-center py-4 text-center">
        <CheckCircle2 className="mb-2 h-10 w-10 text-agave" />
        <p className="text-sm font-medium text-ink">Password updated</p>
        <p className="mt-1 text-xs text-ink-muted">Redirecting to sign in…</p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-ink-muted">Choose a new password for your account.</p>
      {error && (
        <div className="rounded-xl border border-danger/30 bg-[#F7E0E0] p-3 text-sm text-danger">{error}</div>
      )}
      <div>
        <label className="mb-1 block text-xs font-medium text-ink-soft">New password</label>
        <input
          className={input}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          autoFocus
          required
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-ink-soft">Confirm new password</label>
        <input
          className={input}
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
          required
        />
      </div>
      <Button type="submit" disabled={busy || !password || !confirm} className="w-full justify-center">
        <KeyRound className="h-4 w-4" /> {busy ? "Updating…" : "Set new password"}
      </Button>
      <Link
        href="/login"
        className="flex items-center justify-center gap-1.5 text-xs font-medium text-ink-muted hover:text-ink"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to sign in
      </Link>
    </form>
  );
}

function ResetPassword() {
  const params = useSearchParams();
  const token = params.get("token") || "";

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-agave text-white">
            <Leaf className="h-6 w-6" />
          </span>
          <h1 className="text-xl font-semibold text-ink">Reset password</h1>
          <p className="mt-1 text-sm text-ink-muted">Agave Field operations console</p>
        </div>
        <div className="rounded-2xl border border-line bg-white p-6 shadow-sm">
          {token ? <ConfirmView token={token} /> : <RequestView />}
        </div>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPassword />
    </Suspense>
  );
}
