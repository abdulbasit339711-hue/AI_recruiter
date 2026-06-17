// src/components/job/JobCard.tsx
"use client";
import React from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { Job } from "@/types";

interface JobCardProps {
  job: Job;
}

export const JobCard: React.FC<JobCardProps> = ({ job }) => {
  return (
    <Link href={`/applicant/${job.id}`} className="group block h-full">
      <GlassCard variant="tile" hover className="flex h-full flex-col gap-4 p-6">
        <div className="flex items-start justify-between gap-3">
          <p className="font-mono text-xs uppercase tracking-[0.06em] text-muted-foreground">
            {job.department}
          </p>
          <StatusBadge status={job.status} />
        </div>
        <h3 className="font-display text-xl font-bold leading-tight text-heading">{job.title}</h3>
        <p className="line-clamp-3 flex-1 text-sm text-muted-foreground" title={job.job_description}>
          {job.job_description}
        </p>
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-primary-strong">
          View role
          <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
        </span>
      </GlassCard>
    </Link>
  );
};
