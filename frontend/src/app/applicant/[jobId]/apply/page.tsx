"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Loader2, FileText, UploadCloud, CheckCircle2 } from "lucide-react";
import { useJob } from "@/hooks/useJob";
import { useUploadResume } from "@/hooks/useUploadResume";
import { IqTest } from "@/components/applicant/IqTest";
import { Button } from "@/components/ui/button";
import type { IqSubmitResponse } from "@/types";

type Step = "iq" | "upload";

export default function ApplyPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const numericId = Number(jobId);
  const router = useRouter();
  const { data: job, isLoading, isError } = useJob(numericId);
  const upload = useUploadResume(numericId);
  const [file, setFile] = useState<File | null>(null);
  const [step, setStep] = useState<Step>("iq");
  const [iq, setIq] = useState<IqSubmitResponse | null>(null);

  const onIqComplete = (result: IqSubmitResponse | null) => {
    setIq(result);
    setStep("upload");
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    try {
      await upload.mutateAsync({ file, iqToken: iq?.result_token });
      router.push(`/applicant/${jobId}/apply/success`);
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
        <p className="mt-1 text-xs text-muted-foreground">
          Step {step === "iq" ? "1" : "2"} of 2 — {step === "iq" ? "aptitude screen" : "résumé upload"}
        </p>
      </div>

      {step === "iq" ? (
        <IqTest jobId={numericId} onComplete={onIqComplete} />
      ) : upload.isPending ? (
        <UploadingLoader fileName={file?.name} />
      ) : (
        <form onSubmit={onSubmit} className="space-y-4 rounded-md border border-white/10 bg-card/80 p-5">
          {iq && (
            <div className="flex items-center gap-2 rounded-md border border-emerald-400/20 bg-emerald-400/10 p-3 text-sm text-emerald-200">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              Aptitude screen complete — {iq.correct}/{iq.total} correct ({Math.round(iq.score)}%).
            </div>
          )}

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

          <Button type="submit" className="w-full" size="lg" disabled={!file}>
            Submit application
          </Button>
        </form>
      )}
    </section>
  );
}

/** Animated loader shown while the resume is being uploaded & queued. */
function UploadingLoader({ fileName }: { fileName?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-5 rounded-md border border-white/10 bg-card/80 p-10 text-center">
      {/* Pulsing ring + spinner with a document icon at the center */}
      <div className="relative flex h-20 w-20 items-center justify-center">
        <span className="absolute inset-0 animate-ping rounded-full bg-primary/20" />
        <span className="absolute inset-2 rounded-full bg-primary/10" />
        <Loader2 className="absolute h-20 w-20 animate-spin text-primary/70" strokeWidth={1.25} />
        <FileText className="relative h-7 w-7 text-primary" />
      </div>

      <div>
        <p className="flex items-center justify-center gap-2 text-base font-medium">
          <UploadCloud className="h-4 w-4 text-primary" /> Uploading your resume…
        </p>
        {fileName && <p className="mt-1 truncate text-xs text-muted-foreground">{fileName}</p>}
        <p className="mt-2 text-sm text-muted-foreground">
          Please don&apos;t close this window — this only takes a moment.
        </p>
      </div>

      {/* Indeterminate progress bar */}
      <div className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-white/10">
        <div className="h-full w-1/3 animate-[loading_1.2s_ease-in-out_infinite] rounded-full bg-primary" />
      </div>
    </div>
  );
}
