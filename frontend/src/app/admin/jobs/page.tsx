// src/app/admin/jobs/page.tsx
"use client";

import React, { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { useJobs } from "@/hooks/useJobs";
import { useCreateJob } from "@/hooks/useCreateJob";
import { useUpdateJob } from "@/hooks/useUpdateJob";
import { useArchiveJob } from "@/hooks/useArchiveJob";
import { JobCard } from "@/components/job/JobCard";
import { JobFormModal } from "@/components/admin/JobFormModal";
import {
  Plus, Briefcase, Users, Star, Search, SlidersHorizontal,
  LayoutGrid, List, ChevronDown,
} from "lucide-react";
import type { Job } from "@/types";
import { useIsAdmin } from "@/hooks/useRole";

type DeadlineFilter = "all" | "closing-soon" | "overdue";
type SortKey = "newest" | "oldest" | "most-candidates" | "top-score" | "shortlist-rate";
type ViewMode = "grid" | "list";

const EASE = [0.22, 1, 0.36, 1] as const;

function matchesDeadline(job: Job, filter: DeadlineFilter): boolean {
  if (filter === "all") return true;
  const deadline = job.resume_deadline;
  if (!deadline) return false;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diff = Math.ceil((new Date(deadline).getTime() - today.getTime()) / 86_400_000);
  if (filter === "overdue") return diff < 0;
  if (filter === "closing-soon") return diff >= 0 && diff <= 7;
  return false;
}

function sortJobs(jobs: Job[], key: SortKey): Job[] {
  return [...jobs].sort((a, b) => {
    switch (key) {
      case "newest":          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      case "oldest":          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      case "most-candidates": return (b.candidate_count ?? 0) - (a.candidate_count ?? 0);
      case "top-score":       return (b.top_score ?? 0) - (a.top_score ?? 0);
      case "shortlist-rate": {
        const ra = a.candidate_count ? (a.shortlisted_count ?? 0) / a.candidate_count : 0;
        const rb = b.candidate_count ? (b.shortlisted_count ?? 0) / b.candidate_count : 0;
        return rb - ra;
      }
      default: return 0;
    }
  });
}

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-2xl bg-white/[0.04] ${className}`} />;
}

function SummaryTile({ label, value, color, icon }: { label: string; value: string | number; color: string; icon: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 rounded-xl px-3.5 py-2.5"
      style={{ background: "var(--surface-card)", border: "1px solid var(--surface-border)" }}>
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
        style={{ background: `${color}18`, color }}>
        {icon}
      </span>
      <div>
        <p className="font-mono text-sm font-bold tabular-nums" style={{ color: "var(--color-heading, #fff)" }}>{value}</p>
        <p className="text-[10px] text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

export default function AdminJobsPage() {
  const { data: jobs = [], isLoading, isError, error } = useJobs();
  const createJobMutation = useCreateJob();
  const updateJobMutation = useUpdateJob();
  const archiveJobMutation = useArchiveJob();
  const isAdmin = useIsAdmin();

  const [isModalOpen, setModalOpen] = useState(false);
  const [editingJob, setEditingJob]   = useState<Job | null>(null);
  const [deadlineFilter, setDeadlineFilter] = useState<DeadlineFilter>("all");
  const [sortKey, setSortKey]   = useState<SortKey>("newest");
  const [search, setSearch]     = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [showSort, setShowSort] = useState(false);

  const SORT_OPTIONS: { key: SortKey; label: string }[] = [
    { key: "newest",          label: "Newest first" },
    { key: "oldest",          label: "Oldest first" },
    { key: "most-candidates", label: "Most candidates" },
    { key: "top-score",       label: "Top score" },
    { key: "shortlist-rate",  label: "Shortlist rate" },
  ];

  const filteredJobs = useMemo(() => {
    let result = jobs.filter((j) => matchesDeadline(j, deadlineFilter));
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (j) => j.title.toLowerCase().includes(q) || (j.department ?? "").toLowerCase().includes(q)
      );
    }
    return sortJobs(result, sortKey);
  }, [jobs, deadlineFilter, search, sortKey]);

  const totalCandidates  = jobs.reduce((s, j) => s + (j.candidate_count ?? 0), 0);
  const totalShortlisted = jobs.reduce((s, j) => s + (j.shortlisted_count ?? 0), 0);
  const shortlistRate    = totalCandidates > 0 ? Math.round((totalShortlisted / totalCandidates) * 100) : 0;

  const openCreate = () => { setEditingJob(null); setModalOpen(true); };
  const openEdit   = (job: Job) => { setEditingJob(job); setModalOpen(true); };

  const handleSubmit = async (
    data: { title: string; department: string; job_description: string; llm_prompt?: string; voice_prompt?: string; resume_deadline?: string; interview_deadline?: string },
    id?: number
  ) => {
    if (id) await updateJobMutation.mutateAsync({ id, ...data });
    else     await createJobMutation.mutateAsync(data);
  };

  const handleArchive = async (job: Job) => { await archiveJobMutation.mutateAsync(job.id); };

  if (isError) {
    return (
      <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-[#F25C7C]/20 bg-[#F25C7C]/10 p-4 text-sm text-[#F25C7C]">
          Error loading jobs: {error instanceof Error ? error.message : "Unknown"}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">

      {/* ── Header ── */}
      <motion.div
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: EASE }}
        className="mb-5 flex flex-wrap items-start justify-between gap-3"
      >
        <div>
          <h1 className="text-2xl font-bold text-heading">Job Openings</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {isLoading ? "Loading…" : `${jobs.length} active role${jobs.length !== 1 ? "s" : ""} in your pipeline`}
          </p>
        </div>
        {isAdmin && (
          <button onClick={openCreate}
            className="flex items-center gap-2 rounded-xl bg-[#1C99BF] px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-[#3DAFCC] hover:shadow-[0_0_24px_rgba(28,153,191,0.4)]">
            <Plus className="h-4 w-4" />
            Post New Job
          </button>
        )}
      </motion.div>

      {/* ── Summary tiles ── */}
      {!isLoading && jobs.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.05, ease: EASE }}
          className="mb-5 flex flex-wrap gap-2"
        >
          <SummaryTile label="Active roles"     value={jobs.length}          color="#1C99BF" icon={<Briefcase className="h-3.5 w-3.5" />} />
          <SummaryTile label="Total candidates" value={totalCandidates}      color="#3DAFCC" icon={<Users     className="h-3.5 w-3.5" />} />
          <SummaryTile label="Shortlisted"      value={totalShortlisted}     color="#34C28A" icon={<Star      className="h-3.5 w-3.5" />} />
          <SummaryTile label="Shortlist rate"   value={`${shortlistRate}%`}  color="#8B5CF6" icon={<Star      className="h-3.5 w-3.5" />} />
        </motion.div>
      )}

      {/* ── Toolbar ── */}
      {!isLoading && jobs.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.08, ease: EASE }}
          className="mb-5 flex flex-wrap items-center gap-2"
        >
          {/* Search */}
          <div className="relative min-w-[180px] flex-1 max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              placeholder="Search title or department…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border py-2 pr-3 text-sm focus:outline-none focus:ring-1 focus:ring-[#1C99BF]/40"
              style={{
                background: "var(--surface-card)",
                borderColor: "var(--surface-border)",
                color: "var(--color-heading)",
                paddingLeft: "2.125rem",
              }}
            />
          </div>

          {/* Deadline filter pills */}
          <div className="flex rounded-xl border p-0.5"
            style={{ background: "var(--surface-card)", borderColor: "var(--surface-border)" }}>
            {(["all", "closing-soon", "overdue"] as DeadlineFilter[]).map((f) => (
              <button key={f} onClick={() => setDeadlineFilter(f)}
                className="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                style={deadlineFilter === f
                  ? { background: "rgba(28,153,191,0.2)", color: "#1C99BF" }
                  : { color: "var(--muted-foreground)" }}>
                {f === "all" ? "All" : f === "closing-soon" ? "Closing soon" : "Overdue"}
              </button>
            ))}
          </div>

          {/* Sort dropdown */}
          <div className="relative">
            <button onClick={() => setShowSort((p) => !p)}
              className="flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors"
              style={{
                background: "var(--surface-card)",
                borderColor: showSort ? "rgba(28,153,191,0.4)" : "var(--surface-border)",
                color: "var(--color-heading)",
              }}>
              <SlidersHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
              {SORT_OPTIONS.find((o) => o.key === sortKey)?.label}
              <ChevronDown className={`h-3 w-3 text-muted-foreground transition-transform ${showSort ? "rotate-180" : ""}`} />
            </button>
            {showSort && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowSort(false)} />
                <div className="absolute left-0 top-full z-20 mt-1 min-w-[170px] overflow-hidden rounded-xl border py-1 shadow-xl"
                  style={{ background: "var(--surface-card)", borderColor: "var(--surface-border)" }}>
                  {SORT_OPTIONS.map((opt) => (
                    <button key={opt.key}
                      onClick={() => { setSortKey(opt.key); setShowSort(false); }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors hover:bg-white/[0.05]"
                      style={{ color: sortKey === opt.key ? "#1C99BF" : "var(--color-heading)" }}>
                      <span className={`h-1.5 w-1.5 rounded-full transition-colors ${sortKey === opt.key ? "bg-[#1C99BF]" : ""}`} />
                      {opt.label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* View mode toggle */}
          <div className="flex rounded-xl border p-0.5"
            style={{ background: "var(--surface-card)", borderColor: "var(--surface-border)" }}>
            <button onClick={() => setViewMode("grid")}
              className="rounded-lg p-1.5 transition-colors"
              style={viewMode === "grid" ? { background: "rgba(28,153,191,0.2)", color: "#1C99BF" } : { color: "var(--muted-foreground)" }}>
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button onClick={() => setViewMode("list")}
              className="rounded-lg p-1.5 transition-colors"
              style={viewMode === "list" ? { background: "rgba(28,153,191,0.2)", color: "#1C99BF" } : { color: "var(--muted-foreground)" }}>
              <List className="h-3.5 w-3.5" />
            </button>
          </div>

          {filteredJobs.length !== jobs.length && (
            <span className="text-xs text-muted-foreground">
              Showing {filteredJobs.length} of {jobs.length}
            </span>
          )}
        </motion.div>
      )}

      {/* ── Loading skeletons ── */}
      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-56" />
          ))}
        </div>
      )}

      {/* ── Empty state (no jobs at all) ── */}
      {!isLoading && jobs.length === 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, ease: EASE }}
          className="flex flex-col items-center justify-center gap-5 rounded-2xl px-6 py-24 text-center"
          style={{ background: "var(--surface-card)", border: "1px dashed var(--surface-border)" }}
        >
          <span className="flex h-16 w-16 items-center justify-center rounded-2xl"
            style={{ background: "rgba(28,153,191,0.1)", color: "#1C99BF" }}>
            <Briefcase className="h-7 w-7" strokeWidth={1.5} />
          </span>
          <div>
            <p className="text-base font-semibold text-heading">No open roles yet</p>
            <p className="mt-1 max-w-xs text-sm text-muted-foreground">
              Create your first job posting to start AI-powered candidate screening.
            </p>
          </div>
          {isAdmin && (
            <button onClick={openCreate}
              className="flex items-center gap-2 rounded-xl bg-[#1C99BF] px-5 py-2.5 text-sm font-semibold text-white transition-all hover:bg-[#3DAFCC] hover:shadow-[0_0_24px_rgba(28,153,191,0.4)]">
              <Plus className="h-4 w-4" /> Post New Job
            </button>
          )}
        </motion.div>
      )}

      {/* ── No filter match ── */}
      {!isLoading && jobs.length > 0 && filteredJobs.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl py-16 text-center"
          style={{ background: "var(--surface-card)", border: "1px dashed var(--surface-border)" }}>
          <Search className="h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">No jobs match your filters.</p>
          <button onClick={() => { setSearch(""); setDeadlineFilter("all"); }}
            className="text-xs text-primary underline underline-offset-2">
            Clear filters
          </button>
        </div>
      )}

      {/* ── Jobs grid / list ── */}
      {!isLoading && filteredJobs.length > 0 && (
        viewMode === "grid" ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredJobs.map((job, i) => (
              <JobCard
                key={job.id}
                job={job}
                candidateCount={job.candidate_count}
                onEdit={isAdmin ? openEdit : undefined}
                onArchive={isAdmin ? handleArchive : undefined}
                index={i}
              />
            ))}
          </div>
        ) : (
          /* List view */
          <div className="flex flex-col gap-2">
            {filteredJobs.map((job, i) => {
              const count       = job.candidate_count ?? 0;
              const shortlisted = job.shortlisted_count ?? 0;
              const pct         = count > 0 ? Math.round((shortlisted / count) * 100) : 0;
              const avgScore    = job.avg_score;
              return (
                <motion.div key={job.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: i * 0.04, ease: EASE }}
                  className="flex items-center gap-4 rounded-xl px-4 py-3 transition-all hover:border-[#1C99BF]/30"
                  style={{ background: "var(--surface-card)", border: "1px solid var(--surface-border)" }}
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                    style={{ background: "rgba(28,153,191,0.12)", color: "#1C99BF" }}>
                    <Briefcase className="h-4 w-4" strokeWidth={2} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-heading">{job.title}</p>
                    <p className="text-[11px] text-muted-foreground">{job.department || "—"}</p>
                  </div>
                  <div className="hidden items-center gap-1.5 sm:flex">
                    <Users className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs tabular-nums text-muted-foreground">{count}</span>
                  </div>
                  {shortlisted > 0 && (
                    <div className="hidden items-center gap-1 md:flex">
                      <Star className="h-3.5 w-3.5 text-[#34C28A]" />
                      <span className="font-mono text-xs text-[#34C28A]">{pct}%</span>
                    </div>
                  )}
                  {avgScore != null && (
                    <span className="hidden font-mono text-xs font-semibold tabular-nums lg:block"
                      style={{ color: avgScore >= 70 ? "#34C28A" : avgScore >= 40 ? "#F5B544" : "#F25C7C" }}>
                      avg {avgScore.toFixed(1)}
                    </span>
                  )}
                  <span className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                    style={job.status === "Active"
                      ? { background: "rgba(28,153,191,0.15)", color: "#1C99BF" }
                      : { background: "rgba(107,114,128,0.15)", color: "#6B7280" }}>
                    {job.status}
                  </span>
                  <div className="flex items-center gap-1">
                    {isAdmin && (
                      <button onClick={() => openEdit(job)}
                        className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-[#1C99BF]/10 hover:text-[#1C99BF]"
                        title="Edit">
                        <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M11.5 2.5a2.121 2.121 0 013 3L5 15H2v-3L11.5 2.5z" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </button>
                    )}
                    {isAdmin && job.status !== "Archived" && (
                      <button onClick={() => handleArchive(job)}
                        className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-[#F25C7C]/10 hover:text-[#F25C7C]"
                        title="Archive">
                        <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M2 4h12M5 4V3a1 1 0 011-1h4a1 1 0 011 1v1M6 7v6M10 7v6M3 4l1 9a1 1 0 001 1h6a1 1 0 001-1l1-9" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </button>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        )
      )}

      <JobFormModal
        open={isModalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        initialData={editingJob ?? undefined}
      />
    </div>
  );
}
