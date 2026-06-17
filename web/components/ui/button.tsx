import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-agave text-white hover:bg-agave-deep shadow-card",
  secondary: "bg-white text-agave-deep border border-line hover:bg-agave-light",
  ghost: "text-ink-soft hover:bg-sand",
};
const SIZES: Record<Size, string> = { sm: "h-8 px-3 text-sm", md: "h-10 px-4 text-sm" };

export const Button = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }
>(({ className, variant = "primary", size = "md", ...props }, ref) => (
  <button
    ref={ref}
    className={cn(
      "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-agave-ring disabled:opacity-50 disabled:pointer-events-none",
      VARIANTS[variant], SIZES[size], className,
    )}
    {...props}
  />
));
Button.displayName = "Button";
