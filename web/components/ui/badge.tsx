import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "agave" | "clay" | "ok" | "warn" | "danger" | "info" | "muted";

const VARIANTS: Record<Variant, string> = {
  default: "bg-sand text-ink-soft",
  agave: "bg-agave-light text-agave-deep",
  clay: "bg-clay-light text-clay",
  ok: "bg-agave-light text-agave-deep",
  warn: "bg-[#FBEFD9] text-warn",
  danger: "bg-[#F7E0E0] text-danger",
  info: "bg-[#E1EEF4] text-info",
  muted: "bg-sand text-ink-muted",
};

export function Badge({
  variant = "default",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: Variant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}
