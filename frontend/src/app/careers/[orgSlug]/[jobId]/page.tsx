"use client";

import React from "react";
import { useParams } from "next/navigation";
import { useJob } from "@/hooks/useJob";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import Link from "next/link";
import { ArrowRight, ArrowLeft } from "lucide-react";
import { Reveal } from "@/components/ui/Reveal";
import type { Org } from "@/types";

export default function CareersJobDetailPage() {
  const { orgSlug, jobId } = useParams<{ orgSlug: string; jobId: string }>();
  const numericId = Number(jobId);

  const { data: job, isLoading, isError, error } = useJob(numericId);
  const { data: org } = useQuery<Org>({
    queryKey: ["orgs", orgSlug],
    queryFn: () => api.getOrgBySlug(orgSlug),
    staleTime: 60_000,
    enabled: !!orgSlug,
  });

  const color = org?.primary_color || "#1C99BF";

  if (isLoading) {
    return (
      <section className="mx-auto max-w-3xl p-4 py-8 space-y-4">
        <div className="h-8 w-32 animate-pulse glass rounded-xl" />
        <div className="h-64 animate-pulse glass rounded-2xl" />
      </section>
    );
  }

  if (isError || !job) {
    return <p className="p-8 text-center text-weak">Failed to load job details: {error instanceof Error ? error.message : "Unknown error"}</p>;
  }

  return (
    <section className="mx-auto max-w-3xl space-y-5 p-4 py-8">
      <Reveal>
        <Link
          href={`/careers/${orgSlug}`}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> All openings
        </Link>
      </Reveal>
      <Reveal index={1}>
        <div className="glass rounded-2xl p-7">
          <span
            className="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
            style={{ background: `${color}18`, color, border: `1px solid ${color}30` }}
          >
            {job.department}
          </span>
          <h1 className="mt-3 font-display text-[34px] font-bold leading-tight tracking-tight text-heading">
            {job.title}
          </h1>
        </div>
      </Reveal>
      <Reveal index={2}>
        <div className="glass whitespace-pre-wrap rounded-2xl p-7 text-sm leading-7 text-muted-foreground">
          {job.job_description}
        </div>
      </Reveal>
      <Reveal index={3}>
        <Link
          href={`/careers/${orgSlug}/${job.id}/apply`}
          className="flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3.5 font-semibold text-white shadow-lg transition hover:opacity-90"
          style={{ background: color, boxShadow: `0 12px 28px -10px ${color}80` }}
        >
          Apply now <ArrowRight className="h-4 w-4" />
        </Link>
      </Reveal>
    </section>
  );
}
