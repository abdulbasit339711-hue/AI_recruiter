// src/components/ui/ScoreChip.tsx
import * as React from "react";
import { scoreMeta, scoreTier, type ScoreTier } from "@/lib/score";
import { cn } from "@/lib/utils";

/** Distinct shape per tier (color-blind safe), colors fixed across themes. */
function TierIcon({ tier, size = 13 }: { tier: ScoreTier; size?: number }) {
  if (tier === "strong") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="9" fill="var(--strong)" />
        <path d="M8 12.5l2.5 2.5L16 9" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (tier === "promising") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="9" fill="none" stroke="var(--promising)" strokeWidth="2.6" />
        <path d="M12 3a9 9 0 0 1 0 18z" fill="var(--promising)" />
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="none" stroke="var(--weak)" strokeWidth="2.6" />
      <circle cx="12" cy="12" r="3.4" fill="var(--weak)" />
    </svg>
  );
}

export interface ScoreChipProps {
  score: number | null | undefined;
  /** Hide the icon (rare — keeps it color-blind safe by default). */
  iconless?: boolean;
  size?: "sm" | "md";
  className?: string;
}

/** The Strong / Promising / Weak pill used in tables, cards, and detail. */
export function ScoreChip({ score, iconless = false, size = "md", className }: ScoreChipProps) {
  const meta = scoreMeta(score);
  const tier = scoreTier(score);
  return (
    <span
      className={cn(meta.chipClass, size === "sm" && "text-[11px] px-2.5 py-1", className)}
      title={`${meta.label} (${Math.round(score ?? 0)})`}
    >
      {!iconless && <TierIcon tier={tier} size={size === "sm" ? 11 : 13} />}
      {meta.label}
    </span>
  );
}
