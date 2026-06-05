export function ScoreBar({ value, max = 100 }: { value?: number | null; max?: number }) {
  const score = Math.max(0, Math.min(max, value ?? 0));
  const percent = max > 0 ? (score / max) * 100 : 0;
  const color = score >= 75 ? "bg-emerald-400" : score >= 60 ? "bg-amber-400" : "bg-sky-400";

  return (
    <div className="flex min-w-28 items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${percent}%` }} />
      </div>
      <span className="w-10 text-right text-sm font-semibold tabular-nums">{score.toFixed(1)}</span>
    </div>
  );
}
