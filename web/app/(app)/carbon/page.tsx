import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Leaf } from "lucide-react";

export default function CarbonPage() {
  return (
    <>
      <PageHeader title="Carbon & Traceability" subtitle="Planned vs actual footprint from locked factor snapshots" />
      <EmptyState icon={Leaf} title="Carbon dashboard — arriving in Phase 4"
        description="Breakdowns by activity, product, lot, and season; per-hectare intensity; missing-data and override reports. Wires to /api/carbon/*." />
    </>
  );
}
