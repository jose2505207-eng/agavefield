import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Settings } from "lucide-react";

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" subtitle="Environment status, roles, and configuration" />
      <EmptyState icon={Settings} title="Settings — arriving in Phase 4"
        description="Go-live readiness (DB, storage, email, RBAC), API keys, and team roles. Wires to /api/system/status." />
    </>
  );
}
