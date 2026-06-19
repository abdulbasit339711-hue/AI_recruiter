// src/app/admin/dashboard/page.tsx
"use client";

import React from "react";
import { motion } from "framer-motion";
import { GlassCard } from "@/components/ui/GlassCard";
import { CountUp } from "@/components/ui/charts";
import { useMetrics } from "@/hooks/useMetrics";

const EASE = [0.22, 1, 0.36, 1] as const;

const container = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.07 } },
};

const item = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 70) return "var(--strong)";
  if (score >= 40) return "var(--promising)";
  return "var(--weak)";
}

function binColor(label: string): string {
  if (label === "0-20" || label === "0–20") return "var(--weak)";
  if (label === "21-40" || label === "21–40") return "#F25C7C99";
  if (label === "41-60" || label === "41–60") return "var(--promising)";
  return "var(--strong)";
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-2xl bg-white/[0.04] ${className}`}
    />
  );
}

// ── SVG Donut ────────────────────────────────────────────────────────────────

function DonutChart({
  segments,
}: {
  segments: { value: number; color: string; label: string }[];
}) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const r = 50;
  const cx = 60;
  const cy = 60;
  const circumference = 2 * Math.PI * r;
  const gap = 3;

  let offset = 0;
  const arcs = segments.map((seg) => {
    const pct = total > 0 ? seg.value / total : 0;
    const dash = Math.max(0, circumference * pct - gap);
    const arc = { ...seg, dash, dashOffset: -offset * circumference };
    offset += pct;
    return arc;
  });

  return (
    <svg viewBox="0 0 120 120" width={120} height={120} className="shrink-0">
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke="rgba(255,255,255,0.06)"
        strokeWidth={18}
      />
      {arcs.map((arc, i) => (
        <circle
          key={i}
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={arc.color}
          strokeWidth={18}
          strokeDasharray={`${arc.dash} ${circumference}`}
          strokeDashoffset={arc.dashOffset}
          strokeLinecap="round"
          style={{ transform: "rotate(-90deg)", transformOrigin: "60px 60px" }}
        />
      ))}
    </svg>
  );
}

// ── FunnelBar ────────────────────────────────────────────────────────────────

function FunnelBar({
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
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-4">
      <span className="w-40 shrink-0 text-xs text-muted-foreground">{label}</span>
      <div className="flex-1 h-3 rounded-full overflow-hidden bg-white/[0.06]">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 1, ease: EASE, delay: 0.2 }}
        />
      </div>
      <span className="w-14 text-right font-mono text-xs font-semibold text-heading tabular-nums">
        {value}
      </span>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AdminDashboardPage() {
  const { data: m, isLoading } = useMetrics();

  if (isLoading || !m) {
    return (
      <div className="space-y-6 p-6 max-w-6xl mx-auto">
        {/* Header placeholder */}
        <div className="space-y-1.5">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-4 w-56" />
        </div>
        {/* KPI row */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        {/* Two-col */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
        {/* Funnel */}
        <Skeleton className="h-48" />
      </div>
    );
  }

  const avgScore = Number(m.avgScore.toFixed(1));
  const totalPipeline = m.processedCount + m.pendingCount + m.failedCount;

  const kpiCards = [
    {
      label: "Total Jobs",
      value: m.totalJobs,
      decimals: 0,
      suffix: "",
      borderColor: "var(--primary)",
    },
    {
      label: "Candidates",
      value: m.totalCandidates,
      decimals: 0,
      suffix: "",
      borderColor: "var(--primary)",
    },
    {
      label: "Avg Score",
      value: avgScore,
      decimals: 1,
      suffix: "",
      borderColor: scoreColor(avgScore),
    },
    {
      label: "Shortlisted",
      value: m.shortlistedCount ?? 0,
      decimals: 0,
      suffix: "",
      borderColor: "var(--strong)",
    },
  ];

  const scoreDist = (m.scoreDistribution ?? []).map((b) => ({
    label: b.label,
    count: b.count,
  }));
  const distMax = Math.max(...scoreDist.map((b) => b.count), 1);

  const pipelineSegments = [
    { label: "Processed", value: m.processedCount, color: "var(--primary)" },
    { label: "Pending", value: m.pendingCount, color: "var(--promising)" },
    { label: "Failed", value: m.failedCount, color: "var(--weak)" },
  ];

  return (
    <motion.div
      className="space-y-6 p-6 max-w-6xl mx-auto"
      initial="hidden"
      animate="visible"
      variants={container}
    >
      {/* 1. Header */}
      <motion.div variants={item} className="space-y-1">
        <h1 className="text-2xl font-bold text-heading">Dashboard</h1>
        <p className="text-sm text-muted-foreground">AI recruitment overview</p>
      </motion.div>

      {/* 2. KPI cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {kpiCards.map((card, i) => (
          <motion.div key={card.label} variants={item}>
            <GlassCard
              className="p-5 flex flex-col justify-between gap-3 overflow-hidden"
              style={{ borderBottom: `4px solid ${card.borderColor}` }}
            >
              <p className="text-[11px] uppercase tracking-widest text-muted-foreground">
                {card.label}
              </p>
              <p className="text-3xl font-bold font-mono tabular-nums text-heading leading-none">
                <CountUp
                  value={card.value}
                  decimals={card.decimals}
                  suffix={card.suffix}
                />
              </p>
            </GlassCard>
          </motion.div>
        ))}
      </div>

      {/* 3. Two-column row: histogram + donut */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Score Distribution */}
        <motion.div variants={item}>
          <GlassCard className="p-5 h-full">
            <h3 className="text-sm font-semibold text-heading">Score Distribution</h3>
            <p className="mt-0.5 text-xs text-muted-foreground mb-4">
              Candidates grouped by total score
            </p>
            <div
              className="flex items-end gap-3"
              style={{ height: 120 }}
            >
              {scoreDist.map((b, i) => {
                const heightPct = (b.count / distMax) * 100;
                const color = binColor(b.label);
                return (
                  <div
                    key={b.label}
                    className="flex flex-1 flex-col items-center gap-1 h-full"
                  >
                    {/* count above bar */}
                    <span className="font-mono text-[10px] font-semibold text-heading tabular-nums mb-0.5">
                      {b.count}
                    </span>
                    {/* bar */}
                    <div className="flex w-full flex-1 items-end">
                      <motion.div
                        className="w-full rounded-t-md"
                        style={{
                          background: `linear-gradient(180deg, ${color}, color-mix(in srgb, ${color} 50%, transparent))`,
                        }}
                        initial={{ height: 0 }}
                        animate={{ height: `${heightPct}%` }}
                        transition={{ duration: 0.8, ease: EASE, delay: i * 0.07 }}
                      />
                    </div>
                    {/* label below bar */}
                    <span
                      className="font-mono text-[9px] text-muted-foreground leading-none mt-1"
                      style={{ color: "var(--muted-foreground)" }}
                    >
                      {b.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </GlassCard>
        </motion.div>

        {/* Candidate Status */}
        <motion.div variants={item}>
          <GlassCard className="p-5 h-full">
            <h3 className="text-sm font-semibold text-heading">Candidate Status</h3>
            <p className="mt-0.5 text-xs text-muted-foreground mb-4">
              Processing pipeline breakdown
            </p>
            <div className="flex items-center gap-6">
              <div className="relative shrink-0">
                <DonutChart segments={pipelineSegments} />
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="font-mono text-lg font-bold text-heading leading-none">
                    <CountUp value={m.totalCandidates} />
                  </span>
                  <span className="text-[9px] uppercase tracking-wide text-muted-foreground mt-0.5">
                    total
                  </span>
                </div>
              </div>
              <ul className="flex-1 space-y-3">
                {pipelineSegments.map((seg) => {
                  const pct =
                    totalPipeline > 0
                      ? Math.round((seg.value / totalPipeline) * 100)
                      : 0;
                  return (
                    <li
                      key={seg.label}
                      className="flex items-center justify-between gap-2 text-sm"
                    >
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <span
                          className="h-2.5 w-2.5 rounded-full shrink-0"
                          style={{ background: seg.color }}
                        />
                        {seg.label}
                      </span>
                      <span className="flex items-center gap-1.5 shrink-0">
                        <span className="font-mono text-xs font-semibold text-heading tabular-nums">
                          {seg.value}
                        </span>
                        <span className="text-[10px] text-muted-foreground opacity-60">
                          ({pct}%)
                        </span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          </GlassCard>
        </motion.div>
      </div>

      {/* 4. Recruitment Funnel */}
      <motion.div variants={item}>
        <GlassCard className="p-5">
          <h3 className="text-sm font-semibold text-heading mb-1">
            Recruitment Funnel
          </h3>
          <p className="text-xs text-muted-foreground mb-5">
            Candidates progressing through each stage
          </p>
          <div className="space-y-4">
            <FunnelBar
              label="Total Applications"
              value={m.totalCandidates}
              max={m.totalCandidates}
              color="var(--primary)"
            />
            <FunnelBar
              label="Processed"
              value={m.processedCount}
              max={m.totalCandidates}
              color="var(--strong)"
            />
            <FunnelBar
              label="Shortlisted"
              value={m.shortlistedCount ?? 0}
              max={m.totalCandidates}
              color="var(--promising)"
            />
          </div>
        </GlassCard>
      </motion.div>
    </motion.div>
  );
}
