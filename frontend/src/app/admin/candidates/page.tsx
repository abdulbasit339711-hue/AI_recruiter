// src/app/admin/candidates/page.tsx
"use client";

import React, { useState } from "react";
import { CandidateTable } from "@/components/admin/CandidateTable";
import { KanbanBoard } from "@/components/admin/KanbanBoard";
import { CandidateNotesPanel } from "@/components/candidates/CandidateNotesPanel";
import { InterviewPanel } from "@/components/candidates/InterviewPanel";
import { useCandidates } from "@/hooks/useCandidates";
import { useJobEvaluationEvents } from "@/hooks/useJobEvaluationEvents";
import { useJobs } from "@/hooks/useJobs";
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
import {
  Mail,
  ClipboardCheck,
  FileText,
  LayoutGrid,
  List,
  ArrowUpDown,
  Brain,
  Check,
  X,
  ExternalLink,
  Search,
  Upload,
  SlidersHorizontal,
  ChevronDown,
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "react-hot-toast";
import { downloadCSV } from "@/lib/csv";
import { formatDuration } from "@/lib/utils";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { StatusBadge as HRStatusBadge } from "@/components/candidates/StatusBadge";
import { ScoreChip } from "@/components/ui/ScoreChip";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { avatarGradient, initials, scoreMeta, recommendationCopy } from "@/lib/score";
import { FadeIn, Stagger, StaggerItem } from "@/components/ui/motion";
import { CountUp } from "@/components/ui/charts";

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

export default function AdminCandidatesPage() {
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

  // Stat tiles derived from current page
  const withIq = candidates.filter((c) => c.iq_score != null);
  const avgIq = withIq.length
    ? Math.round(
        withIq.reduce((s, c) => s + (c.iq_score ?? 0), 0) / withIq.length
      )
    : null;
  const shortlisted = candidates.filter((c) => c.status === "Shortlisted").length;
  const interviews = candidates.filter((c) => c.hr_status === "Interview").length;

  return (
    <div className="space-y-6">
      {/* ── Page header ──────────────────────────────────────────────── */}
      <FadeIn className="flex flex-col gap-6">
        {/* Top bar: title + primary actions */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col gap-1">
            <p className="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">
              Candidates
            </p>
            <h1 className="font-display text-[28px] font-bold leading-none tracking-tight text-heading">
              Candidate Leaderboard
            </h1>
            <p className="text-sm text-muted-foreground">
              Ranked applicants scored on résumé fit and aptitude.
            </p>
          </div>

          {/* Right-side controls */}
          <div className="flex flex-wrap items-center gap-2 self-start">
            {/* View mode toggle */}
            <div className="flex items-center rounded-xl border border-border bg-card p-1 gap-0.5">
              <button
                onClick={() => setViewMode("table")}
                className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition-colors ${
                  viewMode === "table"
                    ? "bg-primary text-white"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <List className="h-3.5 w-3.5" />
                Table
              </button>
              <button
                onClick={() => setViewMode("kanban")}
                className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition-colors ${
                  viewMode === "kanban"
                    ? "bg-primary text-white"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                Kanban
              </button>
            </div>

            {/* Job picker */}
            <div className="relative">
              <select
                className="h-9 appearance-none rounded-xl border border-border bg-card pl-3 pr-8 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
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
              <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            </div>
          </div>
        </div>

        {/* Search + filter bar */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative min-w-[220px] flex-1 max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              placeholder="Search by name, email, or file…"
              className="h-10 w-full rounded-xl border border-border bg-card py-2 pl-9 pr-3 text-sm placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {/* Filters toggle */}
          <button
            onClick={() => setFiltersOpen((p) => !p)}
            className={`inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-sm font-medium transition-colors ${
              filtersOpen || status || hrStatus
                ? "border-primary bg-primary/10 text-primary"
                : "border-border bg-card text-muted-foreground hover:text-foreground"
            }`}
          >
            <SlidersHorizontal className="h-4 w-4" />
            Filters
            {(status || hrStatus) && (
              <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-white">
                {[status, hrStatus].filter(Boolean).length}
              </span>
            )}
          </button>

          {/* Sort */}
          <div className="flex items-center gap-1.5">
            <select
              className="h-10 appearance-none rounded-xl border border-border bg-card px-3 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value);
                setPage(1);
              }}
            >
              <option value="total_score">Sort: Effective Score</option>
              <option value="created_at">Sort: Submission Date</option>
              <option value="hr_status">Sort: HR Stage</option>
            </select>
            <button
              onClick={toggleSortOrder}
              title={`Currently ${order === "desc" ? "descending" : "ascending"}`}
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowUpDown className="h-4 w-4" />
            </button>
          </div>

          {/* Upload resume (teal CTA) */}
          <Button
            className="ml-auto h-10 gap-2 bg-primary px-4 text-sm font-semibold text-white hover:bg-[#3DAFCC]"
            onClick={() => {
              // Navigate to upload page or trigger upload modal
              window.location.href = "/admin";
            }}
          >
            <Upload className="h-4 w-4" />
            Upload Resume
          </Button>
        </div>

        {/* Expanded filters panel */}
        {filtersOpen && (
          <div className="grid grid-cols-1 gap-3 rounded-2xl border border-border bg-card p-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">
                Evaluation Status
              </label>
              <select
                className="h-9 w-full rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                value={status ?? ""}
                onChange={(e) => {
                  setStatus(
                    (e.target.value || undefined) as CandidateStatus | undefined
                  );
                  setPage(1);
                }}
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option || "All Statuses"}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">
                HR Recruitment Stage
              </label>
              <select
                className="h-9 w-full rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
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
            </div>

            <div className="flex items-end">
              <button
                onClick={() => {
                  setStatus(undefined);
                  setHrStatus(undefined);
                }}
                className="h-9 rounded-xl border border-border bg-background px-3 text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                Clear filters
              </button>
            </div>
          </div>
        )}
      </FadeIn>

      {/* ── Stat tiles (only when job selected + data loaded) ─────── */}
      {activeJobId && data && (
        <Stagger className="grid grid-cols-2 gap-3.5 lg:grid-cols-4" gap={0.06}>
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
              <div className="glass-tile h-full rounded-2xl p-[18px]">
                <p className="text-xs font-medium text-muted-foreground">
                  {t.label}
                </p>
                <div
                  className={`mt-1.5 font-mono text-[26px] font-semibold tabular-nums ${
                    t.accent ? "text-primary" : "text-heading"
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

      {/* ── Error state ───────────────────────────────────────────── */}
      {error && (
        <FadeIn
          className="flex items-center gap-3 rounded-2xl border border-weak/30 bg-weak/5 p-4"
          y={8}
        >
          <X className="h-5 w-5 shrink-0 text-weak" />
          <p className="text-sm text-weak">
            Failed to load candidates: {error.message}
          </p>
        </FadeIn>
      )}

      {/* ── No job selected ───────────────────────────────────────── */}
      {!activeJobId && !jobsLoading && (
        <FadeIn
          className="flex flex-col items-center gap-3 rounded-2xl border border-border bg-card px-6 py-20 text-center"
          y={8}
        >
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <FileText className="h-6 w-6" />
          </span>
          <p className="font-display text-base font-semibold text-heading">
            No job openings yet
          </p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Create a job opening first — candidates are ranked per role.
          </p>
        </FadeIn>
      )}

      {/* ── Main content ──────────────────────────────────────────── */}
      {activeJobId && (
        <>
          {/* Toolbar: export + editors */}
          <div className="flex flex-wrap items-center justify-between gap-3">
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

              {/* Shortlist emails */}
              <div className="flex items-center gap-1.5 rounded-xl border border-border bg-card px-3 py-1.5">
                <span className="text-xs text-muted-foreground">Top</span>
                <select
                  value={topN}
                  onChange={(e) => setTopN(Number(e.target.value))}
                  className="h-6 rounded-md border border-border bg-background px-1.5 text-xs focus:outline-none"
                >
                  {[5, 10, 15, 20, 25, 30].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  className="h-7 gap-1 bg-primary px-2 text-[11px] font-semibold text-white hover:bg-[#3DAFCC]"
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
                  {viewMode === "table" && data.pages > 1
                    ? ` · page ${data.page}/${data.pages}`
                    : ""}
                </p>
              )}
              <QuestionBankEditor jobId={activeJobId} />
              <ScoringWeightsEditor jobId={activeJobId} />
            </div>
          </div>

          {/* Table / Kanban */}
          {viewMode === "table" ? (
            <CandidateTable
              candidates={filteredCandidates}
              isLoading={isLoading || jobsLoading}
              onView={handleView}
              onUpdate={refetch}
            />
          ) : (
            <KanbanBoard
              candidates={filteredCandidates}
              onView={handleView}
              onUpdate={refetch}
            />
          )}

          {/* Pagination */}
          {viewMode === "table" && data && data.pages > 1 && (
            <div className="flex items-center justify-end gap-2">
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

      {/* ── Candidate detail modal ────────────────────────────────── */}
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

          {/* Plain-language recommendation */}
          {selected && modalTab === "details" && (
            <div className="mt-3 flex items-start gap-3 rounded-2xl border border-border bg-foreground/[0.03] p-3.5">
              <ScoreRing
                value={selected.hr_score_override ?? selected.total_score}
                size={56}
                stroke={6}
                label=""
                animate={false}
              />
              <p className="text-sm leading-relaxed text-foreground">
                <strong className="text-heading">
                  {
                    scoreMeta(selected.hr_score_override ?? selected.total_score)
                      .label
                  }{" "}
                  match.
                </strong>{" "}
                {recommendationCopy(
                  selected.hr_score_override ?? selected.total_score
                )}
              </p>
            </div>
          )}

          {/* Tabs */}
          <div className="mt-3 flex items-center justify-between gap-1 border-b border-border">
            <div className="flex items-center gap-1">
              {(["details", "interview"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setModalTab(t)}
                  className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium capitalize transition ${
                    modalTab === t
                      ? "border-primary text-heading"
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
                className="mb-1 inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-foreground/5"
                title="Open the full interview evaluation page"
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
                {/* Recruiter Summary */}
                <div className="glass-tile rounded-xl p-4">
                  <h3 className="mb-2 text-sm font-semibold text-primary">
                    Recruiter Summary
                  </h3>
                  <p className="text-sm leading-6 text-muted-foreground">
                    {selected?.summary || "No summary available yet."}
                  </p>
                </div>

                {/* Job Description */}
                {currentJob && (
                  <div className="glass-tile max-h-[250px] overflow-y-auto rounded-xl p-4">
                    <h4 className="mb-1 text-sm font-semibold text-primary">
                      Job Description
                    </h4>
                    <p className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                      {currentJob.job_description}
                    </p>
                  </div>
                )}

                {/* Skills matched / missing */}
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="glass-tile rounded-xl p-4">
                    <h3 className="mb-3 text-sm font-semibold text-strong">
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
                    <h3 className="mb-3 text-sm font-semibold text-promising">
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

                {/* Evidence */}
                <div className="glass-tile rounded-xl p-4">
                  <h3 className="mb-3 text-sm font-semibold text-heading">
                    Evidence
                  </h3>
                  <ul className="space-y-2">
                    {(selected?.evidence
                      ? parseEvidence(selected.evidence)
                      : []
                    ).map((e: string, idx: number) => (
                      <li
                        key={idx}
                        className="rounded-md border border-border bg-foreground/[0.04] px-3 py-2 text-sm text-muted-foreground"
                      >
                        {e}
                      </li>
                    ))}
                    {!selected?.evidence && (
                      <li className="text-sm text-muted-foreground">
                        No evidence items captured.
                      </li>
                    )}
                  </ul>
                </div>

                {/* Suggested interview questions */}
                <div className="glass-tile rounded-xl p-4">
                  <h3 className="mb-3 text-sm font-semibold text-primary">
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
                        None yet — generated when the résumé is scored by the
                        LLM (Tier 3).
                      </li>
                    )}
                  </ol>
                  <p className="mt-2 text-[11px] text-muted-foreground">
                    The AI interviewer asks these as presets at the start of the
                    interview.
                  </p>
                </div>

                {/* Recruitment Notes Panel */}
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

              {/* Sidebar */}
              <aside className="h-fit space-y-4 rounded-xl glass-tile p-4">
                <div className="space-y-2">
                  <p className="text-xs uppercase text-muted-foreground">
                    Evaluation status
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {selected && <StatusBadge status={selected.status} />}
                    {selected && (
                      <HRStatusBadge status={selected.hr_status} />
                    )}
                  </div>
                </div>

                <div className="flex flex-col items-center gap-2 border-t border-border pt-4">
                  <ScoreRing
                    value={
                      selected?.hr_score_override ?? selected?.total_score
                    }
                    size={120}
                    stroke={10}
                    label="effective score"
                  />
                  {selected?.hr_score_override !== null &&
                    selected?.hr_score_override !== undefined && (
                      <div className="text-center">
                        <p className="text-xs font-semibold text-promising">
                          Overridden by HR
                        </p>
                        <p className="text-[10px] text-muted-foreground line-through">
                          Original: {selected.total_score.toFixed(1)}
                        </p>
                      </div>
                    )}
                </div>

                <div className="grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
                  {[
                    { label: "Tier 1", value: selected?.tier1 },
                    { label: "Tier 2", value: selected?.tier2 },
                    { label: "Tier 3", value: selected?.tier3 },
                  ].map(({ label, value }) => (
                    <div
                      key={label}
                      className="rounded-md bg-foreground/[0.04] p-2"
                    >
                      <p className="text-[10px] text-muted-foreground">
                        {label}
                      </p>
                      <p className="text-sm font-semibold">
                        {value?.toFixed(1) ?? "0.0"}
                      </p>
                    </div>
                  ))}
                </div>

                {selected?.iq_score != null && (
                  <div className="space-y-1.5 border-t border-border pt-3">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-xs uppercase text-muted-foreground">
                        <Brain className="h-3.5 w-3.5" /> Aptitude screen
                      </span>
                      <span className="text-sm font-semibold">
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
                            className="rounded-md border border-border bg-foreground/[0.03] p-2 text-[11px]"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <span className="font-medium text-foreground/90">
                                {i + 1}. {iqd.prompt}
                              </span>
                              <span className="flex shrink-0 items-center gap-1 text-[10px] text-muted-foreground">
                                {iqd.is_correct ? (
                                  <Check className="h-3 w-3 text-strong" />
                                ) : (
                                  <X className="h-3 w-3 text-weak" />
                                )}
                                {iqd.time_seconds != null
                                  ? `${iqd.time_seconds}s`
                                  : ""}
                              </span>
                            </div>
                            <div className="mt-1 space-y-0.5">
                              <p
                                className={
                                  iqd.is_correct ? "text-strong" : "text-weak"
                                }
                              >
                                Answered:{" "}
                                {iqd.chosen_text ?? "— (no answer)"}
                              </p>
                              {!iqd.is_correct && (
                                <p className="text-strong/80">
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

                <div className="space-y-2 border-t border-border pt-3 text-sm">
                  <p>
                    <span className="block text-xs text-muted-foreground">
                      Role:
                    </span>
                    {selected?.current_role || "-"}
                  </p>
                  <p>
                    <span className="block text-xs text-muted-foreground">
                      Experience:
                    </span>
                    {selected?.years_experience != null
                      ? `${selected.years_experience} yrs`
                      : "-"}
                  </p>
                  <p>
                    <span className="block text-xs text-muted-foreground">
                      Companies:
                    </span>
                    {parseList(selected?.companies).join(", ") || "-"}
                  </p>
                  <p>
                    <span className="block text-xs text-muted-foreground">
                      Submitted:
                    </span>
                    {selected
                      ? new Date(selected.created_at).toLocaleString()
                      : "-"}
                  </p>
                </div>

                <div className="space-y-2 border-t border-border pt-3">
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
