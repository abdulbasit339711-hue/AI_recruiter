"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Circle, Loader2 } from "lucide-react";

import { api } from "@/lib/api";
import type { ScoreExplanation as Explanation } from "@/types";

const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

/** "Why this score": how each tier contributed, what the rules found, and why the status came out. */
export function ScoreExplanation({ candidateId, version }: { candidateId: number; version?: unknown }) {
  const [data, setData] = useState<Explanation | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    setData(null);
    setFailed(false);
    api.getScoreExplanation(candidateId).then((d) => live && setData(d)).catch(() => live && setFailed(true));
    return () => { live = false; };
  }, [candidateId, version]);

  if (failed) return null;
  if (!data) return <div className="glass-tile rounded-xl p-4"><Loader2 className="h-4 w-4 animate-spin" /></div>;

  return (
    <div className="glass-tile space-y-4 rounded-xl p-4">
      <div>
        <h3 className="text-sm font-semibold text-[#1C99BF]">Why this score</h3>
        <p className="mt-1 text-sm text-muted-foreground">{data.outcome}</p>
        {data.override != null && (
          <p className="mt-1 text-xs text-amber-300">
            HR override in effect: {fmt(data.override)} (calculated score was {fmt(data.total)}).
          </p>
        )}
      </div>

      {data.tiers.map((t) => (
        <div key={t.key} className={t.skipped ? "opacity-70" : ""}>
          <div className="flex items-baseline justify-between text-sm">
            <span className="font-medium text-heading">{t.label}</span>
            <span className="font-mono text-xs">
              {fmt(t.score)} / {fmt(t.max)}
              {t.weight !== 1 && <span className="text-muted-foreground"> × {fmt(t.weight)} weight</span>}
            </span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-foreground/10">
            <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, (t.score / (t.max || 1)) * 100)}%` }} />
          </div>
          <p className={`mt-1.5 text-xs ${t.fallback ? "text-amber-300" : "text-muted-foreground"}`}>
            {t.fallback && <AlertTriangle className="mr-1 inline h-3 w-3" />}
            {t.note}
          </p>
          {t.items && (
            <ul className="mt-2 space-y-1">
              {t.items.map((i) => {
                const ok = i.points >= i.max;
                return (
                  <li key={i.label} className="flex items-center gap-2 text-xs text-muted-foreground">
                    {ok ? <CheckCircle2 className="h-3.5 w-3.5 text-[#34C28A]" /> : <Circle className="h-3.5 w-3.5 text-[#F5B544]" />}
                    <span className="flex-1">{i.label}</span>
                    <span className="font-mono">{fmt(i.points)} / {fmt(i.max)}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ))}

      {data.warnings.length > 0 && (
        <ul className="space-y-1 border-t border-white/[0.06] pt-3">
          {data.warnings.map((w, i) => (
            <li key={i} className="text-xs text-amber-300"><AlertTriangle className="mr-1 inline h-3 w-3" />{w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
