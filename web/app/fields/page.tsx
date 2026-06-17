import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { MapPinned } from "lucide-react";

export default function FieldsPage() {
  return (
    <>
      <PageHeader title="Fields / Lots" subtitle="Fields, lots, and zones with operational status" />
      <EmptyState icon={MapPinned} title="Fields & Lots — arriving in Phase 4"
        description="Lot status cards, map markers, recent activity, and per-lot timelines." />
    </>
  );
}
