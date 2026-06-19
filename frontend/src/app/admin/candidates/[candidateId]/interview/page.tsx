"use client";

import { useParams } from "next/navigation";
import { Brain } from "lucide-react";

import { InterviewPanel } from "@/components/candidates/InterviewPanel";
import { useCandidate } from "@/hooks/useCandidate";
import { useInterviewResult } from "@/hooks/useInterviewResult";
import { GlassCard } from "@/components/ui/GlassCard";
import { CountUp, RadialGauge } from "@/components/ui/charts";
import { FadeIn } from "@/components/ui/motion";

const TIER_MAX = { tier1: 30, tier2: 40, tier3: 30 } as const;

function parseAssessment(raw: string | null | undefined) {
  if (!raw) return null;
  try {
    const p = JSON.parse(raw);
    if (p && typeof p === "object") return p as Record<string, unknown>;
  } catch { /* ignore */ }
  return null;
}

export default function CandidateInterviewPage() {
  const { candidateId } = useParams<{ candidateId: string }>();
  const id = Number(candidateId);
  const { data: candidate, isLoading } = useCandidate(id);
  const { data: interviewResult } = useInterviewResult(id);

  const assessment = parseAssessment(interviewResult?.session?.overall_assessment);
  const fr = (assessment?.final_ai_recommendation ?? {}) as Record<string, unknown>;
  const ov = (assessment?.overall_assessment ?? {}) as Record<string, unknown>;
  const decision = String(fr.decision ?? ov.hiring_recommendation ?? "").replace(/_/g, " ");
  const overallScore = fr.overall_candidate_score != null ? Number(fr.overall_candidate_score)
    : ov.overall_candidate_score != null ? Number(ov.overall_candidate_score) : null;
  const jobMatch = fr.job_match_percentage != null ? Number(fr.job_match_percentage)
    : ov.job_match_percentage != null ? Number(ov.job_match_percentage) : null;
  const rationale = String(fr.decision_rationale ?? "");

  const d = decision.toLowerCase();
  const decisionColor = d === "hire" ? "var(--strong)" : d === "reject" ? "var(--weak)" : d ? "var(--promising)" : null;
  const decisionBg = d === "hire" ? "rgba(52,194,138,0.12)" : d === "reject" ? "rgba(242,92,124,0.12)" : d ? "rgba(245,181,68,0.12)" : null;

  const total = Number(candidate?.hr_score_override ?? candidate?.total_score) || 0;
  const gaugeColor = total >= 70 ? "var(--strong)" : total >= 40 ? "var(--promising)" : "var(--weak)";
  const tiers = [
    { label: "Profile", value: Number(candidate?.tier1) || 0, max: TIER_MAX.tier1, color: "var(--strong)" },
    { label: "Semantic", value: Number(candidate?.tier2) || 0, max: TIER_MAX.tier2, color: "var(--primary)" },
    { label: "LLM eval", value: Number(candidate?.tier3) || 0, max: TIER_MAX.tier3, color: "var(--promising)" },
  ];

  const iq = candidate?.iq_score;
  const hasIq = iq != null && !Number.isNaN(Number(iq));

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      {/* ── Compact page header ── */}
      <FadeIn>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-lg font-semibold text-heading">
              {candidate?.name || candidate?.filename || "Candidate"}
            </h1>
            <p className="text-xs text-muted-foreground">Interview results</p>
          </div>
          {decisionColor && (
            <span
              className="rounded-lg px-4 py-1.5 text-sm font-bold tracking-wide"
              style={{ background: decisionBg ?? undefined, color: decisionColor, border: `1px solid ${decisionColor}40` }}
            >
              {decision.toUpperCase()}
            </span>
          )}
        </div>
      </FadeIn>

      {/* ── Single compact summary card: score + tiers + AI verdict ── */}
      {!isLoading && candidate && (
        <FadeIn delay={0.05}>
          <GlassCard className="p-4">
            <div className="flex flex-wrap items-center gap-5">
              {/* Gauge */}
              <RadialGauge value={Math.round(total)} max={100} size={90} stroke={8} color={gaugeColor} label="score" sublabel="/ 100" />

              {/* Tier bars */}
              <div className="flex-1 min-w-[160px] space-y-2">
                {tiers.map((t) => {
                  const pct = t.max ? (t.value / t.max) * 100 : 0;
                  return (
                    <div key={t.label} className="flex items-center gap-2">
                      <span className="w-16 text-[11px] text-muted-foreground shrink-0">{t.label}</span>
                      <div className="flex-1 h-1.5 rounded-full overflow-hidden bg-foreground/10">
                        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: t.color }} />
                      </div>
                      <span className="w-10 text-right font-mono text-[11px] tabular-nums text-heading">
                        {Math.round(t.value)}/{t.max}
                      </span>
                    </div>
                  );
                })}
                {hasIq && (
                  <div className="flex items-center gap-2 pt-0.5">
                    <Brain className="h-3 w-3 text-primary shrink-0 ml-0.5" />
                    <span className="w-14 text-[11px] text-muted-foreground shrink-0">IQ screen</span>
                    <span className="font-mono text-[11px] font-semibold text-primary tabular-nums">
                      <CountUp value={Number(iq)} suffix="%" />
                    </span>
                  </div>
                )}
              </div>

              {/* AI verdict column */}
              {(overallScore != null || jobMatch != null) && (
                <div className="shrink-0 flex flex-col gap-2 border-l border-border pl-5">
                  {overallScore != null && (
                    <div>
                      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">AI Score</div>
                      <span className="font-mono text-2xl font-bold tabular-nums leading-none" style={{ color: decisionColor ?? "var(--primary)" }}>
                        {overallScore}<span className="text-xs font-normal text-muted-foreground">/100</span>
                      </span>
                    </div>
                  )}
                  {jobMatch != null && (
                    <div>
                      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Job match</div>
                      <span className="font-mono text-2xl font-bold tabular-nums leading-none" style={{ color: decisionColor ?? "var(--primary)" }}>
                        {jobMatch}<span className="text-xs font-normal text-muted-foreground">%</span>
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Rationale — compact, below the row */}
            {rationale && (
              <p className="mt-3 border-t border-border pt-3 text-xs leading-relaxed text-foreground/70">
                {rationale}
              </p>
            )}
          </GlassCard>
        </FadeIn>
      )}

      {/* ── Interview panel ── */}
      <FadeIn delay={0.1}>
        <GlassCard className="p-5">
          <InterviewPanel candidateId={id} />
        </GlassCard>
      </FadeIn>
    </div>
  );
}
