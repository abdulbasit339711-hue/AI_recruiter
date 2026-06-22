// src/app/admin/jobs/page.tsx
"use client";

import React, { useState } from "react";
import { useJobs } from "@/hooks/useJobs";
import { useCreateJob } from "@/hooks/useCreateJob";
import { useUpdateJob } from "@/hooks/useUpdateJob";
import { useArchiveJob } from "@/hooks/useArchiveJob";
import { JobCard } from "@/components/job/JobCard";
import { JobFormModal } from "@/components/admin/JobFormModal";
import { Plus, Briefcase } from "lucide-react";
import type { Job } from "@/types";
import { useIsAdmin } from "@/hooks/useRole";

export default function AdminJobsPage() {
  const { data: jobs = [], isLoading, isError, error } = useJobs();
  const createJobMutation = useCreateJob();
  const updateJobMutation = useUpdateJob();
  const archiveJobMutation = useArchiveJob();
  const isAdmin = useIsAdmin();

  const [isModalOpen, setModalOpen] = useState(false);
  const [editingJob, setEditingJob] = useState<Job | null>(null);

  const openCreate = () => {
    setEditingJob(null);
    setModalOpen(true);
  };

  const openEdit = (job: Job) => {
    setEditingJob(job);
    setModalOpen(true);
  };

  const handleSubmit = async (
    data: {
      title: string;
      department: string;
      job_description: string;
      llm_prompt?: string;
    },
    id?: number
  ) => {
    if (id) {
      await updateJobMutation.mutateAsync({ id, ...data });
    } else {
      await createJobMutation.mutateAsync(data);
    }
  };

  const handleArchive = async (job: Job) => {
    await archiveJobMutation.mutateAsync(job.id);
  };

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
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-heading">Job Openings</h1>
        {isAdmin && (
          <button
            onClick={openCreate}
            className="flex items-center gap-2 rounded-xl bg-[#1C99BF] px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-[#3DAFCC] hover:shadow-[0_0_24px_rgba(28,153,191,0.4)]"
          >
            <Plus className="h-4 w-4" />
            Post New Job
          </button>
        )}
      </div>

      {/* ── Loading skeletons ──────────────────────────────────────────────── */}
      {isLoading && (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="animate-pulse rounded-2xl p-5"
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--surface-border)",
                backdropFilter: "blur(12px)",
              }}
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="h-10 w-10 rounded-xl bg-white/[0.06]" />
                <div className="h-5 w-16 rounded-full bg-white/[0.06]" />
              </div>
              <div className="h-4 w-40 rounded bg-white/[0.08]" />
              <div className="mt-1 h-3 w-24 rounded bg-white/[0.06]" />
              <div className="mt-1.5 h-3 w-full rounded bg-white/[0.04]" />
              <div className="mt-3 h-3 w-28 rounded bg-white/[0.06]" />
              <div className="mt-2 h-1.5 w-full rounded-full bg-white/[0.04]" />
              <div className="mt-4 flex gap-2 border-t border-white/[0.05] pt-4">
                <div className="h-8 flex-1 rounded-lg bg-white/[0.06]" />
                <div className="h-8 w-8 rounded-lg bg-white/[0.06]" />
                <div className="h-8 w-8 rounded-lg bg-white/[0.06]" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Empty state ────────────────────────────────────────────────────── */}
      {!isLoading && jobs.length === 0 && (
        <div
          className="flex flex-col items-center justify-center gap-4 rounded-2xl px-6 py-20 text-center"
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--surface-border)",
            backdropFilter: "blur(12px)",
          }}
        >
          <span
            className="flex h-14 w-14 items-center justify-center rounded-2xl"
            style={{ background: "rgba(28,153,191,0.1)", color: "#1C99BF" }}
          >
            <Briefcase className="h-6 w-6" strokeWidth={2} />
          </span>
          <div className="flex flex-col gap-1.5">
            <p className="text-sm font-semibold text-heading">
              No jobs yet — create your first opening
            </p>
            <p className="max-w-xs text-xs text-muted-foreground">
              Add a role to start accepting candidates and running AI screening.
            </p>
          </div>
          {isAdmin && (
            <button
              onClick={openCreate}
              className="flex items-center gap-2 rounded-xl bg-[#1C99BF] px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-[#3DAFCC] hover:shadow-[0_0_24px_rgba(28,153,191,0.4)]"
            >
              <Plus className="h-4 w-4" />
              Post New Job
            </button>
          )}
        </div>
      )}

      {/* ── Jobs grid ──────────────────────────────────────────────────────── */}
      {!isLoading && jobs.length > 0 && (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onEdit={isAdmin ? openEdit : undefined}
              onArchive={isAdmin ? handleArchive : undefined}
            />
          ))}
        </div>
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
