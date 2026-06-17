import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Images } from "lucide-react";

export default function TimelinePage() {
  return (
    <>
      <PageHeader title="Evidence Timeline" subtitle="Georeferenced photo evidence and field history" />
      <EmptyState icon={Images} title="Evidence Timeline — arriving in Phase 3"
        description="A chronological, photo-first history per field/lot/zone with GPS, weather, and carbon context." />
    </>
  );
}
