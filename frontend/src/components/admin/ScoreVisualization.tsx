// src/components/admin/ScoreVisualization.tsx
"use client";

import React from "react";
import { motion } from "framer-motion";
import { Briefcase, Users, Clock, CheckCircle2, XCircle } from "lucide-react";
import { useMetrics } from "@/hooks/useMetrics";
import { GlassCard } from "@/components/ui/GlassCard";
import { CountUp, RadialGauge, Donut, BarChart } from "@/components/ui/charts";

const EASE = [0.22, 1, 0.36, 1] as const;
const container = { hidden: {}, visible: { transition: { staggerChildren: 0.07 } } };
const item = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
};

function StatCard({
  label, value, icon: Icon, accent, decimals = 0,
}: {
  label: string; value: number; icon: React.ElementType; accent: string; decimals?: number;
}) {
  return (
    <motion.div variants={item}>
      <GlassCard variant="tile" hover className="relative overflow-hidden p-4">
        {/* tinted accent wash */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-6 -top-8 h-20 w-20 rounded-full blur-2xl"
          style={{ background: `color-mix(in srgb, ${accent} 30%, transparent)` }}
        />
        <div className="relative flex items-center justify-between">
          <span
            className="flex h-9 w-9 items-center justify-center rounded-xl"
            style={{ background: `color-mix(in srgb, ${accent} 15%, transparent)`, color: accent }}
          >
            <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
          </span>
        </div>
        <p className="relative mt-3 font-mono text-[26px] font-semibold leading-none text-heading">
          <CountUp value={value} decimals={decimals} />
        </p>
        <p className="relative mt-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      </GlassCard>
    </motion.div>
  );
}

function StatSkeleton() {
  return (
    <div className="glass-tile h-[112px] animate-pulse rounded-2xl bg-foreground/[0.04]" />
  );
}

export const ScoreVisualization: React.FC = () => {
  const { data: m, isLoading } = useMetrics();

  if (isLoading || !m) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => <StatSkeleton key={i} />)}
        </div>
        <div className="grid gap-3.5 lg:grid-cols-[1.2fr_1fr]">
          <div className="glass h-64 animate-pulse rounded-2xl bg-foreground/[0.03]" />
          <div className="glass h-64 animate-pulse rounded-2xl bg-foreground/[0.03]" />
        </div>
      </div>
    );
  }

  const stats = [
    { label: "Jobs", value: m.totalJobs, icon: Briefcase, accent: "var(--primary)" },
    { label: "Candidates", value: m.totalCandidates, icon: Users, accent: "var(--primary)" },
    { label: "Pending", value: m.pendingCount, icon: Clock, accent: "var(--promising)" },
    { label: "Processed", value: m.processedCount, icon: CheckCircle2, accent: "var(--strong)" },
    { label: "Failed", value: m.failedCount, icon: XCircle, accent: "var(--weak)" },
  ];

  const pipeline = [
    { label: "Processed", value: m.processedCount, color: "var(--strong)" },
    { label: "Pending", value: m.pendingCount, color: "var(--promising)" },
    { label: "Failed", value: m.failedCount, color: "var(--weak)" },
  ];
  const totalProcessed = m.processedCount + m.pendingCount + m.failedCount;
  const successRate = totalProcessed ? (m.processedCount / totalProcessed) * 100 : 0;

  return (
    <motion.div className="space-y-5" initial="hidden" animate="visible" variants={container}>
      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 xl:grid-cols-5">
        {stats.map((s) => <StatCard key={s.label} {...s} />)}
      </div>

      {/* Pipeline donut + average-score gauge */}
      <div className="grid gap-3.5 lg:grid-cols-[1.2fr_1fr]">
        <motion.div variants={item}>
          <GlassCard className="p-5">
            <h3 className="text-sm font-semibold text-heading">Pipeline breakdown</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">Across current and legacy statuses.</p>
            <div className="mt-4 flex items-center gap-6">
              <div className="relative shrink-0">
                <Donut data={pipeline} />
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="font-mono text-xl font-semibold text-heading">
                    <CountUp value={m.totalCandidates} />
                  </span>
                  <span className="text-[10px] uppercase tracking-wide text-faint">total</span>
                </div>
              </div>
              <ul className="flex-1 space-y-2.5">
                {pipeline.map((p) => (
                  <li key={p.label} className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2 text-muted-foreground">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: p.color }} />
                      {p.label}
                    </span>
                    <span className="font-mono font-semibold text-heading tabular-nums">{p.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          </GlassCard>
        </motion.div>

        <motion.div variants={item}>
          <GlassCard className="flex flex-col items-center justify-center p-5">
            <h3 className="self-start text-sm font-semibold text-heading">Average score</h3>
            <div className="mt-3 flex flex-1 items-center gap-6">
              <RadialGauge value={Number(m.avgScore.toFixed(1))} max={100} label="avg" sublabel="/ 100" />
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Success rate</p>
                <p className="font-mono text-2xl font-semibold text-heading">
                  <CountUp value={successRate} decimals={1} suffix="%" />
                </p>
                <p className="text-xs text-faint">{m.processedCount} of {totalProcessed} processed</p>
              </div>
            </div>
          </GlassCard>
        </motion.div>
      </div>

      {/* Status distribution bars */}
      <motion.div variants={item}>
        <GlassCard className="p-5">
          <h3 className="text-sm font-semibold text-heading">Status distribution</h3>
          <div className="mt-4">
            <BarChart data={pipeline} />
          </div>
        </GlassCard>
      </motion.div>
    </motion.div>
  );
};
