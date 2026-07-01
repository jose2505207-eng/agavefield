"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Leaf, UserPlus, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ROLE_LABELS, type OrgRole } from "@/lib/rbac";
import { validateInvitation, acceptInvitation } from "@/lib/api";

// Public page (no session required): view + accept an organization invitation.
// The token is validated server-side; expired/revoked/over-max-uses tokens are
// rejected. Accepting creates an AppUser + OrganizationMember with the invited
// role/permissions/scope.
export default function InviteAcceptPage() {
  const params = useParams();
  const router = useRouter();
  const token = String(params?.token || "");

  const [info, setInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    validateInvitation(token)
      .then((data) => {
        setInfo(data);
        // Email-bound invite: pre-fill the address the invite was issued to.
        if (data?.invited_email) setEmail(String(data.invited_email));
      })
      .catch(() => setInfo({ valid: false, reason: "error" }))
      .finally(() => setLoading(false));
  }, [token]);

  // The invite is bound to a specific email when the validate response carries
  // `invited_email`. Some deployments additionally require an emailed code; we
  // surface a code field only if the validate response flags it (degrade
  // gracefully to today's behavior when neither field is present).
  const invitedEmail: string | undefined = info?.invited_email || undefined;
  const requiresCode = Boolean(
    info?.requires_verification ?? info?.verification_required ?? info?.requires_code,
  );

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await acceptInvitation({
        token,
        username: username.trim(),
        password,
        full_name: fullName.trim() || undefined,
        // Only include email/code when relevant so plain invites are unaffected.
        email: invitedEmail || email.trim() || undefined,
        verification_code: requiresCode ? code.trim() || undefined : undefined,
      });
      setDone(true);
      setTimeout(() => router.replace("/login"), 1800);
    } catch (err: any) {
      setError(err.message || "Could not accept invitation");
    } finally {
      setBusy(false);
    }
  }

  const input =
    "w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-agave-ring";

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-agave text-white">
            <Leaf className="h-6 w-6" />
          </span>
          <h1 className="text-xl font-semibold text-ink">Agave Field</h1>
          <p className="mt-1 text-sm text-ink-muted">Organization invitation</p>
        </div>

        <div className="rounded-2xl border border-line bg-white p-6 shadow-sm">
          {loading ? (
            <div className="h-32 animate-pulse rounded-xl bg-sand" />
          ) : done ? (
            <div className="flex flex-col items-center py-6 text-center">
              <CheckCircle2 className="mb-2 h-10 w-10 text-agave" />
              <p className="text-sm font-medium text-ink">You&apos;re in!</p>
              <p className="mt-1 text-xs text-ink-muted">Redirecting to sign in…</p>
            </div>
          ) : !info?.valid ? (
            <div className="py-4 text-center">
              <p className="text-sm font-medium text-ink">This invitation can&apos;t be used</p>
              <p className="mt-1 text-xs text-ink-muted">
                Reason: {info?.reason || "invalid"}. Ask an admin for a fresh link.
              </p>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div className="rounded-xl border border-agave/30 bg-agave-light p-3 text-sm text-agave-deep">
                Join <span className="font-semibold">{info.organization_name}</span> as{" "}
                <span className="font-semibold">{ROLE_LABELS[info.invited_role as OrgRole] || info.invited_role}</span>
              </div>
              {error && (
                <div className="rounded-xl border border-danger/30 bg-[#F7E0E0] p-3 text-sm text-danger">{error}</div>
              )}
              {invitedEmail ? (
                <div>
                  <label className="mb-1 block text-xs font-medium text-ink-soft">Invited email</label>
                  <input className={`${input} bg-sand/50 text-ink-muted`} value={invitedEmail} readOnly />
                  <p className="mt-1 text-[11px] text-ink-muted">
                    This invite is bound to this address.
                  </p>
                </div>
              ) : (
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
              )}
              {requiresCode && (
                <div>
                  <label className="mb-1 block text-xs font-medium text-ink-soft">Verification code</label>
                  <input
                    className={input}
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="Code sent to your email"
                    inputMode="numeric"
                    required
                  />
                </div>
              )}
              <div>
                <label className="mb-1 block text-xs font-medium text-ink-soft">Full name</label>
                <input className={input} value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Your name" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-ink-soft">Username</label>
                <input className={input} value={username} onChange={(e) => setUsername(e.target.value)} required autoComplete="username" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-ink-soft">Password</label>
                <input className={input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
              </div>
              <Button type="submit" disabled={busy || !username || !password || (requiresCode && !code)} className="w-full justify-center">
                <UserPlus className="h-4 w-4" /> {busy ? "Joining…" : "Accept invitation"}
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
