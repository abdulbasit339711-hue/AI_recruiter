"use client";

import React from "react";
import { useParams } from "next/navigation";
import { useJob } from "../../../hooks/useJob";
import Link from "next/link";
import { ArrowRight, Clock } from "lucide-react";
import { Reveal } from "@/components/ui/Reveal";

function resumeDeadlineBadge(iso: string | null | undefined) {
  if (!iso) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const d = new Date(iso);
  const diff = Math.ceil((d.getTime() - today.getTime()) / 86_400_000);
  const fmt = (dt: Date) => dt.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
  if (diff < 0)   return { text: `Applications closed on ${fmt(d)}`, color: "#9ca3af" };
  if (diff === 0) return { text: "Applications close today",         color: "#f59e0b" };
  if (diff <= 7)  return { text: `Applications close ${fmt(d)} — ${diff} day${diff !== 1 ? "s" : ""} left`, color: "#f59e0b" };
  return           { text: `Apply by ${fmt(d)}`,                     color: "#6b7280" };
}

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const numericId = Number(jobId);
  const { data: job, isLoading, isError, error } = useJob(numericId);

  if (isLoading) {
    return (
      <section className="mx-auto max-w-3xl p-4 py-8">
        <div className="h-64 animate-pulse glass rounded-2xl" />
      </section>
    );
  }

  if (isError || !job) {
    return (
      <div className="p-4 text-center text-weak">
        Failed to load job details: {error instanceof Error ? error.message : "Unknown error"}
      </div>
    );
  }

  return (
    <section className="mx-auto max-w-3xl space-y-5 p-4 py-8">
      <Reveal>
        <div className="glass rounded-2xl p-7">
          <p className="font-mono text-xs uppercase tracking-[0.06em] text-muted-foreground">{job.department}</p>
          <h1 className="mt-2 font-display text-[34px] font-bold leading-tight tracking-tight text-heading">{job.title}</h1>
          {(() => {
            const dl = resumeDeadlineBadge(job.resume_deadline);
            if (!dl) return null;
            return (
              <p className="mt-3 flex items-center gap-1.5 text-sm" style={{ color: dl.color }}>
                <Clock className="h-4 w-4 shrink-0" />
                {dl.text}
              </p>
            );
          })()}
        </div>
      </Reveal>
      <Reveal index={1}>
        <div className="glass whitespace-pre-wrap rounded-2xl p-7 text-sm leading-7 text-muted-foreground">
          {job.job_description}
        </div>
      </Reveal>
      <Reveal index={2}>
        <Link
          href={`/applicant/${job.id}/apply`}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3.5 font-semibold text-primary-foreground shadow-[0_12px_28px_-10px_var(--primary)] transition hover:opacity-90"
        >
          Apply now <ArrowRight className="h-4 w-4" />
        </Link>
      </Reveal>
    </section>
  );
}
