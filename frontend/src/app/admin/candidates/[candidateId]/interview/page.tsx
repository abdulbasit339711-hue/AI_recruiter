"use client";

import { useParams } from "next/navigation";
import { Brain, Trophy } from "lucide-react";

import { InterviewPanel } from "@/components/candidates/InterviewPanel";
import { useCandidate } from "@/hooks/useCandidate";
import { GlassCard } from "@/components/ui/GlassCard";
import { CountUp, RadialGauge, BarChart } from "@/components/ui/charts";
import { FadeIn, Stagger, StaggerItem } from "@/components/ui/motion";

const TIER_MAX = { tier1: 30, tier2: 40, tier3: 30 } as const;

export default function CandidateInterviewPage() {
  const { candidateId } = useParams<{ candidateId: string }>();
  const id = Number(candidateId);
  const { data: candidate, isLoading } = useCandidate(id);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <FadeIn>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-heading">Interview results</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {candidate?.name || candidate?.filename || "Candidate"} · scores &amp; transcript
            </p>
          </div>
        </div>
      </FadeIn>

      {isLoading ? (
        <ScoreSkeleton />
      ) : candidate ? (
        <ScoreOverview candidate={candidate} />
      ) : null}

      <FadeIn delay={0.15}>
        <GlassCard className="p-5 sm:p-6">
          <InterviewPanel candidateId={id} />
        </GlassCard>
      </FadeIn>
    </div>
  );
}

function ScoreOverview({
  candidate,
}: {
  candidate: NonNullable<ReturnType<typeof useCandidate>["data"]>;
}) {
  const total = Number(candidate.hr_score_override ?? candidate.total_score) || 0;
  const tiers = [
    { label: "Profile rules", value: Number(candidate.tier1) || 0, max: TIER_MAX.tier1, color: "var(--strong)" },
    { label: "Semantic", value: Number(candidate.tier2) || 0, max: TIER_MAX.tier2, color: "var(--primary)" },
    { label: "LLM eval", value: Number(candidate.tier3) || 0, max: TIER_MAX.tier3, color: "var(--promising)" },
  ];
  // Normalize to percent-of-max so each bar reads against its own ceiling, but
  // label with the raw "x/max" so the absolute score stays legible. We key the
  // raw label by bar label (unique) to avoid collisions when two tiers share a %.
  // Normalize each bar to percent-of-its-own-max, but nudge by a sub-pixel epsilon
  // per index so every `value` is float-unique. That lets formatValue map a value
  // back to its raw "x/max" label without collisions when two tiers share a percent.
  const barData = tiers.map((t, i) => ({
    label: t.label,
    value: (t.max ? (t.value / t.max) * 100 : 0) + i * 1e-6,
    color: t.color,
  }));
  const rawByValue = new Map(barData.map((b, i) => [b.value, `${Math.round(tiers[i].value)}/${tiers[i].max}`]));
  const iq = candidate.iq_score;
  const hasIq = iq != null && !Number.isNaN(Number(iq));

  const gaugeColor =
    total >= 70 ? "var(--strong)" : total >= 40 ? "var(--promising)" : "var(--weak)";

  return (
    <Stagger className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      {/* Total score gauge */}
      <StaggerItem>
        <GlassCard className="flex h-full flex-col items-center justify-center gap-3 p-5 sm:p-6">
          <div className="flex w-full items-center justify-between">
            <h3 className="flex items-center gap-1.5 text-sm font-semibold text-heading">
              <Trophy className="h-4 w-4 text-promising" /> Total score
            </h3>
            {candidate.hr_score_override != null && (
              <span className="rounded-full bg-promising/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-promising">
                Overridden
              </span>
            )}
          </div>
          <RadialGauge value={Number(total.toFixed(0))} max={100} size={150} color={gaugeColor} label="score" sublabel="/ 100" />
          {hasIq && (
            <div className="mt-1 flex items-center gap-2 rounded-xl bg-foreground/[0.04] px-3 py-2">
              <Brain className="h-4 w-4 text-primary" />
              <span className="text-xs text-muted-foreground">IQ screen</span>
              <span className="font-mono text-base font-semibold tabular-nums text-heading">
                <CountUp value={Number(iq)} suffix="%" />
              </span>
            </div>
          )}
        </GlassCard>
      </StaggerItem>

      {/* Tier breakdown */}
      <StaggerItem>
        <GlassCard className="flex h-full flex-col p-5 sm:p-6">
          <h3 className="text-sm font-semibold text-heading">Scoring breakdown</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">3-tier engine · each bar scaled to its own ceiling.</p>
          <div className="mt-5 flex-1">
            <BarChart
              data={barData}
              formatValue={(v) => rawByValue.get(v) ?? `${Math.round(v)}`}
            />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border pt-3 text-[11px] text-muted-foreground">
            {tiers.map((t) => (
              <span key={t.label} className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ background: t.color }} />
                {t.label}
              </span>
            ))}
          </div>
        </GlassCard>
      </StaggerItem>
    </Stagger>
  );
}

function ScoreSkeleton() {
  return (
    <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <div className="glass h-64 animate-pulse rounded-2xl bg-foreground/[0.03]" />
      <div className="glass h-64 animate-pulse rounded-2xl bg-foreground/[0.03]" />
    </div>
  );
}
