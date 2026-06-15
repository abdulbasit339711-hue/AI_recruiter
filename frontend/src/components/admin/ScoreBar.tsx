import { scoreTier } from "@/lib/score";

const TIER_VAR: Record<string, string> = {
  strong: "var(--strong)",
  promising: "var(--promising)",
  weak: "var(--weak)",
};

export function ScoreBar({ value, max = 100 }: { value?: number | null; max?: number }) {
  const score = Math.max(0, Math.min(max, value ?? 0));
  const percent = max > 0 ? (score / max) * 100 : 0;
  // Tier color tracks the same 80 / 55 thresholds as the rest of the app.
  const color = TIER_VAR[scoreTier((score / max) * 100)];

  return (
    <div className="flex min-w-28 items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-foreground/10">
        <div className="h-full rounded-full" style={{ width: `${percent}%`, background: color }} />
      </div>
      <span className="w-10 text-right font-mono text-sm font-semibold tabular-nums text-heading">{score.toFixed(1)}</span>
    </div>
  );
}
