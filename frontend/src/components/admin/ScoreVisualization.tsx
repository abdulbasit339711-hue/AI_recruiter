// src/components/admin/ScoreVisualization.tsx
"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  Briefcase, Users, CheckCircle2, Star, TrendingUp,
  ChevronRight,
} from "lucide-react";
import { useMetrics } from "@/hooks/useMetrics";
import { GlassCard } from "@/components/ui/GlassCard";
import { CountUp, RadialGauge, Donut } from "@/components/ui/charts";

const EASE = [0.22, 1, 0.36, 1] as const;
const container = { hidden: {}, visible: { transition: { staggerChildren: 0.07 } } };
const item = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
};

// ─────────────────────────────────────────────────────────────── StatCard ──

function StatCard({
  label,
  value,
  icon: Icon,
  accent,
  decimals = 0,
  suffix = "",
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  accent: string;
  decimals?: number;
  suffix?: string;
}) {
  return (
    <motion.div variants={item}>
      <GlassCard
        variant="tile"
        hover
        className="relative overflow-hidden p-5 flex flex-col gap-3"
        style={{ borderBottom: `3px solid ${accent}` }}
      >
        {/* Accent blob */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-3 -top-6 h-[56px] w-[56px] rounded-full blur-2xl"
          style={{ background: `color-mix(in srgb, ${accent} 30%, transparent)` }}
        />
        {/* Icon */}
        <span
          className="flex h-9 w-9 items-center justify-center rounded-xl shrink-0"
          style={{
            background: `color-mix(in srgb, ${accent} 15%, transparent)`,
            color: accent,
          }}
        >
          <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
        </span>
        {/* Value */}
        <p className="relative font-mono text-3xl font-semibold leading-none text-heading">
          <CountUp value={value} decimals={decimals} suffix={suffix} />
        </p>
        <p className="relative text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
      </GlassCard>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────── Skeletons ──

function StatSkeleton() {
  return (
    <div className="glass-tile h-[140px] animate-pulse rounded-2xl bg-foreground/[0.04]" />
  );
}

function BlockSkeleton({ h = "h-64" }: { h?: string }) {
  return (
    <div className={`glass ${h} animate-pulse rounded-2xl bg-foreground/[0.03]`} />
  );
}

// ─────────────────────────────────────────────── Score distribution bar color ──

function binColor(label: string): string {
  if (label === "0–20" || label === "21–40") return "var(--weak)";
  if (label === "41–60") return "var(--promising)";
  return "var(--strong)";
}

// ──────────────────────────────────────────────────────── Main component ──

export const ScoreVisualization: React.FC = () => {
  const { data: m, isLoading } = useMetrics();

  if (isLoading || !m) {
    return (
      <div className="space-y-6">
        {/* Row 1 skeletons */}
        <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <StatSkeleton key={i} />
          ))}
        </div>
        {/* Row 2 skeletons */}
        <div className="grid gap-3.5 lg:grid-cols-[2fr_1fr]">
          <BlockSkeleton h="h-64" />
          <BlockSkeleton h="h-64" />
        </div>
        {/* Row 3 skeletons */}
        <div className="grid gap-3.5 lg:grid-cols-2">
          <BlockSkeleton h="h-48" />
          <BlockSkeleton h="h-48" />
        </div>
      </div>
    );
  }

  const pipeline = [
    { label: "Processed", value: m.processedCount, color: "var(--strong)" },
    { label: "Pending",   value: m.pendingCount,   color: "var(--promising)" },
    { label: "Failed",    value: m.failedCount,    color: "var(--weak)" },
  ];
  const totalPipeline = m.processedCount + m.pendingCount + m.failedCount;

  // Score distribution → histogram bins (per-bin colour)
  const scoreDist = (m.scoreDistribution ?? []).map((b) => ({
    label: b.label,
    value: b.count,
  }));

  // Build coloured bins for the multi-colour histogram rendering
  const avgScore = Number(m.avgScore.toFixed(1));

  // KPI cards
  const stats: {
    label: string;
    value: number;
    icon: React.ElementType;
    accent: string;
    decimals?: number;
    suffix?: string;
  }[] = [
    { label: "Jobs",        value: m.totalJobs,      icon: Briefcase,    accent: "var(--primary)" },
    { label: "Candidates",  value: m.totalCandidates, icon: Users,        accent: "#8B5CF6" },
    { label: "Processed",   value: m.processedCount, icon: CheckCircle2, accent: "var(--strong)" },
    { label: "Shortlisted", value: m.shortlistedCount ?? 0, icon: Star,  accent: "#F5B544" },
    { label: "Avg Score",   value: avgScore,          icon: TrendingUp,   accent: "var(--primary)", decimals: 1 },
  ];

  return (
    <motion.div className="space-y-5" initial="hidden" animate="visible" variants={container}>
      {/* ── Row 1: KPI cards ── */}
      <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 xl:grid-cols-5">
        {stats.map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>

      {/* ── Row 2: Score histogram (2/3) + Pipeline donut (1/3) ── */}
      <div className="grid gap-3.5 lg:grid-cols-[2fr_1fr]">
        {/* Histogram */}
        <motion.div variants={item}>
          <GlassCard className="p-5">
            <h3 className="text-sm font-semibold text-heading">Score distribution</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              All processed candidates by tier
            </p>
            <div className="mt-5 flex items-end gap-2" style={{ height: 140 }}>
              {scoreDist.map((b, i) => {
                const max = Math.max(...scoreDist.map((x) => x.value), 1);
                const heightPct = (b.value / max) * 100;
                const color = binColor(b.label);
                return (
                  <div key={b.label} className="flex flex-1 flex-col items-center gap-1.5 h-full">
                    <div className="flex w-full flex-1 items-end">
                      <motion.div
                        className="w-full rounded-t-md"
                        style={{
                          background: `linear-gradient(180deg, ${color}, color-mix(in srgb, ${color} 55%, transparent))`,
                        }}
                        initial={{ height: 0 }}
                        animate={{ height: `${heightPct}%` }}
                        transition={{
                          duration: 0.8,
                          ease: EASE,
                          delay: i * 0.06,
                        }}
                      />
                    </div>
                    <span className="font-mono text-[10px] text-faint leading-none">{b.label}</span>
                    <span className="font-mono text-[11px] font-semibold text-heading tabular-nums">
                      {b.value}
                    </span>
                  </div>
                );
              })}
            </div>
          </GlassCard>
        </motion.div>

        {/* Pipeline donut */}
        <motion.div variants={item}>
          <GlassCard className="p-5 flex flex-col">
            <h3 className="text-sm font-semibold text-heading">Pipeline breakdown</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">Processed · Pending · Failed</p>
            <div className="mt-4 flex flex-1 items-center gap-5">
              <div className="relative shrink-0">
                <Donut data={pipeline} size={130} stroke={16} />
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="font-mono text-xl font-semibold text-heading">
                    <CountUp value={m.totalCandidates} />
                  </span>
                  <span className="text-[10px] uppercase tracking-wide text-faint">total</span>
                </div>
              </div>
              <ul className="flex-1 space-y-2.5 min-w-0">
                {pipeline.map((p) => {
                  const pct = totalPipeline ? Math.round((p.value / totalPipeline) * 100) : 0;
                  return (
                    <li key={p.label} className="flex items-center justify-between gap-2 text-sm">
                      <span className="flex items-center gap-2 text-muted-foreground truncate">
                        <span
                          className="h-2.5 w-2.5 rounded-full shrink-0"
                          style={{ background: p.color }}
                        />
                        {p.label}
                      </span>
                      <span className="flex items-center gap-1.5 shrink-0">
                        <span className="font-mono text-xs font-semibold text-heading tabular-nums">
                          {p.value}
                        </span>
                        <span className="text-[10px] text-faint">({pct}%)</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          </GlassCard>
        </motion.div>
      </div>

      {/* ── Row 3: Avg score gauge + Quality funnel ── */}
      <div className="grid gap-3.5 lg:grid-cols-2">
        {/* Radial gauge */}
        <motion.div variants={item}>
          <GlassCard className="p-5 flex items-center gap-6">
            <RadialGauge
              value={avgScore}
              max={100}
              size={160}
              stroke={14}
              label="avg"
              sublabel="/ 100"
            />
            <div className="space-y-2 min-w-0">
              <h3 className="text-sm font-semibold text-heading">Average score</h3>
              <p className="text-xs text-muted-foreground">Across all scored candidates</p>
              <div className="mt-3 space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Processed</span>
                  <span className="font-mono font-semibold text-heading tabular-nums">
                    {m.processedCount}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Total candidates</span>
                  <span className="font-mono font-semibold text-heading tabular-nums">
                    {m.totalCandidates}
                  </span>
                </div>
                {totalPipeline > 0 && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Processing rate</span>
                    <span className="font-mono font-semibold text-strong tabular-nums">
                      <CountUp
                        value={Math.round((m.processedCount / totalPipeline) * 100)}
                        suffix="%"
                      />
                    </span>
                  </div>
                )}
              </div>
            </div>
          </GlassCard>
        </motion.div>

        {/* Quality funnel */}
        <motion.div variants={item}>
          <GlassCard className="p-5">
            <h3 className="text-sm font-semibold text-heading">Recruitment funnel</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Candidates → Processed → Shortlisted
            </p>
            <ul className="mt-4 space-y-4">
              {/* Total */}
              <FunnelRow
                label="Total candidates"
                value={m.totalCandidates}
                max={m.totalCandidates}
                color="var(--primary)"
              />
              {/* Processed */}
              <FunnelRow
                label="Processed"
                value={m.processedCount}
                max={m.totalCandidates}
                color="var(--strong)"
              />
              {/* Shortlisted */}
              <FunnelRow
                label="Shortlisted"
                value={m.shortlistedCount ?? 0}
                max={m.totalCandidates}
                color="#F5B544"
              />
            </ul>
            {/* Top score */}
            <div className="mt-5 flex items-center gap-2 rounded-xl border border-border/60 px-3 py-2.5">
              <Star className="h-4 w-4 text-[#F5B544] shrink-0" strokeWidth={1.75} />
              <span className="text-xs text-muted-foreground">Top score</span>
              <span className="ml-auto font-mono text-lg font-semibold text-heading tabular-nums">
                <CountUp value={m.topScore ?? 0} decimals={1} />
              </span>
              <span className="text-xs text-faint">/ 100</span>
            </div>
          </GlassCard>
        </motion.div>
      </div>
    </motion.div>
  );
};

// ────────────────────────────────────────────────────────── FunnelRow ──

function FunnelRow({
  label,
  value,
  max,
  color,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <li>
      <div className="mb-1 flex items-center justify-between gap-2 text-xs">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <ChevronRight className="h-3 w-3" />
          {label}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="font-mono font-semibold text-heading tabular-nums">{value}</span>
          <span className="text-faint">({pct}%)</span>
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-foreground/[0.07]">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.9, ease: EASE }}
        />
      </div>
    </li>
  );
}
