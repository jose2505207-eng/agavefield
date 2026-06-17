import {
  LayoutDashboard,
  ClipboardList,
  Tractor,
  Images,
  Leaf,
  MapPinned,
  BookOpen,
  CheckSquare,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export const NAV: NavItem[] = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Work Orders", href: "/work-orders", icon: ClipboardList },
  { label: "Field Execution", href: "/execution", icon: Tractor },
  { label: "Evidence Timeline", href: "/timeline", icon: Images },
  { label: "Carbon & Traceability", href: "/carbon", icon: Leaf },
  { label: "Fields / Lots", href: "/fields", icon: MapPinned },
  { label: "Catalogs", href: "/catalogs", icon: BookOpen },
  { label: "Review Queue", href: "/review", icon: CheckSquare },
  { label: "Settings", href: "/settings", icon: Settings },
];
