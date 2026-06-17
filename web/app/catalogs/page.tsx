import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { BookOpen } from "lucide-react";

export default function CatalogsPage() {
  return (
    <>
      <PageHeader title="Catalogs" subtitle="Products, activities, and assignees with carbon factors" />
      <EmptyState icon={BookOpen} title="Catalogs — arriving in Phase 4"
        description="Editable product/activity catalogs (allowed/restricted/prohibited, dose, carbon factors) and the assignee directory. Wires to /api/products, /api/activities, /api/assignees." />
    </>
  );
}
