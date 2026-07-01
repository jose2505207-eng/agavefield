"use client";

import { useState } from "react";
import { X, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { updateMember } from "@/lib/api";
import {
  PERMISSION_KEYS, PERMISSION_LABELS, ROLE_LABELS, SCOPE_LABELS,
  type Member, type OrgRole, type DataScope, type PermissionKey,
} from "@/lib/rbac";

const ROLES: OrgRole[] = ["worker", "supervisor", "engineer", "admin", "auditor"];
const SCOPES: DataScope[] = ["self", "team", "ranch", "organization"];

// Edit a member's role, per-permission overrides, and data scope. Saves via the
// session-authenticated PATCH; the server recomputes effective permissions from
// role template + overrides, so this editor only sends the deltas the admin set.
export function RolePermissionEditor({
  member,
  onClose,
  onSaved,
}: {
  member: Member & Record<PermissionKey, boolean>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [role, setRole] = useState<OrgRole>(member.role);
  const [scope, setScope] = useState<DataScope>(member.data_scope);
  const [perms, setPerms] = useState<Record<PermissionKey, boolean>>(
    Object.fromEntries(PERMISSION_KEYS.map((k) => [k, Boolean(member[k])])) as Record<PermissionKey, boolean>,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await updateMember(member.id, {
        role,
        data_scope: scope,
        permissions: perms,
      });
      onSaved();
      onClose();
    } catch (err: any) {
      setError(err.message || "Could not save changes");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/40" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg rounded-2xl border border-line bg-white shadow-lift">
        <div className="flex items-center justify-between border-b border-line p-5">
          <div>
            <h3 className="text-sm font-semibold text-ink">
              Edit {member.full_name || member.username}
            </h3>
            <p className="text-xs text-ink-muted">Role, permissions & data scope</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-ink-muted hover:bg-sand">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-[60vh] space-y-4 overflow-y-auto p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-soft">Role</span>
              <select
                className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm"
                value={role}
                onChange={(e) => setRole(e.target.value as OrgRole)}
              >
                {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-soft">Data scope</span>
              <select
                className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm"
                value={scope}
                onChange={(e) => setScope(e.target.value as DataScope)}
              >
                {SCOPES.map((s) => <option key={s} value={s}>{SCOPE_LABELS[s]}</option>)}
              </select>
            </label>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-muted">
              Permissions (override the role default)
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {PERMISSION_KEYS.map((k) => (
                <label key={k} className="flex items-center gap-2 rounded-xl border border-line px-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    checked={perms[k]}
                    onChange={(e) => setPerms((p) => ({ ...p, [k]: e.target.checked }))}
                    className="h-4 w-4 accent-agave"
                  />
                  <span className="text-ink">{PERMISSION_LABELS[k]}</span>
                </label>
              ))}
            </div>
          </div>

          {error && (
            <div className="rounded-xl border border-danger/30 bg-[#F7E0E0] p-3 text-sm text-danger">
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-line p-4">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy}>
            <Save className="h-4 w-4" /> {busy ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}
