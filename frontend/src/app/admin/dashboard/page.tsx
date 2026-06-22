// src/app/admin/dashboard/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Briefcase, Users, Gauge, Clock, ChevronRight, Trophy, Filter, Loader2, CalendarDays, X, Video, CheckCircle2, AlertCircle, Send } from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { Stat } from "@/components/ui/Stat";
import { RadialGauge, CountUp } from "@/components/ui/charts";
import { useMetrics } from "@/hooks/useMetrics";
import { useJobs } from "@/hooks/useJobs";
import { api } from "@/lib/api";

type DatePreset = "today" | "7d" | "30d" | "90d" | "custom" | "all";

const DATE_PRESETS: { key: DatePreset; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "7d",    label: "7 days" },
  { key: "30d",   label: "30 days" },
  { key: "90d",   label: "90 days" },
  { key: "custom", label: "Custom" },
  { key: "all",   label: "All time" },
];

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function presetToDates(preset: DatePreset): { from: string | null; to: string | null } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (preset === "all" || preset === "custom") return { from: null, to: null };
  if (preset === "today") return { from: isoDate(today), to: isoDate(today) };
  const days = preset === "7d" ? 7 : preset === "30d" ? 30 : 90;
  const from = new Date(today);
  from.setDate(from.getDate() - (days - 1));
  return { from: isoDate(from), to: isoDate(today) };
}

const EASE = [0.22, 1, 0.36, 1] as const;

function scoreColor(score: number): string {
  if (score >= 70) return "#34C28A";
  if (score >= 40) return "#F5B544";
  return "#F25C7C";
}

const BUCKET_COLORS = ["#F25C7C", "#F25C7C", "#F5B544", "#34C28A", "#34C28A"];

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded-2xl bg-white/[0.04] ${className}`} />
  );
}

type ActionCandidate = {
  id: number;
  name: string | null;
  email: string | null;
  job_id: number;
  total_score: number;
  status: string;
  hr_status: string | null;
};

export default function DashboardPage() {
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [preset, setPreset] = useState<DatePreset>("all");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [actionCandidates, setActionCandidates] = useState<ActionCandidate[]>([]);
  const [inviting, setInviting] = useState<Record<number, "loading" | "done" | "error">>({});

  const { from: presetFrom, to: presetTo } = presetToDates(preset);
  const fromDate = preset === "custom" ? (customFrom || null) : presetFrom;
  const toDate   = preset === "custom" ? (customTo   || null) : presetTo;

  const { data: m, isLoading, isPlaceholderData } = useMetrics({
    jobId: selectedJobId,
    fromDate,
    toDate,
  });
  const { data: jobs } = useJobs("Active");

  const loadActionCandidates = useCallback(async () => {
    try {
      const rows = await api.getActionNeededCandidates(selectedJobId);
      setActionCandidates(rows);
    } catch {
      // non-fatal; panel stays empty
    }
  }, [selectedJobId]);

  useEffect(() => { loadActionCandidates(); }, [loadActionCandidates]);

  async function inviteOne(candidateId: number) {
    setInviting((p) => ({ ...p, [candidateId]: "loading" }));
    try {
      await api.triggerInterviewInvite(candidateId);
      setInviting((p) => ({ ...p, [candidateId]: "done" }));
      // Refresh panel after invite sent
      setTimeout(loadActionCandidates, 1200);
    } catch {
      setInviting((p) => ({ ...p, [candidateId]: "error" }));
    }
  }

  if (isLoading || !m) {
    return (
      <div className="mx-auto max-w-[1400px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <div className="space-y-1.5">
          <Skeleton className="h-8 w-44" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-64 lg:col-span-2" />
          <Skeleton className="h-64" />
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-72" />
          <Skeleton className="h-72 lg:col-span-2" />
        </div>
      </div>
    );
  }

  const avgScore = m.avgScore;
  const totalJobs = selectedJobId != null ? 1 : (jobs?.length ?? m.totalJobs);
  const totalCandidates = m.totalCandidates;
  const pendingCount = m.pendingCount;
  const processedCount = m.processedCount;
  const shortlistedCount = m.shortlistedCount ?? 0;
  const failedCount = m.failedCount;
  const topScore = m.topScore ?? 0;
  const pendingReviewCount = m.pendingReviewCount ?? 0;
  const interviewReadyCount = m.interviewReadyCount ?? 0;
  const scoreDistribution = m.scoreDistribution ?? [
    { label: "0-20", count: 0 },
    { label: "21-40", count: 0 },
    { label: "41-60", count: 0 },
    { label: "61-80", count: 0 },
    { label: "81-100", count: 0 },
  ];

  const maxBucket = Math.max(...scoreDistribution.map((b) => b.count), 1);

  const funnelStages = [
    { label: "Total Applied", value: totalCandidates, color: "#3DAFCC" },
    { label: "Processed by AI", value: processedCount, color: "#1C99BF" },
    { label: "Shortlisted", value: shortlistedCount, color: "#34C28A" },
  ];
  const funnelMax = Math.max(...funnelStages.map((s) => s.value), 1);

  const donutTotal = processedCount + pendingCount + failedCount;
  const donutData = [
    { label: "Processed", value: processedCount, color: "#1C99BF" },
    { label: "Pending", value: pendingCount, color: "#F5B544" },
    { label: "Failed", value: failedCount, color: "#F25C7C" },
  ];

  const allActiveJobs = jobs ?? [];
  const activeJobs = selectedJobId != null
    ? allActiveJobs.filter((j) => j.id === selectedJobId)
    : allActiveJobs;
  const selectedJobName = selectedJobId != null
    ? (allActiveJobs.find((j) => j.id === selectedJobId)?.title ?? "")
    : null;

  return (
    <div className="relative mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      {/* Dim overlay while job-specific data is loading */}
      <AnimatePresence>
        {isPlaceholderData && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="pointer-events-none absolute inset-0 z-20 flex items-start justify-center pt-40"
            style={{ background: "rgba(0,0,0,0.25)", backdropFilter: "blur(1px)", borderRadius: 16 }}
          >
            <div
              className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-heading"
              style={{ background: "var(--surface-card)", border: "1px solid var(--surface-border)" }}
            >
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              Updating…
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      {/* Page title + filters */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: EASE }}
        className="mb-6 space-y-3"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-heading">Recruitment Overview</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {selectedJobName
                ? `Showing data for: ${selectedJobName}`
                : "Real-time AI screening pipeline across all open roles."}
            </p>
          </div>

          {/* Job filter */}
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 shrink-0 text-muted-foreground" />
            <div className="relative">
              <select
                value={selectedJobId ?? ""}
                onChange={(e) =>
                  setSelectedJobId(e.target.value === "" ? null : Number(e.target.value))
                }
                className="appearance-none rounded-xl border px-3 py-2 pr-8 text-sm font-medium focus:outline-none focus:ring-1"
                style={{
                  background: "var(--surface-card)",
                  borderColor: selectedJobId != null ? "rgba(28,153,191,0.5)" : "var(--surface-border)",
                  color: "var(--color-heading)",
                }}
              >
                <option value="">All Jobs</option>
                {(jobs ?? []).map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                ))}
              </select>
              <ChevronRight className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 rotate-90 text-muted-foreground" />
            </div>
            {selectedJobId != null && (
              <button
                onClick={() => setSelectedJobId(null)}
                className="rounded-lg px-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                ✕ Clear
              </button>
            )}
          </div>
        </div>

        {/* Date range filter */}
        <div className="flex flex-wrap items-center gap-2">
          <CalendarDays className="h-4 w-4 shrink-0 text-muted-foreground" />
          <div
            className="flex rounded-xl border p-0.5"
            style={{ background: "var(--surface-card)", borderColor: "var(--surface-border)" }}
          >
            {DATE_PRESETS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setPreset(key)}
                className="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                style={
                  preset === key
                    ? { background: "rgba(28,153,191,0.2)", color: "#1C99BF" }
                    : { color: "var(--muted-foreground)" }
                }
              >
                {label}
              </button>
            ))}
          </div>

          {/* Custom date pickers (shown only when "Custom" selected) */}
          {preset === "custom" && (
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
                className="rounded-xl border px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#1C99BF]/40"
                style={{ background: "var(--surface-card)", borderColor: "var(--surface-border)", color: "var(--color-heading)" }}
              />
              <span className="text-xs text-muted-foreground">to</span>
              <input
                type="date"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
                className="rounded-xl border px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#1C99BF]/40"
                style={{ background: "var(--surface-card)", borderColor: "var(--surface-border)", color: "var(--color-heading)" }}
              />
              {(customFrom || customTo) && (
                <button
                  onClick={() => { setCustomFrom(""); setCustomTo(""); }}
                  className="rounded-lg p-1 text-muted-foreground transition-colors hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          )}

          {/* Active date range label */}
          {(fromDate || toDate) && preset !== "custom" && (
            <span className="text-xs text-muted-foreground">
              {fromDate && toDate && fromDate === toDate
                ? fromDate
                : `${fromDate ?? "…"} → ${toDate ?? "…"}`}
            </span>
          )}
        </div>
      </motion.div>

      {/* KPI Cards */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat
          label="Active Jobs"
          value={totalJobs}
          accentColor="#1C99BF"
          icon={<Briefcase className="h-4 w-4" />}
          delay={0}
        />
        <Stat
          label="Candidates"
          value={totalCandidates}
          accentColor="#3DAFCC"
          icon={<Users className="h-4 w-4" />}
          delay={0.08}
        />
        <Stat
          label="Avg Score"
          value={avgScore}
          suffix="/100"
          decimals={1}
          accentColor={scoreColor(avgScore)}
          icon={<Gauge className="h-4 w-4" />}
          delay={0.16}
        />
        <Stat
          label="Pending Review"
          value={pendingReviewCount}
          accentColor="#F5B544"
          icon={<Clock className="h-4 w-4" />}
          delay={0.24}
        />
      </div>

      {/* Middle row: Score distribution + Recruitment funnel */}
      <div className="mb-4 grid gap-4 lg:grid-cols-3">
        {/* Score distribution histogram */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: EASE }}
          className="lg:col-span-2"
        >
          <GlassCard className="h-full p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-heading">Score Distribution</h2>
              <div className="flex items-center gap-4">
                {[
                  { label: "Weak", color: "#F25C7C" },
                  { label: "Promising", color: "#F5B544" },
                  { label: "Strong", color: "#34C28A" },
                ].map((d) => (
                  <div key={d.label} className="flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: d.color }}
                    />
                    <span className="text-[11px] text-muted-foreground">{d.label}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex h-44 items-end gap-3">
              {scoreDistribution.map((bucket, i) => {
                const color = BUCKET_COLORS[i] ?? "#1C99BF";
                const heightPct = (bucket.count / maxBucket) * 100;
                return (
                  <div
                    key={bucket.label}
                    className="flex flex-1 flex-col items-center gap-2"
                  >
                    <span
                      className="font-mono text-xs font-semibold tabular-nums"
                      style={{ color }}
                    >
                      {bucket.count}
                    </span>
                    <div
                      className="relative w-full flex-1 rounded-lg"
                      style={{
                        background: "var(--surface-subtle)",
                        minHeight: 80,
                      }}
                    >
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: `${heightPct}%` }}
                        transition={{
                          duration: 1,
                          delay: i * 0.1,
                          ease: EASE,
                        }}
                        className="absolute bottom-0 left-0 right-0 rounded-lg"
                        style={{
                          background: `linear-gradient(180deg, ${color}, ${color}99)`,
                          boxShadow: `0 0 16px ${color}33`,
                        }}
                      />
                    </div>
                    <span className="text-[10px] text-muted-foreground">
                      {bucket.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </GlassCard>
        </motion.div>

        {/* Recruitment funnel */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.18, ease: EASE }}
        >
          <GlassCard className="h-full p-6">
            <h2 className="mb-4 text-sm font-semibold text-heading">
              Recruitment Funnel
            </h2>
            <div className="flex flex-col gap-4">
              {funnelStages.map((stage, i) => {
                const widthPct = (stage.value / funnelMax) * 100;
                return (
                  <div key={stage.label}>
                    <div className="mb-1.5 flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">
                        {stage.label}
                      </span>
                      <span className="font-mono text-xs font-semibold tabular-nums text-heading">
                        {stage.value}
                      </span>
                    </div>
                    <div
                      className="h-2.5 w-full overflow-hidden rounded-full"
                      style={{ background: "var(--surface-subtle)" }}
                    >
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${widthPct}%` }}
                        transition={{
                          duration: 1.1,
                          delay: i * 0.15,
                          ease: EASE,
                        }}
                        className="h-full rounded-full"
                        style={{
                          background: `linear-gradient(90deg, ${stage.color}, ${stage.color}cc)`,
                          boxShadow: `0 0 12px ${stage.color}40`,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            {totalCandidates > 0 && (
              <div className="mt-6 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 text-center">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Conversion Rate
                </p>
                <p
                  className="mt-1 font-mono text-2xl font-bold"
                  style={{ color: "#34C28A" }}
                >
                  {Math.round((shortlistedCount / totalCandidates) * 100)}%
                </p>
                <p className="text-[10px] text-muted-foreground">
                  {shortlistedCount} shortlisted
                </p>
              </div>
            )}
          </GlassCard>
        </motion.div>
      </div>

      {/* Bottom row: Status donut + Active jobs spotlight */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Status donut */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.22, ease: EASE }}
        >
          <GlassCard className="h-full p-6">
            <h2 className="mb-4 text-sm font-semibold text-heading">
              Status Breakdown
            </h2>
            <div className="flex flex-col items-center">
              {/* SVG donut */}
              {(() => {
                const size = 160;
                const thickness = 22;
                const r = (size - thickness) / 2;
                const c = 2 * Math.PI * r;
                let acc = 0;
                const total2 = donutTotal || 1;
                return (
                  <div
                    className="relative"
                    style={{ width: size, height: size }}
                  >
                    <svg
                      width={size}
                      height={size}
                      style={{ transform: "rotate(-90deg)" }}
                    >
                      <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={r}
                        fill="none"
                        stroke="rgba(255,255,255,0.04)"
                        strokeWidth={thickness}
                      />
                      {donutData.map((slice, i) => {
                        const frac = slice.value / total2;
                        const dash = c * frac;
                        const gap = c - dash;
                        const offset = -(acc * c);
                        acc += frac;
                        return (
                          <motion.circle
                            key={slice.label}
                            cx={size / 2}
                            cy={size / 2}
                            r={r}
                            fill="none"
                            stroke={slice.color}
                            strokeWidth={thickness}
                            strokeDasharray={`${dash} ${gap}`}
                            strokeDashoffset={offset}
                            initial={{
                              opacity: 0,
                              strokeDasharray: `0 ${c}`,
                            }}
                            animate={{
                              opacity: 1,
                              strokeDasharray: `${dash} ${gap}`,
                            }}
                            transition={{
                              duration: 1,
                              delay: i * 0.15,
                              ease: EASE,
                            }}
                            style={{
                              filter: `drop-shadow(0 0 4px ${slice.color}40)`,
                            }}
                          />
                        );
                      })}
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="font-mono text-2xl font-bold tabular-nums text-heading">
                        <CountUp value={donutTotal} />
                      </span>
                      <span className="mt-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                        Candidates
                      </span>
                    </div>
                  </div>
                );
              })()}
              <div className="mt-4 flex w-full flex-col gap-2">
                {donutData.map((slice) => (
                  <div key={slice.label} className="flex items-center gap-2.5">
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{
                        background: slice.color,
                        boxShadow: `0 0 6px ${slice.color}80`,
                      }}
                    />
                    <span className="text-xs text-muted-foreground">
                      {slice.label}
                    </span>
                    <span className="ml-auto font-mono text-xs font-semibold tabular-nums text-heading">
                      {slice.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Top score highlight */}
            {topScore > 0 && (
              <div className="mt-6 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 text-center">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Top Score
                </p>
                <p
                  className="mt-1 font-mono text-2xl font-bold"
                  style={{ color: scoreColor(topScore) }}
                >
                  <CountUp value={topScore} decimals={topScore % 1 ? 1 : 0} />
                </p>
                <p className="text-[10px] text-muted-foreground">out of 100</p>
              </div>
            )}
          </GlassCard>
        </motion.div>

        {/* Active jobs + Avg score gauge spotlight */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.26, ease: EASE }}
          className="lg:col-span-2"
        >
          <GlassCard className="h-full p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-heading">
                Active Roles &amp; Pipeline Health
              </h2>
              <Link
                href="/admin/candidates"
                className="flex items-center gap-1 text-xs text-primary transition-colors hover:text-primary/80"
              >
                View candidates <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            {/* Top row: score gauge + shortlisted callout */}
            <div className="mb-5 flex flex-wrap items-center gap-6">
              <div className="flex flex-col items-center">
                <RadialGauge
                  value={avgScore}
                  max={100}
                  size={110}
                  stroke={9}
                  color={scoreColor(avgScore)}
                  label="Avg Score"
                />
              </div>
              <div className="flex flex-1 flex-col gap-3 min-w-[140px]">
                {[
                  {
                    label: "Shortlisted",
                    value: shortlistedCount,
                    color: "#34C28A",
                  },
                  {
                    label: "In Pipeline",
                    value: processedCount,
                    color: "#1C99BF",
                  },
                  {
                    label: "Pending",
                    value: pendingCount,
                    color: "#F5B544",
                  },
                ].map((item) => (
                  <div key={item.label} className="flex items-center gap-3">
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{
                        background: item.color,
                        boxShadow: `0 0 6px ${item.color}80`,
                      }}
                    />
                    <span className="flex-1 text-xs text-muted-foreground">
                      {item.label}
                    </span>
                    <span
                      className="font-mono text-sm font-bold tabular-nums"
                      style={{ color: item.color }}
                    >
                      <CountUp value={item.value} />
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Active jobs list */}
            {activeJobs.length === 0 ? (
              <div className="flex h-28 items-center justify-center text-sm text-muted-foreground">
                No active roles — create your first job posting to get started.
              </div>
            ) : (
              <div className="grid gap-2.5 sm:grid-cols-2">
                {activeJobs.slice(0, 4).map((job, i) => (
                  <Link
                    key={job.id}
                    href={`/admin/jobs?jobId=${job.id}`}
                    className="flex items-center gap-3 rounded-xl p-3.5 transition-all glass-hover"
                    style={{
                      background: "var(--surface-card)",
                      border: "1px solid var(--surface-border)",
                    }}
                  >
                    <span
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold"
                      style={{
                        background: "rgba(28,153,191,0.15)",
                        color: "#1C99BF",
                        border: "1px solid rgba(28,153,191,0.2)",
                      }}
                    >
                      {(i + 1).toString().padStart(2, "0")}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-heading">
                        {job.title}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {job.department}
                      </p>
                    </div>
                    <ChevronRight className="ml-auto h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  </Link>
                ))}
              </div>
            )}

            {activeJobs.length > 4 && (
              <div className="mt-3 text-center">
                <Link
                  href="/admin/jobs"
                  className="flex items-center justify-center gap-1 text-xs text-primary transition-colors hover:text-primary/80"
                >
                  <Trophy className="h-3 w-3" />
                  {activeJobs.length - 4} more active role
                  {activeJobs.length - 4 !== 1 ? "s" : ""}
                  <ChevronRight className="h-3 w-3" />
                </Link>
              </div>
            )}
          </GlassCard>
        </motion.div>
      </div>

      {/* Run Mock Interviews Panel */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.32, ease: EASE }}
        className="mt-4"
      >
        <GlassCard className="p-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span
                className="flex h-8 w-8 items-center justify-center rounded-lg"
                style={{ background: "rgba(28,153,191,0.15)", border: "1px solid rgba(28,153,191,0.2)" }}
              >
                <Video className="h-4 w-4" style={{ color: "#1C99BF" }} />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-heading">Run Interviews</h2>
                <p className="text-xs text-muted-foreground">
                  Shortlisted candidates awaiting interview invitation
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {interviewReadyCount > 0 && (
                <span
                  className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
                  style={{ background: "rgba(245,181,68,0.15)", color: "#F5B544", border: "1px solid rgba(245,181,68,0.25)" }}
                >
                  {interviewReadyCount} ready
                </span>
              )}
              <Link
                href="/admin/candidates"
                className="flex items-center gap-1 text-xs text-primary transition-colors hover:text-primary/80"
              >
                View all <ChevronRight className="h-3 w-3" />
              </Link>
            </div>
          </div>

          {actionCandidates.length === 0 ? (
            <div className="flex items-center justify-center gap-2 rounded-xl py-8 text-sm text-muted-foreground"
              style={{ background: "var(--surface-card)", border: "1px dashed var(--surface-border)" }}>
              <CheckCircle2 className="h-4 w-4 text-[#34C28A]" />
              All shortlisted candidates have been invited
            </div>
          ) : (
            <div className="space-y-2">
              {actionCandidates.map((c) => {
                const state = inviting[c.id];
                const scoreColor =
                  c.total_score >= 70 ? "#34C28A" : c.total_score >= 40 ? "#F5B544" : "#F25C7C";
                return (
                  <div
                    key={c.id}
                    className="flex items-center gap-3 rounded-xl px-4 py-3"
                    style={{ background: "var(--surface-card)", border: "1px solid var(--surface-border)" }}
                  >
                    {/* Score badge */}
                    <span
                      className="shrink-0 rounded-lg px-2 py-1 font-mono text-xs font-bold tabular-nums"
                      style={{ background: `${scoreColor}18`, color: scoreColor, border: `1px solid ${scoreColor}30` }}
                    >
                      {Math.round(c.total_score)}
                    </span>

                    {/* Name + email */}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-heading">
                        {c.name || "Unknown Candidate"}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">{c.email ?? "—"}</p>
                    </div>

                    {/* HR status */}
                    {c.hr_status && c.hr_status !== "Applied" && (
                      <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium"
                        style={{ background: "rgba(28,153,191,0.12)", color: "#1C99BF" }}>
                        {c.hr_status}
                      </span>
                    )}

                    {/* View link */}
                    <Link
                      href={`/admin/candidates?candidateId=${c.id}`}
                      className="shrink-0 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                    >
                      View
                    </Link>

                    {/* Invite button */}
                    <button
                      onClick={() => inviteOne(c.id)}
                      disabled={state === "loading" || state === "done"}
                      className="flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all disabled:cursor-not-allowed disabled:opacity-60"
                      style={
                        state === "done"
                          ? { background: "rgba(52,194,138,0.15)", color: "#34C28A", border: "1px solid rgba(52,194,138,0.3)" }
                          : state === "error"
                          ? { background: "rgba(242,92,124,0.12)", color: "#F25C7C", border: "1px solid rgba(242,92,124,0.25)" }
                          : { background: "rgba(28,153,191,0.15)", color: "#1C99BF", border: "1px solid rgba(28,153,191,0.25)" }
                      }
                    >
                      {state === "loading" ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : state === "done" ? (
                        <><CheckCircle2 className="h-3 w-3" /> Invited</>
                      ) : state === "error" ? (
                        <><AlertCircle className="h-3 w-3" /> Retry</>
                      ) : (
                        <><Send className="h-3 w-3" /> Invite</>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </GlassCard>
      </motion.div>
    </div>
  );
}
