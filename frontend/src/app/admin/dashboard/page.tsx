// src/app/admin/dashboard/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Briefcase, Users, Gauge, Clock, ChevronRight, Filter,
  Loader2, CalendarDays, X, Video, CheckCircle2, AlertCircle,
  Send, TrendingUp, Star, Zap,
} from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { RadialGauge, CountUp } from "@/components/ui/charts";
import { useMetrics } from "@/hooks/useMetrics";
import { useJobs } from "@/hooks/useJobs";
import { api } from "@/lib/api";

type DatePreset = "today" | "7d" | "30d" | "90d" | "custom" | "all";

const DATE_PRESETS: { key: DatePreset; label: string }[] = [
  { key: "today",  label: "Today" },
  { key: "7d",     label: "7 days" },
  { key: "30d",    label: "30 days" },
  { key: "90d",    label: "90 days" },
  { key: "custom", label: "Custom" },
  { key: "all",    label: "All time" },
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
  return <div className={`animate-pulse rounded-2xl bg-white/[0.04] ${className}`} />;
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

/* ── Inline KPI tile ── */
function KpiTile({
  label,
  value,
  suffix,
  decimals = 0,
  color,
  icon,
  delay = 0,
  subtitle,
}: {
  label: string;
  value: number;
  suffix?: string;
  decimals?: number;
  color: string;
  icon: React.ReactNode;
  delay?: number;
  subtitle?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay, ease: EASE }}
      className="relative overflow-hidden rounded-2xl p-4"
      style={{
        background: "var(--surface-card)",
        border: "1px solid var(--surface-border)",
      }}
    >
      {/* Glow orb */}
      <div
        className="pointer-events-none absolute -right-4 -top-4 h-20 w-20 rounded-full opacity-20 blur-2xl"
        style={{ background: color }}
      />
      {/* Bottom accent bar */}
      <div
        className="absolute bottom-0 left-0 right-0 h-[2px]"
        style={{ background: color, boxShadow: `0 0 10px ${color}80` }}
      />

      <div className="flex items-start justify-between gap-2">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <span
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
          style={{ background: `${color}1a`, color }}
        >
          {icon}
        </span>
      </div>

      <div className="mt-2 flex items-baseline gap-1">
        <span className="font-mono text-2xl font-bold tabular-nums" style={{ color: "var(--color-heading, #fff)" }}>
          <CountUp value={value} decimals={decimals} />
        </span>
        {suffix && <span className="text-xs text-muted-foreground">{suffix}</span>}
      </div>

      {subtitle && (
        <p className="mt-0.5 text-[10px] text-muted-foreground">{subtitle}</p>
      )}
    </motion.div>
  );
}

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

  const { data: m, isLoading, isPlaceholderData } = useMetrics({ jobId: selectedJobId, fromDate, toDate });
  const { data: jobs } = useJobs("Active");

  const loadActionCandidates = useCallback(async () => {
    try {
      const rows = await api.getActionNeededCandidates(selectedJobId);
      setActionCandidates(rows);
    } catch { /* non-fatal */ }
  }, [selectedJobId]);

  useEffect(() => { loadActionCandidates(); }, [loadActionCandidates]);

  async function inviteOne(candidateId: number) {
    setInviting((p) => ({ ...p, [candidateId]: "loading" }));
    try {
      await api.triggerInterviewInvite(candidateId);
      setInviting((p) => ({ ...p, [candidateId]: "done" }));
      setTimeout(loadActionCandidates, 1200);
    } catch {
      setInviting((p) => ({ ...p, [candidateId]: "error" }));
    }
  }

  if (isLoading || !m) {
    return (
      <div className="mx-auto max-w-[1400px] space-y-5 px-4 py-6 sm:px-6 lg:px-8">
        <Skeleton className="h-9 w-56" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
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

  // ── Derived values ────────────────────────────────────────────────────────
  const avgScore           = m.avgScore;
  const totalJobs          = selectedJobId != null ? 1 : (jobs?.length ?? m.totalJobs);
  const totalCandidates    = m.totalCandidates;
  const pendingCount       = m.pendingCount;
  const processedCount     = m.processedCount;
  const shortlistedCount   = m.shortlistedCount ?? 0;
  const failedCount        = m.failedCount;
  const topScore           = m.topScore ?? 0;
  const pendingReviewCount = m.pendingReviewCount ?? 0;
  const interviewReadyCount = m.interviewReadyCount ?? 0;
  const scoreDistribution  = m.scoreDistribution ?? [
    { label: "0–20", count: 0 }, { label: "21–40", count: 0 }, { label: "41–60", count: 0 },
    { label: "61–80", count: 0 }, { label: "81–100", count: 0 },
  ];

  const maxBucket  = Math.max(...scoreDistribution.map((b) => b.count), 1);
  const totalBuckets = scoreDistribution.reduce((s, b) => s + b.count, 0) || 1;

  // Funnel stages with conversion between each
  const funnelStages = [
    { label: "Total Applied",   value: totalCandidates, color: "#3DAFCC" },
    { label: "Processed by AI", value: processedCount,  color: "#1C99BF" },
    { label: "Shortlisted",     value: shortlistedCount, color: "#34C28A" },
    { label: "Interview Ready", value: interviewReadyCount, color: "#8B5CF6" },
  ];
  const funnelMax = Math.max(...funnelStages.map((s) => s.value), 1);

  // Donut
  const donutTotal = processedCount + pendingCount + failedCount;
  const donutData  = [
    { label: "Processed", value: processedCount, color: "#1C99BF" },
    { label: "Pending",   value: pendingCount,   color: "#F5B544" },
    { label: "Failed",    value: failedCount,    color: "#F25C7C" },
  ];

  const allActiveJobs = jobs ?? [];
  const activeJobs    = selectedJobId != null
    ? allActiveJobs.filter((j) => j.id === selectedJobId)
    : allActiveJobs;
  const selectedJobName = selectedJobId != null
    ? (allActiveJobs.find((j) => j.id === selectedJobId)?.title ?? "")
    : null;

  return (
    <div className="relative mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      {/* Dim overlay while switching jobs */}
      <AnimatePresence>
        {isPlaceholderData && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="pointer-events-none absolute inset-0 z-20 flex items-start justify-center pt-40"
            style={{ background: "rgba(0,0,0,0.25)", backdropFilter: "blur(1px)", borderRadius: 16 }}
          >
            <div className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-heading"
              style={{ background: "var(--surface-card)", border: "1px solid var(--surface-border)" }}>
              <Loader2 className="h-4 w-4 animate-spin text-primary" /> Updating…
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Header ── */}
      <motion.div
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: EASE }}
        className="mb-5 flex flex-wrap items-start justify-between gap-3"
      >
        <div>
          <h1 className="text-2xl font-bold text-heading">Recruitment Overview</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {selectedJobName ? `Showing data for: ${selectedJobName}` : "Real-time AI screening pipeline across all open roles."}
          </p>
        </div>

        {/* Filters (job + date) */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Job selector */}
          <div className="flex items-center gap-1.5">
            <Filter className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <div className="relative">
              <select
                value={selectedJobId ?? ""}
                onChange={(e) => setSelectedJobId(e.target.value === "" ? null : Number(e.target.value))}
                className="appearance-none rounded-xl border px-3 py-1.5 pr-7 text-xs font-medium focus:outline-none focus:ring-1"
                style={{
                  background: "var(--surface-card)",
                  borderColor: selectedJobId != null ? "rgba(28,153,191,0.5)" : "var(--surface-border)",
                  color: "var(--color-heading)",
                }}
              >
                <option value="">All Jobs</option>
                {allActiveJobs.map((job) => (
                  <option key={job.id} value={job.id}>{job.title}</option>
                ))}
              </select>
              <ChevronRight className="pointer-events-none absolute right-1.5 top-1/2 h-3 w-3 -translate-y-1/2 rotate-90 text-muted-foreground" />
            </div>
            {selectedJobId != null && (
              <button onClick={() => setSelectedJobId(null)}
                className="rounded-lg p-1 text-muted-foreground transition-colors hover:text-foreground">
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Date preset pills */}
          <div className="flex items-center gap-1.5">
            <CalendarDays className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <div className="flex rounded-xl border p-0.5"
              style={{ background: "var(--surface-card)", borderColor: "var(--surface-border)" }}>
              {DATE_PRESETS.map(({ key, label }) => (
                <button key={key} onClick={() => setPreset(key)}
                  className="rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors"
                  style={
                    preset === key
                      ? { background: "rgba(28,153,191,0.2)", color: "#1C99BF" }
                      : { color: "var(--muted-foreground)" }
                  }
                >{label}</button>
              ))}
            </div>
          </div>

          {/* Custom pickers */}
          {preset === "custom" && (
            <div className="flex items-center gap-2">
              <input type="date" value={customFrom} onChange={(e) => setCustomFrom(e.target.value)}
                className="rounded-xl border px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#1C99BF]/40"
                style={{ background: "var(--surface-card)", borderColor: "var(--surface-border)", color: "var(--color-heading)" }} />
              <span className="text-xs text-muted-foreground">→</span>
              <input type="date" value={customTo} onChange={(e) => setCustomTo(e.target.value)}
                className="rounded-xl border px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#1C99BF]/40"
                style={{ background: "var(--surface-card)", borderColor: "var(--surface-border)", color: "var(--color-heading)" }} />
              {(customFrom || customTo) && (
                <button onClick={() => { setCustomFrom(""); setCustomTo(""); }}
                  className="rounded-lg p-1 text-muted-foreground hover:text-foreground">
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          )}
        </div>
      </motion.div>

      {/* ── 6 KPI tiles ── */}
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <KpiTile label="Active Jobs"      value={totalJobs}          color="#1C99BF" icon={<Briefcase className="h-3.5 w-3.5" />} delay={0}    subtitle="open roles" />
        <KpiTile label="Total Candidates" value={totalCandidates}    color="#3DAFCC" icon={<Users     className="h-3.5 w-3.5" />} delay={0.05} subtitle="all applications" />
        <KpiTile label="Shortlisted"      value={shortlistedCount}   color="#34C28A" icon={<Star      className="h-3.5 w-3.5" />} delay={0.1}  subtitle="passed AI screen" />
        <KpiTile label="Avg Score"        value={avgScore}           color={scoreColor(avgScore)} icon={<Gauge className="h-3.5 w-3.5" />} delay={0.15} decimals={1} suffix="/100" />
        <KpiTile label="Pending Review"   value={pendingReviewCount} color="#F5B544" icon={<Clock     className="h-3.5 w-3.5" />} delay={0.2}  subtitle="awaiting HR action" />
        <KpiTile label="Interview Ready"  value={interviewReadyCount} color="#8B5CF6" icon={<Zap      className="h-3.5 w-3.5" />} delay={0.25} subtitle="invites auto-sent" />
      </div>

      {/* ── Row 2: Histogram + Funnel ── */}
      <div className="mb-4 grid gap-4 lg:grid-cols-3">

        {/* Score distribution histogram */}
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.12, ease: EASE }}
          className="lg:col-span-2"
        >
          <GlassCard className="h-full p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-heading">Score Distribution</h2>
                <p className="text-[11px] text-muted-foreground">{totalBuckets} candidates scored</p>
              </div>
              <div className="flex items-center gap-3">
                {[
                  { label: "Weak",      color: "#F25C7C" },
                  { label: "Promising", color: "#F5B544" },
                  { label: "Strong",    color: "#34C28A" },
                ].map((d) => (
                  <div key={d.label} className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full" style={{ background: d.color }} />
                    <span className="text-[11px] text-muted-foreground">{d.label}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex h-48 items-end gap-2">
              {scoreDistribution.map((bucket, i) => {
                const color     = BUCKET_COLORS[i] ?? "#1C99BF";
                const heightPct = (bucket.count / maxBucket) * 100;
                const pct       = Math.round((bucket.count / totalBuckets) * 100);
                return (
                  <div key={bucket.label} className="flex flex-1 flex-col items-center gap-1">
                    {/* Percentage label above bar */}
                    <span className="font-mono text-[10px] font-semibold tabular-nums" style={{ color }}>
                      {bucket.count > 0 ? `${pct}%` : ""}
                    </span>
                    {/* Bar track */}
                    <div className="relative w-full flex-1 overflow-hidden rounded-lg"
                      style={{ background: "var(--surface-subtle)", minHeight: 80 }}>
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: `${heightPct}%` }}
                        transition={{ duration: 0.9, delay: i * 0.08, ease: EASE }}
                        className="absolute bottom-0 left-0 right-0 rounded-lg"
                        style={{
                          background: `linear-gradient(180deg, ${color}, ${color}99)`,
                          boxShadow: `0 0 16px ${color}33`,
                        }}
                      />
                      {/* Count label inside bar */}
                      <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: bucket.count > 0 ? 1 : 0 }}
                        transition={{ delay: 0.8 + i * 0.08 }}
                        className="absolute bottom-2 left-0 right-0 text-center font-mono text-[10px] font-bold text-white/80"
                      >
                        {bucket.count}
                      </motion.span>
                    </div>
                    <span className="text-[10px] text-muted-foreground">{bucket.label}</span>
                  </div>
                );
              })}
            </div>

            {/* Top score callout */}
            {topScore > 0 && (
              <div className="mt-4 flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5">
                <span className="text-[11px] text-muted-foreground">Top score</span>
                <span className="font-mono text-sm font-bold" style={{ color: scoreColor(topScore) }}>
                  {topScore.toFixed(1)} / 100
                </span>
              </div>
            )}
          </GlassCard>
        </motion.div>

        {/* Recruitment funnel */}
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2, ease: EASE }}
        >
          <GlassCard className="h-full p-5">
            <div className="mb-1">
              <h2 className="text-sm font-semibold text-heading">Recruitment Funnel</h2>
              <p className="text-[11px] text-muted-foreground">Conversion at each stage</p>
            </div>

            <div className="mt-4 flex flex-col gap-1">
              {funnelStages.map((stage, i) => {
                const widthPct = (stage.value / funnelMax) * 100;
                const prev     = funnelStages[i - 1];
                const convPct  = prev && prev.value > 0
                  ? Math.round((stage.value / prev.value) * 100)
                  : null;

                return (
                  <div key={stage.label}>
                    {/* Conversion arrow between stages */}
                    {convPct !== null && (
                      <div className="flex items-center gap-1 py-1 pl-1">
                        <svg className="h-3 w-3 shrink-0 text-muted-foreground/40" viewBox="0 0 12 12" fill="currentColor">
                          <path d="M6 1v8M3 7l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        <span className="text-[10px] font-mono text-muted-foreground/70">
                          {convPct}% converted
                        </span>
                      </div>
                    )}
                    <div>
                      <div className="mb-1.5 flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">{stage.label}</span>
                        <span className="font-mono text-xs font-semibold tabular-nums text-heading">
                          {stage.value}
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--surface-subtle)" }}>
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${widthPct}%` }}
                          transition={{ duration: 1, delay: i * 0.12, ease: EASE }}
                          className="h-full rounded-full"
                          style={{
                            background: `linear-gradient(90deg, ${stage.color}, ${stage.color}cc)`,
                            boxShadow: `0 0 10px ${stage.color}40`,
                          }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Overall conversion */}
            {totalCandidates > 0 && (
              <div className="mt-5 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5 text-center">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Overall Shortlist Rate
                </p>
                <p className="mt-1 font-mono text-2xl font-bold" style={{ color: "#34C28A" }}>
                  {Math.round((shortlistedCount / totalCandidates) * 100)}%
                </p>
                <p className="text-[10px] text-muted-foreground">
                  {shortlistedCount} of {totalCandidates} applied
                </p>
              </div>
            )}
          </GlassCard>
        </motion.div>
      </div>

      {/* ── Row 3: Status donut + Active jobs ── */}
      <div className="mb-4 grid gap-4 lg:grid-cols-3">

        {/* Status donut */}
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.24, ease: EASE }}
        >
          <GlassCard className="h-full p-5">
            <h2 className="mb-4 text-sm font-semibold text-heading">Status Breakdown</h2>
            <div className="flex flex-col items-center">
              {/* SVG donut */}
              {(() => {
                const size = 152, thickness = 20, r = (size - thickness) / 2;
                const c = 2 * Math.PI * r;
                let acc = 0;
                const total2 = donutTotal || 1;
                return (
                  <div className="relative" style={{ width: size, height: size }}>
                    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
                      <circle cx={size / 2} cy={size / 2} r={r} fill="none"
                        stroke="rgba(255,255,255,0.04)" strokeWidth={thickness} />
                      {donutData.map((slice, i) => {
                        const frac = slice.value / total2;
                        const dash = c * frac, gap = c - dash;
                        const offset = -(acc * c);
                        acc += frac;
                        return (
                          <motion.circle key={slice.label}
                            cx={size / 2} cy={size / 2} r={r}
                            fill="none" stroke={slice.color} strokeWidth={thickness}
                            strokeDasharray={`${dash} ${gap}`} strokeDashoffset={offset}
                            initial={{ opacity: 0, strokeDasharray: `0 ${c}` }}
                            animate={{ opacity: 1, strokeDasharray: `${dash} ${gap}` }}
                            transition={{ duration: 1, delay: i * 0.15, ease: EASE }}
                            style={{ filter: `drop-shadow(0 0 4px ${slice.color}40)` }}
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

              <div className="mt-4 w-full space-y-2">
                {donutData.map((slice) => (
                  <div key={slice.label} className="flex items-center gap-2.5">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ background: slice.color, boxShadow: `0 0 6px ${slice.color}80` }} />
                    <span className="flex-1 text-xs text-muted-foreground">{slice.label}</span>
                    <span className="font-mono text-xs font-semibold tabular-nums text-heading">{slice.value}</span>
                    <span className="w-8 text-right font-mono text-[10px] text-muted-foreground">
                      {donutTotal ? Math.round((slice.value / donutTotal) * 100) : 0}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </GlassCard>
        </motion.div>

        {/* Active roles + gauge */}
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.28, ease: EASE }}
          className="lg:col-span-2"
        >
          <GlassCard className="h-full p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-heading">Active Roles &amp; Pipeline Health</h2>
                <p className="text-[11px] text-muted-foreground">{activeJobs.length} open position{activeJobs.length !== 1 ? "s" : ""}</p>
              </div>
              <Link href="/admin/candidates"
                className="flex items-center gap-1 text-xs text-primary transition-colors hover:text-primary/80">
                View candidates <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            {/* Gauge + pipeline stats */}
            <div className="mb-5 flex items-center gap-6">
              <div className="shrink-0">
                <RadialGauge value={avgScore} max={100} size={104} stroke={8}
                  color={scoreColor(avgScore)} label="Avg Score" />
              </div>
              <div className="flex flex-1 flex-col gap-2 min-w-0">
                {[
                  { label: "Shortlisted",     value: shortlistedCount,    color: "#34C28A", of: totalCandidates },
                  { label: "In Pipeline",     value: processedCount,      color: "#1C99BF", of: totalCandidates },
                  { label: "Pending",         value: pendingCount,        color: "#F5B544", of: null },
                  { label: "Interview Ready", value: interviewReadyCount, color: "#8B5CF6", of: shortlistedCount },
                ].map((item) => (
                  <div key={item.label} className="flex items-center gap-2.5">
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: item.color, boxShadow: `0 0 5px ${item.color}80` }} />
                    <span className="flex-1 text-xs text-muted-foreground">{item.label}</span>
                    <span className="font-mono text-sm font-bold tabular-nums" style={{ color: item.color }}>
                      <CountUp value={item.value} />
                    </span>
                    {item.of != null && item.of > 0 && (
                      <span className="w-8 text-right font-mono text-[10px] text-muted-foreground">
                        {Math.round((item.value / item.of) * 100)}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Job cards */}
            {activeJobs.length === 0 ? (
              <div className="flex h-24 items-center justify-center rounded-xl text-sm text-muted-foreground"
                style={{ background: "var(--surface-card)", border: "1px dashed var(--surface-border)" }}>
                No active roles — create your first job to get started.
              </div>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {activeJobs.slice(0, 4).map((job, i) => (
                  <Link key={job.id} href={`/admin/jobs?jobId=${job.id}`}
                    className="group flex items-center gap-3 rounded-xl p-3 transition-all glass-hover"
                    style={{ background: "var(--surface-card)", border: "1px solid var(--surface-border)" }}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold"
                      style={{ background: "rgba(28,153,191,0.15)", color: "#1C99BF", border: "1px solid rgba(28,153,191,0.2)" }}>
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-heading">{job.title}</p>
                      <p className="truncate text-[11px] text-muted-foreground">{job.department || "—"}</p>
                    </div>
                    <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                  </Link>
                ))}
              </div>
            )}

            {activeJobs.length > 4 && (
              <div className="mt-3 text-center">
                <Link href="/admin/jobs"
                  className="flex items-center justify-center gap-1 text-xs text-primary transition-colors hover:text-primary/80">
                  <TrendingUp className="h-3 w-3" />
                  {activeJobs.length - 4} more role{activeJobs.length - 4 !== 1 ? "s" : ""}
                  <ChevronRight className="h-3 w-3" />
                </Link>
              </div>
            )}
          </GlassCard>
        </motion.div>
      </div>

      {/* ── Row 4: Interview invites panel ── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.34, ease: EASE }}
      >
        <GlassCard className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg"
                style={{ background: "rgba(28,153,191,0.15)", border: "1px solid rgba(28,153,191,0.2)" }}>
                <Video className="h-4 w-4" style={{ color: "#1C99BF" }} />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-heading">Interview Invites</h2>
                <p className="text-[11px] text-muted-foreground">
                  Invites are sent automatically on score threshold. Re-send manually if needed.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {interviewReadyCount > 0 && (
                <span className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
                  style={{ background: "rgba(139,92,246,0.15)", color: "#8B5CF6", border: "1px solid rgba(139,92,246,0.25)" }}>
                  {interviewReadyCount} ready
                </span>
              )}
              <Link href="/admin/candidates"
                className="flex items-center gap-1 text-xs text-primary transition-colors hover:text-primary/80">
                View all <ChevronRight className="h-3 w-3" />
              </Link>
            </div>
          </div>

          {actionCandidates.length === 0 ? (
            <div className="flex items-center justify-center gap-2 rounded-xl py-7 text-sm text-muted-foreground"
              style={{ background: "var(--surface-card)", border: "1px dashed var(--surface-border)" }}>
              <CheckCircle2 className="h-4 w-4 text-[#34C28A]" />
              All shortlisted candidates have been invited
            </div>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {actionCandidates.map((c) => {
                const state = inviting[c.id];
                const sc    = c.total_score >= 70 ? "#34C28A" : c.total_score >= 40 ? "#F5B544" : "#F25C7C";
                return (
                  <div key={c.id}
                    className="flex items-center gap-3 rounded-xl px-3 py-2.5"
                    style={{ background: "var(--surface-card)", border: "1px solid var(--surface-border)" }}
                  >
                    {/* Score badge */}
                    <span className="shrink-0 rounded-lg px-2 py-1 font-mono text-xs font-bold tabular-nums"
                      style={{ background: `${sc}18`, color: sc, border: `1px solid ${sc}30` }}>
                      {Math.round(c.total_score)}
                    </span>

                    {/* Name + email */}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-heading">
                        {c.name || "Unknown Candidate"}
                      </p>
                      <p className="truncate text-[11px] text-muted-foreground">{c.email ?? "—"}</p>
                    </div>

                    {/* Actions */}
                    <div className="flex shrink-0 items-center gap-1.5">
                      <Link href={`/admin/candidates?candidateId=${c.id}`}
                        className="text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">
                        View
                      </Link>
                      <button
                        onClick={() => inviteOne(c.id)}
                        disabled={state === "loading" || state === "done"}
                        className="flex items-center gap-1 rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all disabled:cursor-not-allowed disabled:opacity-60"
                        style={
                          state === "done"  ? { background: "rgba(52,194,138,0.15)",  color: "#34C28A", border: "1px solid rgba(52,194,138,0.3)"  } :
                          state === "error" ? { background: "rgba(242,92,124,0.12)", color: "#F25C7C", border: "1px solid rgba(242,92,124,0.25)" } :
                                              { background: "rgba(28,153,191,0.15)",  color: "#1C99BF", border: "1px solid rgba(28,153,191,0.25)"  }
                        }
                      >
                        {state === "loading" ? <Loader2 className="h-3 w-3 animate-spin" /> :
                         state === "done"    ? <><CheckCircle2 className="h-3 w-3" /> Sent</> :
                         state === "error"   ? <><AlertCircle  className="h-3 w-3" /> Retry</> :
                                              <><Send className="h-3 w-3" /> Re-send</>}
                      </button>
                    </div>
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
