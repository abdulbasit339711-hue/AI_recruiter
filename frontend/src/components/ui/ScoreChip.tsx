interface ScoreChipProps {
  score: number | null | undefined;
  size?: "sm" | "md" | "lg";
}

function scoreColor(score: number): string {
  if (score >= 70) return "#34C28A";
  if (score >= 40) return "#F5B544";
  return "#F25C7C";
}

export function ScoreChip({ score, size = "md" }: ScoreChipProps) {
  if (score == null) {
    return (
      <span className="inline-flex items-center rounded-full bg-white/[0.04] px-2.5 py-1 text-xs text-muted-foreground">
        —
      </span>
    );
  }
  const color = scoreColor(score);
  const cls =
    size === "sm"
      ? "px-2 py-0.5 text-[11px]"
      : size === "lg"
      ? "px-4 py-1.5 text-base"
      : "px-3 py-1 text-sm";

  return (
    <span
      className={`inline-flex items-center rounded-full font-mono font-semibold tabular-nums ${cls}`}
      style={{
        background: `${color}26`,
        color,
        border: `1px solid ${color}59`,
      }}
    >
      {Math.round(score)}
    </span>
  );
}
