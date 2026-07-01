"use client";

import { useCallback, useEffect, useState } from "react";
import { Users2 } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { DemoBadge } from "@/components/demo-badge";
import { EmptyState } from "@/components/empty-state";
import { AccessDeniedState, LegacyAdminNotice } from "@/components/access-denied-state";
import { MemberManagementTable } from "@/components/member-management-table";
import { useAuth } from "@/lib/auth";
import { listMembers } from "@/lib/api";
import type { Member, PermissionKey } from "@/lib/rbac";

type FullMember = Member & Record<PermissionKey, boolean>;

export default function MembersPage() {
  const { isDemo, can, loading, ctx } = useAuth();
  const [members, setMembers] = useState<FullMember[] | null>(null);
  const [denied, setDenied] = useState(false);

  const load = useCallback(() => {
    setDenied(false);
    listMembers()
      .then((rows) => setMembers(rows as FullMember[]))
      .catch(() => setDenied(true));
  }, []);

  useEffect(() => {
    if (!loading) load();
  }, [loading, load]);

  const canManage = can("can_manage_members");
  const isLegacyAdmin = Boolean(ctx) && ctx?.has_membership === false;

  return (
    <>
      <PageHeader
        title="Members"
        subtitle="People in your organization, their roles and permissions"
        actions={isDemo ? <DemoBadge /> : undefined}
      />
      {denied ? (
        isLegacyAdmin ? (
          <LegacyAdminNotice />
        ) : (
          <AccessDeniedState description="You need member-management or invite permission to view the roster." />
        )
      ) : !members ? (
        <div className="h-64 animate-pulse rounded-2xl border border-line bg-white" />
      ) : members.length === 0 ? (
        <EmptyState icon={Users2} title="No members yet" description="Invite people to your organization to get started." />
      ) : (
        <>
          {isDemo && (
            <p className="mb-4 text-xs text-ink-muted">
              Demo organization — editing is blocked server-side. Try the editor to see the read-only guard.
            </p>
          )}
          <MemberManagementTable members={members} canManage={canManage} onChanged={load} />
        </>
      )}
    </>
  );
}
