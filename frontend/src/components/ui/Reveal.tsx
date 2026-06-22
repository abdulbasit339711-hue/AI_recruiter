// src/components/ui/Reveal.tsx
import * as React from "react";
import { cn } from "@/lib/utils";

export interface RevealProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Stagger index — each step delays the reveal by ~70ms. */
  index?: number;
  as?: "div" | "section" | "li" | "tr";
}

/**
 * Staggered entrance. Pure CSS (`.reveal` keyframe), so it is automatically
 * disabled under `prefers-reduced-motion`. Use `index` to cascade a list.
 */
export function Reveal({ index = 0, className, style, as = "div", ...props }: RevealProps) {
  const Tag = as as React.ElementType;
  return (
    <Tag
      className={cn("reveal", className)}
      style={{ animationDelay: `${Math.min(index, 12) * 70}ms`, ...style }}
      {...props}
    />
  );
}
