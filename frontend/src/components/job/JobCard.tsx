// src/components/job/JobCard.tsx
"use client";

import React from "react";
import Link from "next/link";
import { Briefcase, Users, Archive, Edit } from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import type { Job } from "@/types";

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
      className="rounded-full px-2.5 py-1 text-xs font-medium leading-none"
      style={
        isActive
          ? {
              background: "rgba(28,153,191,0.15)",
              color: "#1C99BF",
              border: "1px solid rgba(28,153,191,0.3)",
            }
          : {
              background: "rgba(85,96,112,0.15)",
              color: "#556070",
              border: "1px solid rgba(85,96,112,0.3)",
            }
      }
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
  const snippet = (job.job_description ?? "").slice(0, 160);

  return (
    <GlassCard
      variant="tile"
      hover
      className="flex flex-col p-5 transition-all duration-200"
    >
      {/* Top: icon + status */}
      <div className="mb-3 flex items-start justify-between">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-xl"
          style={{ background: "rgba(28,153,191,0.1)", color: "#1C99BF" }}
        >
          <Briefcase className="h-5 w-5" strokeWidth={2} />
        </div>
        <StatusChip status={job.status} />
      </div>

      {/* Title */}
      <h3 className="text-base font-semibold leading-snug text-heading">
        {job.title}
      </h3>

      {/* Department */}
      <p className="text-xs text-muted-foreground">{job.department}</p>

      {/* Description snippet */}
      {snippet && (
        <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground/60">
          {snippet}
        </p>
      )}

      {/* Stats row */}
      <div className="mt-3 flex items-center gap-3">
        <Users className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">
          {candidateCount != null ? candidateCount : "—"} candidates
        </span>
      </div>

      {/* Mini score bar */}
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.04]">
        <div className="flex h-full w-full">
          {/* weak 25% */}
          <div
            className="h-full"
            style={{ width: "25%", background: "#F25C7C" }}
          />
          {/* promising 45% */}
          <div
            className="h-full"
            style={{ width: "45%", background: "#F5B544" }}
          />
          {/* strong 30% */}
          <div
            className="h-full"
            style={{ width: "30%", background: "#34C28A" }}
          />
        </div>
      </div>
      <div className="flex justify-between text-[9px] text-muted-foreground/40">
        <span>0</span>
        <span>50</span>
        <span>100</span>
      </div>

      {/* Bottom actions */}
      <div className="mt-4 flex gap-2 border-t border-white/[0.05] pt-4">
        <Link
          href={`/admin/candidates?job=${job.id}`}
          className="flex-1 rounded-lg border border-white/[0.06] bg-white/[0.02] py-2 text-center text-xs text-muted-foreground transition-colors hover:border-[#1C99BF]/30 hover:text-[#1C99BF]"
        >
          View candidates
        </Link>

        {onEdit && (
          <button
            type="button"
            onClick={() => onEdit(job)}
            className="rounded-lg border border-white/[0.06] p-2 text-muted-foreground transition-colors hover:border-[#1C99BF]/30 hover:text-[#1C99BF]"
            title="Edit job"
          >
            <Edit className="h-4 w-4" />
          </button>
        )}

        {onArchive && job.status !== "Archived" && (
          <button
            type="button"
            onClick={() => onArchive(job)}
            className="rounded-lg border border-white/[0.06] p-2 text-muted-foreground transition-colors hover:border-[#F25C7C]/30 hover:text-[#F25C7C]"
            title="Archive job"
          >
            <Archive className="h-4 w-4" />
          </button>
        )}
      </div>
    </GlassCard>
  );
};
