"use client";

import { useCallback, useEffect, useState } from "react";
import { Mail, XCircle } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { DemoBadge } from "@/components/demo-badge";
import { EmptyState } from "@/components/empty-state";
import { AccessDeniedState, LegacyAdminNotice } from "@/components/access-denied-state";
import { InviteMemberPanel } from "@/components/invite-member-panel";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { listInvitations, revokeInvitation } from "@/lib/api";
import { ROLE_LABELS, type Invitation } from "@/lib/rbac";

const STATUS_VARIANT: Record<string, any> = {
  pending: "info",
  accepted: "ok",
  expired: "muted",
  revoked: "danger",
};

export default function InvitationsPage() {
  const { isDemo, can, loading, ctx } = useAuth();
  const [invites, setInvites] = useState<Invitation[] | null>(null);
  const [denied, setDenied] = useState(false);

  const load = useCallback(() => {
    setDenied(false);
    listInvitations()
      .then(setInvites)
      .catch(() => setDenied(true));
  }, []);

  useEffect(() => {
    if (!loading) load();
  }, [loading, load]);

  async function revoke(id: number) {
    try {
      await revokeInvitation(id);
      load();
    } catch (err: any) {
      alert(err.message || "Could not revoke invitation");
    }
  }

  if (!loading && denied) {
    const isLegacyAdmin = Boolean(ctx) && ctx?.has_membership === false;
    return (
      <>
        <PageHeader title="Invitations" />
        {isLegacyAdmin ? (
          <LegacyAdminNotice />
        ) : (
          <AccessDeniedState description="You need invite permission to manage invitations." />
        )}
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Invitations"
        subtitle="Create and manage tokenized invite links"
        actions={isDemo ? <DemoBadge /> : undefined}
      />
      {can("can_invite_members") && (
        <div className="mb-6">
          <InviteMemberPanel onCreated={load} />
        </div>
      )}

      {!invites ? (
        <div className="h-48 animate-pulse rounded-2xl border border-line bg-white" />
      ) : invites.length === 0 ? (
        <EmptyState icon={Mail} title="No invitations yet" description="Created invite links will appear here." />
      ) : (
        <Card>
          <CardContent className="overflow-x-auto pt-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                  <th className="py-2 pr-3 font-medium">Email</th>
                  <th className="py-2 pr-3 font-medium">Role</th>
                  <th className="py-2 pr-3 font-medium">Uses</th>
                  <th className="py-2 pr-3 font-medium">Expires</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {invites.map((inv) => (
                  <tr key={inv.id} className="border-b border-line/60 last:border-0">
                    <td className="py-3 pr-3 text-ink">{inv.invited_email || "— (any)"}</td>
                    <td className="py-3 pr-3"><Badge variant="agave">{ROLE_LABELS[inv.invited_role]}</Badge></td>
                    <td className="py-3 pr-3 text-ink-soft">{inv.used_count}/{inv.max_uses}</td>
                    <td className="py-3 pr-3 text-ink-soft">{inv.expires_at?.slice(0, 10) || "—"}</td>
                    <td className="py-3 pr-3">
                      <Badge variant={STATUS_VARIANT[inv.status] || "muted"}>{inv.status}</Badge>
                    </td>
                    <td className="py-3">
                      {inv.status === "pending" && (
                        <Button size="sm" variant="ghost" onClick={() => revoke(inv.id)}>
                          <XCircle className="h-3.5 w-3.5" /> Revoke
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </>
  );
}
