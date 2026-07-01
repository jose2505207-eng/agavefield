"use client";

import { useState } from "react";
import { Mail, Copy, Check, Send, SlidersHorizontal, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createInvitation } from "@/lib/api";
import {
  PERMISSION_KEYS, PERMISSION_LABELS, ROLE_LABELS, SCOPE_LABELS,
  ROLE_PERMISSION_TEMPLATES, ROLE_DEFAULT_SCOPE, permsDivergeFromRole,
  type OrgRole, type DataScope, type PermissionKey, type PermissionSet, type Invitation,
} from "@/lib/rbac";

const ROLES: OrgRole[] = ["worker", "supervisor", "engineer", "admin", "auditor"];
const SCOPES: DataScope[] = ["self", "team", "ranch", "organization"];

// Create an invitation link. Picking a role PRE-FILLS the default permission set
// + data scope (mirrors the backend role template); the admin may then override
// individual permissions and the scope before sending. The raw token comes back
// ONCE; only its hash is stored server-side. Overrides + scope are sent as
// `permissions` / `data_scope` (the request-body field names the backend
// InvitationCreate schema expects). Demo accounts are blocked server-side.
export function InviteMemberPanel({ onCreated }: { onCreated?: (inv: Invitation) => void }) {
  const [role, setRole] = useState<OrgRole>("worker");
  const [email, setEmail] = useState("");
  const [days, setDays] = useState(14);
  const [scope, setScope] = useState<DataScope>(ROLE_DEFAULT_SCOPE.worker);
  const [perms, setPerms] = useState<PermissionSet>(
    { ...ROLE_PERMISSION_TEMPLATES.worker },
  );
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Invitation | null>(null);
  const [copied, setCopied] = useState(false);

  // Selecting a role resets permissions + scope to that role's defaults; the
  // admin opts into overrides deliberately from a known-good baseline.
  function pickRole(next: OrgRole) {
    setRole(next);
    setPerms({ ...ROLE_PERMISSION_TEMPLATES[next] });
    setScope(ROLE_DEFAULT_SCOPE[next]);
  }

  function resetToTemplate() {
    setPerms({ ...ROLE_PERMISSION_TEMPLATES[role] });
    setScope(ROLE_DEFAULT_SCOPE[role]);
  }

  const diverged = permsDivergeFromRole(role, perms);
  const scopeDiverged = scope !== ROLE_DEFAULT_SCOPE[role];

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setCreated(null);
    try {
      const inv = await createInvitation({
        invited_role: role,
        invited_email: email.trim() || undefined,
        expires_in_days: days,
        // Always send the resolved permissions + scope so the invite records the
        // exact effective set (even when equal to the template). Backend derives
        // the member from these on acceptance.
        permissions: perms,
        data_scope: scope,
      });
      setCreated(inv);
      onCreated?.(inv);
    } catch (err: any) {
      setError(err.message || "Could not create invitation");
    } finally {
      setBusy(false);
    }
  }

  const link =
    created?.accept_url ||
    (created?.token
      ? `${typeof window !== "undefined" ? window.location.origin : ""}/invite/${created.token}`
      : "");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Invite a member</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-soft">Role</span>
              <select
                className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm"
                value={role}
                onChange={(e) => pickRole(e.target.value as OrgRole)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                ))}
              </select>
            </label>
            <label className="block sm:col-span-1">
              <span className="mb-1 block text-xs font-medium text-ink-soft">Email (optional)</span>
              <input
                className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@ranch.mx"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-soft">Expires (days)</span>
              <input
                type="number"
                min={1}
                max={365}
                className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm"
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
              />
            </label>
          </div>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-ink-soft">Data scope</span>
            <select
              className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm"
              value={scope}
              onChange={(e) => setScope(e.target.value as DataScope)}
            >
              {SCOPES.map((s) => (
                <option key={s} value={s}>{SCOPE_LABELS[s]}</option>
              ))}
            </select>
            <span className="mt-1 block text-[11px] text-ink-muted">
              Row visibility for this member. Default for {ROLE_LABELS[role]}:{" "}
              <span className="font-medium">{SCOPE_LABELS[ROLE_DEFAULT_SCOPE[role]]}</span>.
            </span>
          </label>

          <div className="rounded-xl border border-line">
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left text-sm font-medium text-ink-soft hover:bg-sand/60"
            >
              <span className="flex items-center gap-2">
                <SlidersHorizontal className="h-4 w-4 text-ink-muted" />
                Customize permissions
                {(diverged || scopeDiverged) && (
                  <span className="rounded-full bg-clay-light px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-clay">
                    Overridden
                  </span>
                )}
              </span>
              <span className="text-xs text-ink-muted">{showAdvanced ? "Hide" : "Show"}</span>
            </button>

            {showAdvanced && (
              <div className="space-y-3 border-t border-line p-3">
                <p className="text-[11px] text-ink-muted">
                  These pre-filled from the <span className="font-medium">{ROLE_LABELS[role]}</span>{" "}
                  role template. Any change below diverges this invite from the role
                  default — the invited member starts with exactly what you set here.
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {PERMISSION_KEYS.map((k: PermissionKey) => {
                    const isOverride = perms[k] !== ROLE_PERMISSION_TEMPLATES[role][k];
                    return (
                      <label
                        key={k}
                        className="flex items-center gap-2 rounded-xl border border-line px-3 py-2 text-sm"
                      >
                        <input
                          type="checkbox"
                          checked={perms[k]}
                          onChange={(e) => setPerms((p) => ({ ...p, [k]: e.target.checked }))}
                          className="h-4 w-4 accent-agave"
                        />
                        <span className="text-ink">{PERMISSION_LABELS[k]}</span>
                        {isOverride && (
                          <span className="ml-auto text-[10px] font-medium uppercase tracking-wide text-clay">
                             diff
                          </span>
                        )}
                      </label>
                    );
                  })}
                </div>
                {(diverged || scopeDiverged) && (
                  <button
                    type="button"
                    onClick={resetToTemplate}
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-soft hover:text-ink"
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Reset to {ROLE_LABELS[role]} default
                  </button>
                )}
              </div>
            )}
          </div>

          {error && (
            <div className="rounded-xl border border-danger/30 bg-[#F7E0E0] p-3 text-sm text-danger">
              {error}
            </div>
          )}

          <Button type="submit" disabled={busy}>
            <Send className="h-4 w-4" /> {busy ? "Creating…" : "Create invite link"}
          </Button>
        </form>

        {created && link && (
          <div className="mt-4 rounded-xl border border-agave/30 bg-agave-light p-3">
            <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-agave-deep">
              <Mail className="h-3.5 w-3.5" /> Invite link (shown once)
            </p>
            <div className="flex items-center gap-2">
              <code className="min-w-0 flex-1 truncate rounded-lg bg-white px-2 py-1.5 text-xs text-ink-soft">
                {link}
              </code>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  navigator.clipboard?.writeText(link);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }}
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
