// src/app/admin/candidates/page.tsx
"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Search,
  Users,
  Upload,
  Eye,
  Archive,
  ChevronDown,
  X,
  Filter,
  Mail,
  ClipboardCheck,
  FileText,
  LayoutGrid,
  List,
  ArrowUpDown,
  Brain,
  Check,
  ExternalLink,
  SlidersHorizontal,
  Plus,
} from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { ScoreChip } from "@/components/ui/ScoreChip";
import { StatusBadge } from "@/components/candidates/StatusBadge";
import { StatusBadge as EvalStatusBadge } from "@/components/admin/StatusBadge";
import { useCandidates } from "@/hooks/useCandidates";
import { useJobs } from "@/hooks/useJobs";
import { useJobEvaluationEvents } from "@/hooks/useJobEvaluationEvents";
import type { Candidate, CandidateStatus, IqQuestionDetail } from "@/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ResumeViewer } from "@/components/admin/ResumeViewer";
import { ScoringWeightsEditor } from "@/components/admin/ScoringWeightsEditor";
import { QuestionBankEditor } from "@/components/admin/QuestionBankEditor";
import { CandidateNotesPanel } from "@/components/candidates/CandidateNotesPanel";
import { InterviewPanel } from "@/components/candidates/InterviewPanel";
import { KanbanBoard } from "@/components/admin/KanbanBoard";
import { CandidateTable } from "@/components/admin/CandidateTable";
import { api } from "@/lib/api";
import { toast } from "react-hot-toast";
import { downloadCSV } from "@/lib/csv";
import { formatDuration } from "@/lib/utils";
import { avatarGradient, initials, scoreMeta, recommendationCopy } from "@/lib/score";
import { FadeIn, Stagger, StaggerItem } from "@/components/ui/motion";
import { CountUp } from "@/components/ui/charts";
import { ScoreRing } from "@/components/ui/ScoreRing";

// ── Helpers ──────────────────────────────────────────────────────────────────

function avatarColor(name: string): string {
  const colors = [
    "#1C99BF",
    "#34C28A",
    "#F5B544",
    "#3DAFCC",
    "#8B5CF6",
    "#F25C7C",
    "#06B6D4",
  ];
  let h = 0;
  for (let i = 0; i < name.length; i++)
    h = ((h << 5) - h + name.charCodeAt(i)) | 0;
  return colors[Math.abs(h) % colors.length];
}

function candidateInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUS_OPTIONS: Array<CandidateStatus | ""> = [
  "",
  "Queued",
  "Processing",
  "Shortlisted",
  "Reviewed",
  "Rejected",
  "Ungraded",
  "Error",
];

const HR_STATUS_OPTIONS = [
  "",
  "Applied",
  "Screened",
  "Interview",
  "Offer",
  "Hired",
  "Rejected",
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AdminCandidatesPage() {
  const router = useRouter();
  const { data: jobs = [], isLoading: jobsLoading } = useJobs();
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<CandidateStatus | undefined>();
  const [hrStatus, setHrStatus] = useState<string | undefined>();
  const [sortBy, setSortBy] = useState<string>("total_score");
  const [order, setOrder] = useState<string>("desc");
  const [viewMode, setViewMode] = useState<"table" | "kanban">("table");
  const [query, setQuery] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const [selected, setSelected] = useState<Candidate | null>(null);
  const [modalTab, setModalTab] = useState<"details" | "interview">("details");
  const currentJob = jobs.find((j) => j.id === selected?.job_id);
  const [resumeOpen, setResumeOpen] = useState(false);
  const [topN, setTopN] = useState<number>(10);
  const activeJobId = selectedJobId ?? jobs[0]?.id ?? null;

  const { data, isLoading, error, refetch } = useCandidates({
    jobId: activeJobId ?? undefined,
    page: viewMode === "kanban" ? 1 : page,
    pageSize: viewMode === "kanban" ? 100 : 50,
    status,
    hrStatus,
    sortBy,
    order,
  });

  const candidates = data?.items ?? [];
  const q = query.trim().toLowerCase();
  const filteredCandidates = q
    ? candidates.filter((c) =>
        [c.name, c.email, c.filename].some((f) =>
          (f ?? "").toLowerCase().includes(q)
        )
      )
    : candidates;

  useJobEvaluationEvents(activeJobId);

  const handleView = (candidate: Candidate) => {
    setSelected(candidate);
    setModalTab("details");
  };

  const handleViewResume = (candidate: Candidate) => {
    setSelected(candidate);
    setResumeOpen(true);
  };

  const closeModal = () => setSelected(null);
  const closeResume = () => setResumeOpen(false);

  const exportCSV = () => {
    const csvData = candidates.map((c) => ({
      name: c.name ?? "-",
      email: c.email ?? "-",
      hr_status: c.hr_status ?? "Applied",
      effective_score: (c.hr_score_override ?? c.total_score)?.toFixed(1) ?? "0",
      total_score: c.total_score?.toFixed(1) ?? "0",
      iq_score: c.iq_score != null ? Math.round(c.iq_score).toString() : "-",
      iq_accuracy: c.iq_total
        ? Math.round((c.iq_correct! / c.iq_total) * 100).toString()
        : "-",
      iq_time_seconds:
        c.iq_time_seconds != null ? c.iq_time_seconds.toString() : "-",
      iq_attempted_at: c.iq_attempted_at ?? "-",
      status: c.status,
      submitted: c.created_at,
    }));
    downloadCSV("candidates.csv", csvData);
  };

  const parseEvidence = (evidence?: string) => {
    if (!evidence) return [];
    try {
      const arr = JSON.parse(evidence);
      return Array.isArray(arr) ? arr : [];
    } catch {
      return [];
    }
  };

  const parseList = (value?: string | null): string[] => {
    if (!value) return [];
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch {
      return [];
    }
  };

  const parseIqDetail = (value?: string | null): IqQuestionDetail[] => {
    if (!value) return [];
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? (parsed as IqQuestionDetail[]) : [];
    } catch {
      return [];
    }
  };

  const toggleSortOrder = () => {
    setOrder((prev) => (prev === "desc" ? "asc" : "desc"));
  };

  const withIq = candidates.filter((c) => c.iq_score != null);
  const avgIq = withIq.length
    ? Math.round(
        withIq.reduce((s, c) => s + (c.iq_score ?? 0), 0) / withIq.length
      )
    : null;
  const shortlisted = candidates.filter((c) => c.status === "Shortlisted").length;
  const interviews = candidates.filter((c) => c.hr_status === "Interview").length;

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="mb-5 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-heading">Candidates</h1>
          {data && (
            <p className="text-sm text-muted-foreground">
              {data.total} total
            </p>
          )}
        </div>
        <button
          onClick={() => (window.location.href = "/admin")}
          className="rounded-xl bg-[#1C99BF] px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-[#3DAFCC] hover:shadow-[0_0_24px_rgba(28,153,191,0.4)]"
        >
          <span className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            Upload Resume
          </span>
        </button>
      </div>

      {/* ── Controls card ──────────────────────────────────────────────────── */}
      <GlassCard className="mb-4 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              placeholder="Search by name, email, or file…"
              className="w-full rounded-xl border border-white/[0.06] bg-white/[0.02] py-2.5 pl-10 pr-4 text-sm text-heading placeholder:text-muted-foreground focus:border-[#1C99BF]/40 focus:outline-none"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {/* Job select */}
          <select
            className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-sm text-muted-foreground focus:outline-none"
            value={activeJobId ?? ""}
            disabled={jobsLoading || jobs.length === 0}
            onChange={(e) => {
              setSelectedJobId(Number(e.target.value));
              setPage(1);
            }}
          >
            <option value="" disabled hidden>
              Select role…
            </option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title}
              </option>
            ))}
          </select>

          {/* Status select */}
          <select
            className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-sm text-muted-foreground focus:outline-none"
            value={status ?? ""}
            onChange={(e) => {
              setStatus((e.target.value || undefined) as CandidateStatus | undefined);
              setPage(1);
            }}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option || "all"} value={option}>
                {option || "All Statuses"}
              </option>
            ))}
          </select>

          {/* HR Status select */}
          <select
            className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-sm text-muted-foreground focus:outline-none"
            value={hrStatus ?? ""}
            onChange={(e) => {
              setHrStatus(e.target.value || undefined);
              setPage(1);
            }}
          >
            {HR_STATUS_OPTIONS.map((option) => (
              <option key={option || "all"} value={option}>
                {option || "All Stages"}
              </option>
            ))}
          </select>

          {/* Sort + view toggles */}
          <div className="flex items-center gap-2">
            <select
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 text-sm text-muted-foreground focus:outline-none"
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value);
                setPage(1);
              }}
            >
              <option value="total_score">Score</option>
              <option value="created_at">Date</option>
              <option value="hr_status">Stage</option>
            </select>
            <button
              onClick={toggleSortOrder}
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-2.5 text-muted-foreground hover:text-heading transition-colors"
              title={`Currently ${order === "desc" ? "descending" : "ascending"}`}
            >
              <ArrowUpDown className="h-4 w-4" />
            </button>
          </div>

          {/* View mode */}
          <div className="flex items-center rounded-xl border border-white/[0.06] bg-white/[0.02] p-1 gap-0.5">
            <button
              onClick={() => setViewMode("table")}
              className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition-colors ${
                viewMode === "table"
                  ? "bg-[#1C99BF] text-white"
                  : "text-muted-foreground hover:text-heading"
              }`}
            >
              <List className="h-3.5 w-3.5" />
              Table
            </button>
            <button
              onClick={() => setViewMode("kanban")}
              className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition-colors ${
                viewMode === "kanban"
                  ? "bg-[#1C99BF] text-white"
                  : "text-muted-foreground hover:text-heading"
              }`}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              Kanban
            </button>
          </div>
        </div>
      </GlassCard>

      {/* ── Stat tiles ─────────────────────────────────────────────────────── */}
      {activeJobId && data && (
        <Stagger className="mb-4 grid grid-cols-2 gap-3.5 lg:grid-cols-4" gap={0.06}>
          {[
            { label: "Total applicants", value: data.total },
            { label: "Shortlisted", value: shortlisted, accent: true },
            {
              label: "Avg. aptitude",
              value: avgIq ?? 0,
              suffix: "%",
              placeholder: avgIq == null ? "—" : undefined,
            },
            { label: "In interview", value: interviews },
          ].map((t) => (
            <StaggerItem key={t.label}>
              <div
                className="h-full rounded-2xl p-[18px]"
                style={{
                  background: "var(--surface-card)",
                  border: "1px solid var(--surface-border)",
                  backdropFilter: "blur(12px)",
                }}
              >
                <p className="text-xs font-medium text-muted-foreground">
                  {t.label}
                </p>
                <div
                  className={`mt-1.5 font-mono text-[26px] font-semibold tabular-nums ${
                    t.accent ? "text-[#1C99BF]" : "text-heading"
                  }`}
                >
                  {t.placeholder ?? (
                    <CountUp value={t.value} suffix={t.suffix ?? ""} />
                  )}
                </div>
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      )}

      {/* ── Error state ────────────────────────────────────────────────────── */}
      {error && (
        <div className="mb-4 flex items-center gap-3 rounded-2xl border border-[#F25C7C]/30 bg-[#F25C7C]/5 p-4">
          <X className="h-5 w-5 shrink-0 text-[#F25C7C]" />
          <p className="text-sm text-[#F25C7C]">
            Failed to load candidates: {error.message}
          </p>
        </div>
      )}

      {/* ── No job selected ─────────────────────────────────────────────────── */}
      {!activeJobId && !jobsLoading && (
        <GlassCard className="flex flex-col items-center gap-3 px-6 py-20 text-center">
          <span
            className="flex h-12 w-12 items-center justify-center rounded-2xl"
            style={{ background: "rgba(28,153,191,0.1)", color: "#1C99BF" }}
          >
            <FileText className="h-6 w-6" />
          </span>
          <p className="text-base font-semibold text-heading">
            No job openings yet
          </p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Create a job opening first — candidates are ranked per role.
          </p>
        </GlassCard>
      )}

      {/* ── Main candidates list (agon table layout) ─────────────────────── */}
      {activeJobId && viewMode === "table" && (
        <>
          {/* Toolbar */}
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={exportCSV}
                className="h-9 gap-1.5 text-xs"
              >
                <ClipboardCheck className="h-4 w-4" />
                Export CSV
              </Button>

              <div className="flex items-center gap-1.5 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-1.5">
                <span className="text-xs text-muted-foreground">Top</span>
                <select
                  value={topN}
                  onChange={(e) => setTopN(Number(e.target.value))}
                  className="h-6 rounded-md border border-white/[0.06] bg-transparent px-1.5 text-xs text-muted-foreground focus:outline-none"
                >
                  {[5, 10, 15, 20, 25, 30].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  className="h-7 gap-1 bg-[#1C99BF] px-2 text-[11px] font-semibold text-white hover:bg-[#3DAFCC]"
                  onClick={async () => {
                    if (!activeJobId) {
                      toast.error("Select a job opening first.");
                      return;
                    }
                    try {
                      const res = await api.sendShortlistEmails(activeJobId, topN);
                      const msg = res.failed_count
                        ? `${res.failed_count} failed, ${topN - res.failed_count} sent`
                        : "All emails sent successfully!";
                      toast.success(msg);
                    } catch {
                      toast.error("Failed to send emails – please try again.");
                    }
                  }}
                >
                  <Mail className="h-3 w-3" />
                  Shortlist emails
                </Button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {data && (
                <p className="text-xs text-muted-foreground">
                  {candidates.length} of {data.total} candidates
                  {data.pages > 1 ? ` · page ${data.page}/${data.pages}` : ""}
                </p>
              )}
              <QuestionBankEditor jobId={activeJobId} />
              <ScoringWeightsEditor jobId={activeJobId} />
            </div>
          </div>

          {/* Agon-style candidates card */}
          <GlassCard className="overflow-hidden">
            {/* Header row */}
            <div className="hidden md:grid grid-cols-12 gap-4 border-b border-white/[0.06] px-5 py-3.5 text-xs uppercase tracking-wider text-muted-foreground/60">
              <div className="col-span-4">Candidate</div>
              <div className="col-span-3">Role</div>
              <div className="col-span-1">Score</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-1">Applied</div>
              <div className="col-span-1 text-right">Actions</div>
            </div>

            {/* Rows */}
            <div className="divide-y divide-white/[0.04]">
              {isLoading && (
                Array.from({ length: 5 }).map((_, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-12 gap-4 items-center px-5 py-4 animate-pulse"
                  >
                    <div className="col-span-4 flex items-center gap-3">
                      <div className="h-9 w-9 rounded-full bg-white/[0.06]" />
                      <div className="space-y-1.5">
                        <div className="h-3 w-28 rounded bg-white/[0.06]" />
                        <div className="h-2.5 w-20 rounded bg-white/[0.04]" />
                      </div>
                    </div>
                    <div className="col-span-3 h-3 w-24 rounded bg-white/[0.06]" />
                    <div className="col-span-1 h-5 w-10 rounded-full bg-white/[0.06]" />
                    <div className="col-span-2 h-5 w-16 rounded-full bg-white/[0.06]" />
                    <div className="col-span-1 h-3 w-10 rounded bg-white/[0.06]" />
                    <div className="col-span-1 flex justify-end gap-1">
                      <div className="h-8 w-8 rounded-lg bg-white/[0.06]" />
                    </div>
                  </div>
                ))
              )}

              {!isLoading && filteredCandidates.map((candidate, index) => {
                const displayName =
                  candidate.name || candidate.filename || "Unknown";
                const color = avatarColor(displayName);
                const jobTitle =
                  jobs.find((j) => j.id === candidate.job_id)?.title ?? "—";

                return (
                  <motion.div
                    key={candidate.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: index * 0.03 }}
                    className="grid grid-cols-12 gap-4 items-center px-5 py-4 hover:bg-white/[0.02] transition-colors cursor-pointer"
                    onClick={() => router.push(`/admin/candidates/${candidate.id}/interview`)}
                  >
                    {/* Candidate */}
                    <div className="col-span-4 flex items-center gap-3">
                      <div
                        className="h-9 w-9 shrink-0 rounded-full flex items-center justify-center text-xs font-bold text-white"
                        style={{ background: color }}
                      >
                        {candidateInitials(displayName)}
                      </div>
                      <div className="min-w-0">
                        <Link
                          href={`/admin/candidates/${candidate.id}/interview`}
                          className="text-sm font-medium text-heading hover:text-[#1C99BF] transition-colors truncate block"
                        >
                          {displayName}
                        </Link>
                        <p className="text-[11px] text-muted-foreground truncate">
                          {candidate.email ?? formatDate(candidate.created_at)}
                        </p>
                      </div>
                    </div>

                    {/* Role */}
                    <div className="col-span-3 text-sm text-muted-foreground truncate">
                      {jobTitle}
                    </div>

                    {/* Score */}
                    <div className="col-span-1">
                      <ScoreChip
                        score={candidate.hr_score_override ?? candidate.total_score}
                        size="sm"
                      />
                    </div>

                    {/* Status */}
                    <div className="col-span-2">
                      <StatusBadge
                        status={candidate.hr_status ?? candidate.status}
                      />
                    </div>

                    {/* Applied date */}
                    <div className="col-span-1 text-[11px] text-muted-foreground">
                      {formatDate(candidate.created_at)}
                    </div>

                    {/* Actions */}
                    <div className="col-span-1 flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                      <Link
                        href={`/admin/candidates/${candidate.id}/interview`}
                        className="p-2 rounded-lg text-muted-foreground hover:bg-[#1C99BF]/10 hover:text-[#1C99BF] transition-colors"
                        title="View interview"
                      >
                        <Eye className="h-4 w-4" />
                      </Link>
                      <button
                        onClick={() => handleView(candidate)}
                        className="p-2 rounded-lg text-muted-foreground hover:bg-[#F25C7C]/10 hover:text-[#F25C7C] transition-colors"
                        title="View details"
                      >
                        <FileText className="h-4 w-4" />
                      </button>
                    </div>
                  </motion.div>
                );
              })}

              {/* Empty state */}
              {!isLoading && filteredCandidates.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Users className="h-10 w-10 text-muted-foreground/40 mb-3" />
                  <p className="text-sm text-muted-foreground">
                    No candidates yet
                  </p>
                </div>
              )}
            </div>
          </GlassCard>

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <span className="text-xs text-muted-foreground">
                {data.page} / {data.pages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= data.pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {/* ── Kanban view ─────────────────────────────────────────────────────── */}
      {activeJobId && viewMode === "kanban" && (
        <KanbanBoard
          candidates={filteredCandidates}
          onView={handleView}
          onUpdate={refetch}
        />
      )}

      {/* ── Candidate detail modal ───────────────────────────────────────── */}
      <Dialog open={!!selected} onOpenChange={(open) => !open && closeModal()}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <div className="flex items-center gap-3.5">
              <span
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl text-base font-semibold text-white"
                style={{
                  background: avatarGradient(
                    selected?.name || selected?.filename || "?"
                  ),
                }}
                aria-hidden
              >
                {initials(selected?.name) === "··"
                  ? (selected?.filename?.[0] ?? "?").toUpperCase()
                  : initials(selected?.name)}
              </span>
              <div className="min-w-0">
                <DialogTitle className="font-display text-xl font-bold text-heading">
                  {selected?.name || selected?.filename || "Candidate Details"}
                </DialogTitle>
                <DialogDescription>
                  {selected?.email || "No email captured"}
                  {selected?.phone ? ` • ${selected.phone}` : ""}
                </DialogDescription>
              </div>
              {selected && (
                <ScoreChip
                  score={selected.hr_score_override ?? selected.total_score}
                />
              )}
            </div>
          </DialogHeader>

          {selected && modalTab === "details" && (
            <div className="mt-3 flex items-start gap-3 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3.5">
              <ScoreRing
                value={selected.hr_score_override ?? selected.total_score}
                size={56}
                stroke={6}
                label=""
                animate={false}
              />
              <p className="text-sm leading-relaxed text-foreground">
                <strong className="text-heading">
                  {scoreMeta(selected.hr_score_override ?? selected.total_score).label}{" "}
                  match.
                </strong>{" "}
                {recommendationCopy(selected.hr_score_override ?? selected.total_score)}
              </p>
            </div>
          )}

          <div className="mt-3 flex items-center justify-between gap-1 border-b border-white/[0.06]">
            <div className="flex items-center gap-1">
              {(["details", "interview"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setModalTab(t)}
                  className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium capitalize transition ${
                    modalTab === t
                      ? "border-[#1C99BF] text-heading"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {t === "interview" ? "Interview" : "Details"}
                </button>
              ))}
            </div>
            {modalTab === "interview" && selected && (
              <a
                href={`/admin/candidates/${selected.id}/interview`}
                className="mb-1 inline-flex items-center gap-1.5 rounded-lg border border-white/[0.06] px-2.5 py-1 text-xs font-medium text-foreground hover:bg-white/[0.04]"
              >
                Open full page <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>

          {modalTab === "interview" ? (
            <div className="mt-4 max-h-[75vh] overflow-y-auto pr-2">
              {selected && <InterviewPanel candidateId={selected.id} />}
            </div>
          ) : (
            <div className="mt-4 grid max-h-[75vh] gap-6 overflow-y-auto pr-2 lg:grid-cols-[1fr_300px]">
              <div className="space-y-4">
                <div className="glass-tile rounded-xl p-4">
                  <h3 className="mb-2 text-sm font-semibold text-[#1C99BF]">
                    Recruiter Summary
                  </h3>
                  <p className="text-sm leading-6 text-muted-foreground">
                    {selected?.summary || "No summary available yet."}
                  </p>
                </div>

                {currentJob && (
                  <div className="glass-tile max-h-[250px] overflow-y-auto rounded-xl p-4">
                    <h4 className="mb-1 text-sm font-semibold text-[#1C99BF]">
                      Job Description
                    </h4>
                    <p className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                      {currentJob.job_description}
                    </p>
                  </div>
                )}

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="glass-tile rounded-xl p-4">
                    <h3 className="mb-3 text-sm font-semibold text-[#34C28A]">
                      Matched Skills
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {(parseList(selected?.skills_matched).length
                        ? parseList(selected?.skills_matched)
                        : ["No matched skills captured"]
                      ).map((skill) => (
                        <span key={skill} className="chip chip-strong">
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="glass-tile rounded-xl p-4">
                    <h3 className="mb-3 text-sm font-semibold text-[#F5B544]">
                      Missing Skills
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {(parseList(selected?.skills_missing).length
                        ? parseList(selected?.skills_missing)
                        : ["No missing skills captured"]
                      ).map((skill) => (
                        <span key={skill} className="chip chip-promising">
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="glass-tile rounded-xl p-4">
                  <h3 className="mb-3 text-sm font-semibold text-heading">
                    Evidence
                  </h3>
                  <ul className="space-y-2">
                    {(selected?.evidence ? parseEvidence(selected.evidence) : []).map(
                      (e: string, idx: number) => (
                        <li
                          key={idx}
                          className="rounded-md border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-sm text-muted-foreground"
                        >
                          {e}
                        </li>
                      )
                    )}
                    {!selected?.evidence && (
                      <li className="text-sm text-muted-foreground">
                        No evidence items captured.
                      </li>
                    )}
                  </ul>
                </div>

                <div className="glass-tile rounded-xl p-4">
                  <h3 className="mb-3 text-sm font-semibold text-[#1C99BF]">
                    Suggested interview questions
                  </h3>
                  <ol className="list-decimal space-y-2 pl-5">
                    {parseList(selected?.interview_questions).map(
                      (iq: string, idx: number) => (
                        <li key={idx} className="text-sm text-muted-foreground">
                          {iq}
                        </li>
                      )
                    )}
                    {parseList(selected?.interview_questions).length === 0 && (
                      <li className="list-none text-sm text-muted-foreground">
                        None yet — generated when the résumé is scored by the LLM (Tier 3).
                      </li>
                    )}
                  </ol>
                  <p className="mt-2 text-[11px] text-muted-foreground">
                    The AI interviewer asks these as presets at the start of the interview.
                  </p>
                </div>

                {selected && (
                  <div className="glass-tile rounded-xl p-4">
                    <CandidateNotesPanel
                      candidateId={selected.id}
                      hrNotes={selected.hr_notes}
                      onUpdate={async () => {
                        refetch();
                        try {
                          const updated = await api.getCandidate(selected.id);
                          setSelected(updated);
                        } catch {
                          toast.error("Failed to sync updated notes.");
                        }
                      }}
                    />
                  </div>
                )}
              </div>

              <aside className="h-fit space-y-4 rounded-xl glass-tile p-4">
                <div className="space-y-2">
                  <p className="text-xs uppercase text-muted-foreground">
                    Evaluation status
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {selected && <EvalStatusBadge status={selected.status} />}
                    {selected && (
                      <StatusBadge status={selected.hr_status ?? selected.status} />
                    )}
                  </div>
                </div>

                <div className="flex flex-col items-center gap-2 border-t border-white/[0.06] pt-4">
                  <ScoreRing
                    value={selected?.hr_score_override ?? selected?.total_score}
                    size={120}
                    stroke={10}
                    label="effective score"
                  />
                  {selected?.hr_score_override !== null &&
                    selected?.hr_score_override !== undefined && (
                      <div className="text-center">
                        <p className="text-xs font-semibold text-[#F5B544]">
                          Overridden by HR
                        </p>
                        <p className="text-[10px] text-muted-foreground line-through">
                          Original: {selected.total_score.toFixed(1)}
                        </p>
                      </div>
                    )}
                </div>

                <div className="grid grid-cols-3 gap-2 border-t border-white/[0.06] pt-3 text-center">
                  {[
                    { label: "Tier 1", value: selected?.tier1 },
                    { label: "Tier 2", value: selected?.tier2 },
                    { label: "Tier 3", value: selected?.tier3 },
                  ].map(({ label, value }) => (
                    <div
                      key={label}
                      className="rounded-md bg-white/[0.04] p-2"
                    >
                      <p className="text-[10px] text-muted-foreground">{label}</p>
                      <p className="text-sm font-semibold text-heading">
                        {value?.toFixed(1) ?? "0.0"}
                      </p>
                    </div>
                  ))}
                </div>

                {selected?.iq_score != null && (
                  <div className="space-y-1.5 border-t border-white/[0.06] pt-3">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-xs uppercase text-muted-foreground">
                        <Brain className="h-3.5 w-3.5" /> Aptitude screen
                      </span>
                      <span className="text-sm font-semibold text-heading">
                        {Math.round(selected.iq_score)}%
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-[10px] text-muted-foreground">
                      {selected.iq_total ? (
                        <span>
                          Accuracy{" "}
                          {Math.round(
                            (selected.iq_correct! / selected.iq_total) * 100
                          )}
                          % ({selected.iq_correct}/{selected.iq_total})
                        </span>
                      ) : null}
                      {selected.iq_time_seconds != null ? (
                        <span>Time {formatDuration(selected.iq_time_seconds)}</span>
                      ) : null}
                      {selected.iq_attempted_at ? (
                        <span>
                          Attempted{" "}
                          {new Date(selected.iq_attempted_at).toLocaleString()}
                        </span>
                      ) : null}
                    </div>
                    <p className="text-[10px] text-muted-foreground/70">
                      Score is accuracy adjusted for time taken.
                    </p>

                    {parseIqDetail(selected.iq_details).length > 0 && (
                      <ol className="mt-2 space-y-2">
                        {parseIqDetail(selected.iq_details).map((iqd, i) => (
                          <li
                            key={iqd.id ?? i}
                            className="rounded-md border border-white/[0.06] bg-white/[0.02] p-2 text-[11px]"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <span className="font-medium text-foreground/90">
                                {i + 1}. {iqd.prompt}
                              </span>
                              <span className="flex shrink-0 items-center gap-1 text-[10px] text-muted-foreground">
                                {iqd.is_correct ? (
                                  <Check className="h-3 w-3 text-[#34C28A]" />
                                ) : (
                                  <X className="h-3 w-3 text-[#F25C7C]" />
                                )}
                                {iqd.time_seconds != null ? `${iqd.time_seconds}s` : ""}
                              </span>
                            </div>
                            <div className="mt-1 space-y-0.5">
                              <p className={iqd.is_correct ? "text-[#34C28A]" : "text-[#F25C7C]"}>
                                Answered: {iqd.chosen_text ?? "— (no answer)"}
                              </p>
                              {!iqd.is_correct && (
                                <p className="text-[#34C28A]/80">
                                  Correct: {iqd.correct_text}
                                </p>
                              )}
                            </div>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                )}

                <div className="space-y-2 border-t border-white/[0.06] pt-3 text-sm">
                  <p>
                    <span className="block text-xs text-muted-foreground">Role:</span>
                    {selected?.current_role || "-"}
                  </p>
                  <p>
                    <span className="block text-xs text-muted-foreground">Experience:</span>
                    {selected?.years_experience != null
                      ? `${selected.years_experience} yrs`
                      : "-"}
                  </p>
                  <p>
                    <span className="block text-xs text-muted-foreground">Companies:</span>
                    {parseList(selected?.companies).join(", ") || "-"}
                  </p>
                  <p>
                    <span className="block text-xs text-muted-foreground">Submitted:</span>
                    {selected
                      ? new Date(selected.created_at).toLocaleString()
                      : "-"}
                  </p>
                </div>

                {/* ── Availability scheduling ─────────────────────── */}
                {selected && (selected.availability_invited_at || selected.availability_response || selected.interview_confirmed_slot) && (
                  <div className="space-y-2 border-t border-white/[0.06] pt-3">
                    <p className="text-xs uppercase text-muted-foreground">Interview Scheduling</p>
                    {selected.interview_confirmed_slot ? (
                      <div className="rounded-lg bg-green-500/10 px-3 py-2 text-xs text-green-400">
                        <p className="font-semibold">Confirmed</p>
                        <p className="mt-0.5 text-green-300/80">{selected.interview_confirmed_slot}</p>
                      </div>
                    ) : selected.availability_response ? (
                      <div className="space-y-2">
                        <div className="rounded-lg bg-yellow-500/10 px-3 py-2 text-xs text-yellow-400">
                          <p className="font-semibold">Candidate available</p>
                          <p className="mt-0.5 text-yellow-300/80">{selected.availability_response}</p>
                        </div>
                        <button
                          onClick={async () => {
                            try {
                              const updated = await api.confirmInterviewSlot(selected.id, selected.availability_response!);
                              setSelected(updated);
                              refetch();
                              toast.success("Interview slot confirmed!");
                            } catch {
                              toast.error("Failed to confirm slot.");
                            }
                          }}
                          className="w-full rounded-lg bg-green-600/20 py-1.5 text-xs font-semibold text-green-400 transition-colors hover:bg-green-600/30"
                        >
                          Confirm this slot
                        </button>
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Availability form sent.{" "}
                        <span className="text-muted-foreground/60">Waiting for candidate response.</span>
                      </p>
                    )}
                  </div>
                )}

                <div className="space-y-2 border-t border-white/[0.06] pt-3">
                  {selected && (
                    <Button
                      className="w-full gap-2 text-xs"
                      variant="outline"
                      onClick={() => handleViewResume(selected)}
                    >
                      <FileText className="h-4 w-4" /> View Resume Text
                    </Button>
                  )}
                  <DialogClose asChild>
                    <Button className="w-full text-xs" variant="ghost">
                      Close
                    </Button>
                  </DialogClose>
                </div>
              </aside>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Resume viewer modal */}
      <ResumeViewer
        candidateId={selected?.id ?? 0}
        open={resumeOpen}
        onClose={closeResume}
      />
    </div>
  );
}
