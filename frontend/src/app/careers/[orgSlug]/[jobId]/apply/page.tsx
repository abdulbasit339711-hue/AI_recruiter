"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Loader2, FileText, UploadCloud, CheckCircle2 } from "lucide-react";
import { useJob } from "@/hooks/useJob";
import { useUploadResume } from "@/hooks/useUploadResume";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Org } from "@/types";
import { IqTest } from "@/components/applicant/IqTest";
import { Button } from "@/components/ui/button";
import { Swap } from "@/components/ui/motion";
import { formatDuration } from "@/lib/utils";
import type { IqSubmitResponse } from "@/types";

type Step = "iq" | "upload";

export default function CareersApplyPage() {
  const { orgSlug, jobId } = useParams<{ orgSlug: string; jobId: string }>();
  const numericId = Number(jobId);
  const router = useRouter();

  const { data: job, isLoading, isError } = useJob(numericId);
  const { data: org } = useQuery<Org>({
    queryKey: ["orgs", orgSlug],
    queryFn: () => api.getOrgBySlug(orgSlug),
    staleTime: 60_000,
    enabled: !!orgSlug,
  });
  const color = org?.primary_color || "#1C99BF";
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
      router.push(`/careers/${orgSlug}/${jobId}/apply/success`);
    } catch {
      /* error shown below */
    }
  };

  if (isLoading) return <div className="mx-auto mt-8 h-48 max-w-xl animate-pulse glass rounded-2xl" />;
  if (isError || !job) return <p className="p-8 text-weak">Could not load job.</p>;

  return (
    <section className="mx-auto max-w-xl space-y-6 p-4 py-8">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.06em] text-muted-foreground">{job.department}</p>
        <h1 className="mt-2 font-display text-[28px] font-bold leading-tight tracking-tight text-heading">
          Apply for {job.title}
        </h1>
        <div className="mt-4 flex items-center gap-2.5">
          {[
            { key: "iq", label: "Aptitude screen" },
            { key: "upload", label: "Résumé upload" },
          ].map((s, i) => {
            const active = s.key === step;
            const done = step === "upload" && s.key === "iq";
            return (
              <React.Fragment key={s.key}>
                <div className="flex items-center gap-2">
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full font-mono text-xs font-semibold ${
                      active || done ? "text-white" : "border border-border text-muted-foreground"
                    }`}
                    style={active || done ? { background: color } : undefined}
                  >
                    {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : i + 1}
                  </span>
                  <span className={`text-sm ${active ? "font-semibold text-heading" : "text-muted-foreground"}`}>
                    {s.label}
                  </span>
                </div>
                {i === 0 && <div className="h-px w-6 bg-border" />}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      <Swap k={step === "iq" ? "iq" : upload.isPending ? "loading" : "upload"}>
        {step === "iq" ? (
          <IqTest jobId={numericId} onComplete={onIqComplete} />
        ) : upload.isPending ? (
          <UploadingLoader fileName={file?.name} />
        ) : (
          <form onSubmit={onSubmit} className="space-y-4 glass rounded-2xl p-5">
            {iq && (
              <div className="flex items-center gap-3 rounded-xl border p-3 text-sm" style={{ borderColor: `${color}60`, background: `${color}12`, color }}>
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                Aptitude screen complete — {iq.correct}/{iq.total} correct, scored {Math.round(iq.score)}% in {formatDuration(iq.time_seconds)}.
              </div>
            )}
            <label className="block">
              <span className="text-sm font-medium text-heading">Résumé (PDF, max 5MB)</span>
              <div className="relative mt-2 flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border bg-foreground/[0.03] px-4 py-8 text-center transition-colors hover:border-primary/50 focus-within:border-primary/60">
                <UploadCloud className="h-7 w-7" style={{ color }} />
                <p className="text-sm text-foreground">{file ? file.name : "Drag your PDF here, or click to browse"}</p>
                {!file && <p className="text-xs text-muted-foreground">PDF only, up to 5MB.</p>}
                <input
                  type="file"
                  accept=".pdf,application/pdf"
                  className="absolute inset-0 cursor-pointer opacity-0"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
            </label>
            {upload.isError && (
              <p className="rounded-xl border p-3 text-sm" style={{ borderColor: "var(--weak)", background: "var(--weak-bg)", color: "var(--weak-text)" }}>
                {upload.error?.message || "Upload failed"}
              </p>
            )}
            <button
              type="submit"
              className="w-full rounded-xl px-4 py-3.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
              style={{ background: color }}
              disabled={!file}
            >
              Submit application
            </button>
          </form>
        )}
      </Swap>
    </section>
  );
}

function UploadingLoader({ fileName }: { fileName?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-5 glass rounded-2xl p-10 text-center">
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
        <p className="mt-2 text-sm text-muted-foreground">Please don&apos;t close this window.</p>
      </div>
      <div className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-foreground/10">
        <div className="h-full w-1/3 animate-[loading_1.2s_ease-in-out_infinite] rounded-full bg-primary" />
      </div>
    </div>
  );
}
