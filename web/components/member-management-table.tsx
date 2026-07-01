"use client";

import { useState } from "react";
import { Pencil, UserX } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RolePermissionEditor } from "@/components/role-permission-editor";
import { deactivateMember } from "@/lib/api";
import { ROLE_LABELS, SCOPE_LABELS, PERMISSION_KEYS, type Member, type PermissionKey } from "@/lib/rbac";

type FullMember = Member & Record<PermissionKey, boolean>;

export function MemberManagementTable({
  members,
  canManage,
  onChanged,
}: {
  members: FullMember[];
  canManage: boolean;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState<FullMember | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function deactivate(m: FullMember) {
    if (!confirm(`Deactivate ${m.full_name || m.username}?`)) return;
    setBusyId(m.id);
    try {
      await deactivateMember(m.id);
      onChanged();
    } catch (err: any) {
      alert(err.message || "Could not deactivate member");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <CardContent className="overflow-x-auto pt-5">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
              <th className="py-2 pr-3 font-medium">Member</th>
              <th className="py-2 pr-3 font-medium">Role</th>
              <th className="py-2 pr-3 font-medium">Scope</th>
              <th className="py-2 pr-3 font-medium">Permissions</th>
              <th className="py-2 pr-3 font-medium">Status</th>
              {canManage && <th className="py-2 font-medium">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {members.map((m) => {
              const granted = PERMISSION_KEYS.filter((k) => m[k]).length;
              return (
                <tr key={m.id} className="border-b border-line/60 last:border-0">
                  <td className="py-3 pr-3">
                    <div className="font-medium text-ink">{m.full_name || m.username}</div>
                    <div className="text-xs text-ink-muted">{m.username}</div>
                  </td>
                  <td className="py-3 pr-3"><Badge variant="agave">{ROLE_LABELS[m.role]}</Badge></td>
                  <td className="py-3 pr-3 text-ink-soft">{SCOPE_LABELS[m.data_scope]}</td>
                  <td className="py-3 pr-3 text-ink-soft">{granted}/{PERMISSION_KEYS.length}</td>
                  <td className="py-3 pr-3">
                    <Badge variant={m.is_active ? "ok" : "muted"}>{m.is_active ? "Active" : "Inactive"}</Badge>
                  </td>
                  {canManage && (
                    <td className="py-3">
                      <div className="flex items-center gap-1">
                        <Button size="sm" variant="ghost" onClick={() => setEditing(m)}>
                          <Pencil className="h-3.5 w-3.5" /> Edit
                        </Button>
                        {m.is_active && (
                          <Button size="sm" variant="ghost" disabled={busyId === m.id} onClick={() => deactivate(m)}>
                            <UserX className="h-3.5 w-3.5" /> Deactivate
                          </Button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>

      {editing && (
        <RolePermissionEditor
          member={editing}
          onClose={() => setEditing(null)}
          onSaved={onChanged}
        />
      )}
    </Card>
  );
}
