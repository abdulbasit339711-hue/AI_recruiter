// src/components/ui/ScoreRing.tsx
"use client";

import * as React from "react";
import { scoreTier } from "@/lib/score";
import { cn } from "@/lib/utils";

export interface ScoreRingProps {
  /** 0–100 */
  value: number | null | undefined;
  size?: number;
  stroke?: number;
  label?: string;
  /** Override the auto tier color (e.g. always cobalt for aptitude). */
  color?: string;
  /** Count the number up + sweep the arc on mount. */
  animate?: boolean;
  className?: string;
}

function tierColor(value: number | null | undefined): string {
  switch (scoreTier(value)) {
    case "strong": return "var(--strong)";
    case "promising": return "var(--promising)";
    default: return "var(--weak)";
  }
}

/** Circular gauge with the score number inside — the design's signature element. */
export function ScoreRing({
  value,
  size = 88,
  stroke = 8,
  label = "match",
  color,
  animate = true,
  className,
}: ScoreRingProps) {
  const target = Math.max(0, Math.min(100, Math.round(value ?? 0)));
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;

  const [shown, setShown] = React.useState(animate ? 0 : target);

  React.useEffect(() => {
    if (!animate) { setShown(target); return; }
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setShown(target); return; }

    let raf = 0;
    const start = performance.now();
    const duration = 900;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setShown(Math.round(target * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, animate]);

  const ringColor = color ?? tierColor(value);
  const offset = circumference * (1 - shown / 100);

  return (
    <div
      className={cn("relative shrink-0", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${label}: ${target} out of 100`}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={ringColor}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className="font-mono font-semibold leading-none text-heading"
          style={{ fontSize: size * 0.28 }}
        >
          {shown}
        </span>
        {label && (
          <span className="text-muted-foreground" style={{ fontSize: Math.max(9, size * 0.12) }}>
            {label}
          </span>
        )}
      </div>
    </div>
  );
}
