"use client";

import React from "react";
import { useParams } from "next/navigation";
import { useJob } from "../../../hooks/useJob";
import Link from "next/link";

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const numericId = Number(jobId);
  const { data: job, isLoading, isError, error } = useJob(numericId);

  if (isLoading) {
    return (
      <section className="mx-auto max-w-3xl p-4 py-8">
        <div className="h-64 animate-pulse rounded-md border border-white/10 bg-card/80" />
      </section>
    );
  }

  if (isError || !job) {
    return (
      <div className="p-4 text-center text-red-300">
        Failed to load job details: {error instanceof Error ? error.message : "Unknown error"}
      </div>
    );
  }

  return (
    <section className="mx-auto max-w-3xl space-y-6 p-4 py-8">
      <div className="rounded-md border border-white/10 bg-card/80 p-6">
        <p className="text-sm text-muted-foreground">{job.department}</p>
        <h1 className="mt-2 text-3xl font-semibold">{job.title}</h1>
      </div>
      <div className="whitespace-pre-wrap rounded-md border border-white/10 bg-card/80 p-6 text-sm leading-7 text-muted-foreground">
        {job.job_description}
      </div>
      <Link href={`/applicant/${job.id}/apply`}>
        <button className="w-full rounded-md bg-primary px-4 py-2 text-primary-foreground hover:opacity-90">
          Apply Now
        </button>
      </Link>
    </section>
  );
}
