// src/components/job/JobCard.tsx
"use client";
import React from "react";
import Link from "next/link";
import { Briefcase } from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { Job } from "@/types";

interface JobCardProps {
  job: Job;
  candidateCount?: number;
  onEdit?: (job: Job) => void;
  onArchive?: (job: Job) => void;
}

function StatusChip({ status }: { status: Job["status"] }) {
  const isActive = status === "Active";
  return (
    <span
      className={[
        "rounded-full px-2.5 py-1 text-xs font-medium leading-none",
        isActive
          ? "bg-primary/15 text-primary"
          : "bg-foreground/10 text-muted-foreground",
      ].join(" ")}
    >
      {status}
    </span>
  );
}

export const JobCard: React.FC<JobCardProps> = ({
  job,
  candidateCount,
  onEdit,
  onArchive,
}) => {
  const createdDate = new Date(job.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <GlassCard
      variant="tile"
      hover
      className="ozi-glow flex flex-col gap-0 rounded-2xl p-5 transition-all duration-200"
    >
      {/* Top row: title + status */}
      <div className="flex items-start justify-between gap-3">
        <h3 className="flex-1 text-base font-semibold leading-snug text-heading">
          {job.title}
        </h3>
        <StatusChip status={job.status} />
      </div>

      {/* Department */}
      <div className="mt-1 flex items-center gap-1.5">
        <Briefcase className="h-3 w-3 shrink-0 text-muted-foreground" strokeWidth={2} />
        <p className="text-xs text-muted-foreground">{job.department}</p>
      </div>

      {/* Divider */}
      <div className="my-3 border-t border-border" />

      {/* Stats row */}
      <div className="flex items-end gap-6">
        <div className="flex flex-col gap-0.5">
          <span className="font-mono text-2xl font-bold leading-none text-heading tabular-nums">
            {candidateCount != null ? candidateCount : "—"}
          </span>
          <span className="text-xs text-muted-foreground">candidates</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-muted-foreground">Created</span>
          <span className="font-mono text-xs text-muted-foreground tabular-nums">
            {createdDate}
          </span>
        </div>
      </div>

      {/* Divider */}
      <div className="my-3 border-t border-border" />

      {/* Action buttons */}
      <div className="flex items-center gap-2">
        <Link
          href={`/admin/jobs/${job.id}/candidates`}
          className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-[#3DAFCC]"
        >
          View Candidates
        </Link>
        {onEdit && (
          <button
            type="button"
            onClick={() => onEdit(job)}
            className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-heading transition-colors hover:bg-foreground/[0.06]"
          >
            Edit
          </button>
        )}
        {onArchive && job.status !== "Archived" && (
          <button
            type="button"
            onClick={() => onArchive(job)}
            className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-weak transition-colors hover:bg-weak/10"
          >
            Archive
          </button>
        )}
      </div>
    </GlassCard>
  );
};
