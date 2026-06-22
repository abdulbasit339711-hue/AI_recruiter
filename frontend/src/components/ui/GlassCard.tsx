// src/components/ui/GlassCard.tsx
import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "panel" | "tile" | "rail";

const VARIANT: Record<Variant, string> = {
  panel: "glass rounded-2xl",
  tile: "glass-tile rounded-2xl",
  rail: "glass-rail",
};

export interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: Variant;
  /** Adds a subtle lift on hover (skipped under prefers-reduced-motion via CSS). */
  hover?: boolean;
}

/**
 * The single reusable frosted-glass surface. Use `variant="tile"` for small
 * stat tiles (cheaper blur), `variant="rail"` for nav/top bars.
 */
export const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, variant = "panel", hover = false, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(VARIANT[variant], hover && "glass-hover", className)}
      {...props}
    />
  )
);
GlassCard.displayName = "GlassCard";
