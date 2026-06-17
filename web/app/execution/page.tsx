import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Tractor } from "lucide-react";

export default function ExecutionPage() {
  return (
    <>
      <PageHeader title="Field Execution" subtitle="Track in-progress and submitted field work" />
      <EmptyState icon={Tractor} title="Field Execution — arriving in Phase 3"
        description="Live view of executions with actuals, GPS, weather, and the clean mobile worker completion page." />
    </>
  );
}
