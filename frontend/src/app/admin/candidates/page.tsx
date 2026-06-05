// src/app/admin/candidates/page.tsx
"use client";

import React, { useState } from "react";
import { CandidateTable } from "@/components/admin/CandidateTable";
import { KanbanBoard } from "@/components/admin/KanbanBoard";
import { CandidateNotesPanel } from "@/components/candidates/CandidateNotesPanel";
import { useCandidates } from "@/hooks/useCandidates";
import { useJobEvaluationEvents } from "@/hooks/useJobEvaluationEvents";
import { useJobs } from "@/hooks/useJobs";
import type { Candidate, CandidateStatus } from "@/types";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogClose } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ResumeViewer } from "@/components/admin/ResumeViewer";
import { Mail, ClipboardCheck, FileText, LayoutGrid, List, ArrowUpDown } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "react-hot-toast";
import { downloadCSV } from "@/lib/csv";
import { ScoreBar } from "@/components/admin/ScoreBar";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { StatusBadge as HRStatusBadge } from "@/components/candidates/StatusBadge";

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

const HR_STATUS_OPTIONS = ["", "Applied", "Screened", "Interview", "Offer", "Hired", "Rejected"];

export default function AdminCandidatesPage() {
  const { data: jobs = [], isLoading: jobsLoading } = useJobs();
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<CandidateStatus | undefined>();
  const [hrStatus, setHrStatus] = useState<string | undefined>();
  const [sortBy, setSortBy] = useState<string>("total_score");
  const [order, setOrder] = useState<string>("desc");
  const [viewMode, setViewMode] = useState<"table" | "kanban">("table");

  const [selected, setSelected] = useState<Candidate | null>(null);
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

  useJobEvaluationEvents(activeJobId);

  const handleView = (candidate: Candidate) => {
    setSelected(candidate);
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

  const toggleSortOrder = () => {
    setOrder((prev) => (prev === "desc" ? "asc" : "desc"));
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold">Candidate Leaderboard</h1>
          <p className="text-sm text-muted-foreground">Review ranked applicants, monitor queue status, and inspect evidence.</p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-1 self-start rounded-lg border border-white/10 bg-card p-1">
          <Button
            variant={viewMode === "table" ? "default" : "ghost"}
            size="sm"
            onClick={() => setViewMode("table")}
            className="h-8 px-3 gap-1.5 text-xs font-semibold"
          >
            <List className="h-4 w-4" /> Table
          </Button>
          <Button
            variant={viewMode === "kanban" ? "default" : "ghost"}
            size="sm"
            onClick={() => setViewMode("kanban")}
            className="h-8 px-3 gap-1.5 text-xs font-semibold"
          >
            <LayoutGrid className="h-4 w-4" /> Kanban
          </Button>
        </div>
      </div>

      {/* Filters and Controls */}
      <div className="flex flex-col gap-4 rounded-md border border-white/10 bg-card/70 p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 items-end">
          {/* Job select */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground" htmlFor="job-filter">Job Opening</label>
            <select
              id="job-filter"
              className="h-10 w-full rounded-md border border-white/10 bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={activeJobId ?? ""}
              disabled={jobsLoading || (jobs?.length ?? 0) === 0}
              onChange={(event) => {
                setSelectedJobId(Number(event.target.value));
                setPage(1);
              }}
            >
              <option value="" disabled hidden>Job filter</option>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.title} - {job.department}
                </option>
              ))}
            </select>
          </div>

          {/* System status */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground" htmlFor="status-filter">Evaluation Status</label>
            <select
              id="status-filter"
              className="h-10 w-full rounded-md border border-white/10 bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={status ?? ""}
              onChange={(event) => {
                setStatus((event.target.value || undefined) as CandidateStatus | undefined);
                setPage(1);
              }}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option || "all"} value={option}>
                  {option || "All Systems"}
                </option>
              ))}
            </select>
          </div>

          {/* HR recruitment status */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground" htmlFor="hr-status-filter">HR Recruitment Status</label>
            <select
              id="hr-status-filter"
              className="h-10 w-full rounded-md border border-white/10 bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={hrStatus ?? ""}
              onChange={(event) => {
                setHrStatus(event.target.value || undefined);
                setPage(1);
              }}
            >
              {HR_STATUS_OPTIONS.map((option) => (
                <option key={option || "all"} value={option}>
                  {option || "All Recruitment Stages"}
                </option>
              ))}
            </select>
          </div>

          {/* Sorting */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground" htmlFor="sort-filter">Sort Candidates</label>
            <div className="flex items-center gap-2">
              <select
                id="sort-filter"
                className="h-10 flex-1 rounded-md border border-white/10 bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                value={sortBy}
                onChange={(event) => {
                  setSortBy(event.target.value);
                  setPage(1);
                }}
              >
                <option value="total_score">Effective Score</option>
                <option value="created_at">Submission Date</option>
                <option value="hr_status">HR Stage</option>
              </select>
              <Button
                variant="outline"
                className="h-10 w-10 p-0 border-white/10"
                onClick={toggleSortOrder}
                title={`Sort ${order === "desc" ? "Descending" : "Ascending"}`}
              >
                <ArrowUpDown className="h-4 w-4 text-gray-400" />
              </Button>
            </div>
          </div>
        </div>

        {/* Shortlist actions */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-white/5 pt-4">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Shortlist Size:</span>
            <select
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              className="h-9 rounded-md border border-white/10 bg-background px-3 text-xs focus:outline-none"
            >
              {[5, 10, 15, 20, 25, 30].map((n) => (
                <option key={n} value={n}>Top {n}</option>
              ))}
            </select>
            <Button
              variant="default"
              size="sm"
              className="h-9 flex items-center gap-1.5 text-xs"
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
                } catch (err) {
                  toast.error("Failed to send emails – please try again.");
                }
              }}
            >
              <Mail className="h-3.5 w-3.5" /> Send shortlist emails
            </Button>
          </div>

          {data && (
            <p className="text-xs text-muted-foreground">
              Showing {candidates.length} of {data.total} candidates {viewMode === "table" ? `(Page ${data.page} of ${data.pages || 1})` : ""}
            </p>
          )}
        </div>
      </div>

      {/* Main content display */}
      {error && (
        <p className="text-sm text-red-500 mb-2">Failed to load candidates: {error.message}</p>
      )}
      {!activeJobId && !jobsLoading && (
        <p className="text-sm text-muted-foreground text-center py-12">Create a job opening before viewing candidates.</p>
      )}

      {activeJobId && (
        <>
          <div className="flex justify-between items-center mb-2">
            <Button variant="outline" size="sm" onClick={exportCSV} className="flex items-center gap-1.5 text-xs">
              <ClipboardCheck className="h-4 w-4" /> Export CSV
            </Button>
          </div>

          {viewMode === "table" ? (
            <CandidateTable
              candidates={candidates}
              isLoading={isLoading || jobsLoading}
              onView={handleView}
              onUpdate={refetch}
            />
          ) : (
            <KanbanBoard
              candidates={candidates}
              onView={handleView}
              onUpdate={refetch}
            />
          )}

          {/* Pagination (Table view only) */}
          {viewMode === "table" && data && data.pages > 1 && (
            <div className="flex items-center justify-end gap-2 mt-4">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= data.pages}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {/* Candidate detail modal */}
      <Dialog open={!!selected} onOpenChange={(open) => !open && closeModal()}>
        <DialogContent className="max-w-4xl bg-gray-950 text-white border-white/10">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold">{selected?.name || selected?.filename || "Candidate Details"}</DialogTitle>
            <DialogDescription className="text-gray-400">
              {selected?.email || "No email captured"} {selected?.phone ? `• ${selected.phone}` : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_300px] overflow-y-auto max-h-[75vh] pr-2">
            <div className="space-y-4">
               {/* Recruiter Summary */}
               <div className="rounded-md border border-white/10 bg-white/[0.03] p-4">
                 <h3 className="mb-2 text-sm font-semibold text-primary">Recruiter Summary</h3>
                 <p className="text-sm leading-6 text-muted-foreground">{selected?.summary || "No summary available yet."}</p>
               </div>

               {/* Job Description */}
               {currentJob && (
                 <div className="rounded-md border border-white/10 bg-white/[0.03] p-4 mt-4 max-h-[250px] overflow-y-auto">
                   <h4 className="mb-1 text-sm font-semibold text-primary">Job Description</h4>
                   <p className="text-sm leading-6 text-muted-foreground" dangerouslySetInnerHTML={{ __html: currentJob.job_description.replace(/\n/g, "<br/>") }} />
                 </div>
               )}

              {/* Skills matched / missing */}
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-md border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="mb-3 text-sm font-semibold text-emerald-400">Matched Skills</h3>
                  <div className="flex flex-wrap gap-2">
                    {(parseList(selected?.skills_matched).length ? parseList(selected?.skills_matched) : ["No matched skills captured"]).map((skill) => (
                      <span key={skill} className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-xs text-emerald-200">{skill}</span>
                    ))}
                  </div>
                </div>
                <div className="rounded-md border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="mb-3 text-sm font-semibold text-amber-400">Missing Skills</h3>
                  <div className="flex flex-wrap gap-2">
                    {(parseList(selected?.skills_missing).length ? parseList(selected?.skills_missing) : ["No missing skills captured"]).map((skill) => (
                      <span key={skill} className="rounded-full border border-amber-400/20 bg-amber-400/10 px-2.5 py-1 text-xs text-amber-200">{skill}</span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Evidence */}
              <div className="rounded-md border border-white/10 bg-white/[0.03] p-4">
                <h3 className="mb-3 text-sm font-semibold text-gray-300">Evidence</h3>
                <ul className="space-y-2">
                  {(selected?.evidence ? parseEvidence(selected.evidence) : []).map((e: string, idx: number) => (
                    <li key={idx} className="rounded-md border border-white/10 bg-background/60 px-3 py-2 text-sm text-muted-foreground">
                      {e}
                    </li>
                  ))}
                  {!selected?.evidence && <li className="text-sm text-muted-foreground">No evidence items captured.</li>}
                </ul>
              </div>

              {/* Recruitment Notes Panel */}
              {selected && (
                <div className="rounded-md border border-white/10 bg-white/[0.03] p-4">
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

            {/* Sidebar metadata panel */}
            <aside className="space-y-4 rounded-md border border-white/10 bg-white/[0.03] p-4 h-fit">
              <div className="space-y-2">
                <p className="text-xs uppercase text-muted-foreground">Evaluation status</p>
                <div className="flex flex-wrap gap-2">
                  {selected && <StatusBadge status={selected.status} />}
                  {selected && <HRStatusBadge status={selected.hr_status} />}
                </div>
              </div>

              <div className="border-t border-white/5 pt-3">
                <p className="mb-2 text-xs uppercase text-muted-foreground">Effective score</p>
                {selected?.hr_score_override !== null && selected?.hr_score_override !== undefined ? (
                  <div className="space-y-1">
                    <ScoreBar value={selected.hr_score_override} />
                    <p className="text-xs text-amber-400 font-semibold">Overridden</p>
                    <p className="text-[10px] text-muted-foreground line-through">Original: {selected.total_score.toFixed(1)}</p>
                  </div>
                ) : (
                  <ScoreBar value={selected?.total_score} />
                )}
              </div>

              <div className="grid grid-cols-3 gap-2 text-center border-t border-white/5 pt-3">
                <div className="rounded-md bg-background/60 p-2">
                  <p className="text-[10px] text-muted-foreground">Tier 1</p>
                  <p className="text-sm font-semibold">{selected?.tier1?.toFixed(1) ?? "0.0"}</p>
                </div>
                <div className="rounded-md bg-background/60 p-2">
                  <p className="text-[10px] text-muted-foreground">Tier 2</p>
                  <p className="text-sm font-semibold">{selected?.tier2?.toFixed(1) ?? "0.0"}</p>
                </div>
                <div className="rounded-md bg-background/60 p-2">
                  <p className="text-[10px] text-muted-foreground">Tier 3</p>
                  <p className="text-sm font-semibold">{selected?.tier3?.toFixed(1) ?? "0.0"}</p>
                </div>
              </div>

              <div className="space-y-2 text-sm border-t border-white/5 pt-3">
                <p><span className="text-muted-foreground text-xs block">Role:</span> {selected?.current_role || "-"}</p>
                <p><span className="text-muted-foreground text-xs block">Companies:</span> {parseList(selected?.companies).join(", ") || "-"}</p>
                <p><span className="text-muted-foreground text-xs block">Submitted:</span> {selected ? new Date(selected.created_at).toLocaleString() : "-"}</p>
              </div>

              <div className="space-y-2 border-t border-white/5 pt-3">
                {selected && (
                  <Button className="w-full gap-2 text-xs" variant="outline" onClick={() => handleViewResume(selected)}>
                    <FileText className="h-4 w-4" /> View Resume Text
                  </Button>
                )}
                <DialogClose asChild>
                  <Button className="w-full text-xs" variant="ghost">Close</Button>
                </DialogClose>
              </div>
            </aside>
          </div>
        </DialogContent>
      </Dialog>

      {/* Resume viewer modal */}
      <ResumeViewer candidateId={selected?.id ?? 0} open={resumeOpen} onClose={closeResume} />
    </div>
  );
}
