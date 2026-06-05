"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useJob } from "@/hooks/useJob";
import { useUploadResume } from "@/hooks/useUploadResume";
import { Button } from "@/components/ui/button";

export default function ApplyPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const numericId = Number(jobId);
  const router = useRouter();
  const { data: job, isLoading, isError } = useJob(numericId);
  const upload = useUploadResume(numericId);
  const [file, setFile] = useState<File | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    try {
      const result = await upload.mutateAsync(file);
      router.push(`/applicant/${jobId}/apply/success?candidateId=${result.id}`);
    } catch {
      /* error shown below */
    }
  };

  if (isLoading) {
    return <div className="mx-auto mt-8 h-48 max-w-xl animate-pulse rounded-md border border-white/10 bg-card/80" />;
  }

  if (isError || !job) {
    return <p className="p-8 text-red-300">Could not load job.</p>;
  }

  return (
    <section className="mx-auto max-w-xl space-y-6 p-4 py-8">
      <div>
        <p className="text-sm text-muted-foreground">{job.department}</p>
        <h1 className="mt-2 text-2xl font-semibold">Apply for {job.title}</h1>
      </div>

      <form onSubmit={onSubmit} className="space-y-4 rounded-md border border-white/10 bg-card/80 p-5">
        <label className="block">
          <span className="text-sm font-medium">Resume (PDF, max 5MB)</span>
          <input
            type="file"
            accept=".pdf,application/pdf"
            className="mt-2 block w-full rounded-md border border-white/10 bg-background p-3 text-sm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>

        {upload.isError && (
          <p className="rounded-md border border-red-400/20 bg-red-400/10 p-3 text-sm text-red-200">
            {upload.error?.message || "Upload failed"}
          </p>
        )}

        <Button type="submit" className="w-full" size="lg" disabled={!file || upload.isPending}>
          {upload.isPending ? "Uploading..." : "Submit application"}
        </Button>
      </form>
    </section>
  );
}
