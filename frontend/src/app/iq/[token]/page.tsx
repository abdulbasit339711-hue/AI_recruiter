"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CheckCircle2, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { IqTest } from "@/components/applicant/IqTest";
import type { IqSubmitResponse } from "@/types";

type Info = { job_id: number; job_title: string; candidate_name: string | null; already_taken: boolean };

/** Standalone IQ test reached from an HR-sent link (the candidate has already applied). */
export default function IqInvitePage() {
  const { token } = useParams<{ token: string }>();
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    api.getIqInvite(token).then(setInfo).catch((e) => setError(e?.message || "This link is invalid or has expired."));
  }, [token]);

  const onComplete = async (result: IqSubmitResponse | null) => {
    if (!result) {
      setError("The test could not be completed. Please try the link again.");
      return;
    }
    try {
      await api.attachIqInvite(token, result.result_token);
      setDone(true);
    } catch (e) {
      setError((e as Error).message || "Could not record your result.");
    }
  };

  return (
    <section className="mx-auto max-w-xl space-y-6 p-4 py-8">
      {error ? (
        <p className="rounded-xl border p-3 text-sm" style={{ borderColor: "var(--weak)", background: "var(--weak-bg)", color: "var(--weak-text)" }}>{error}</p>
      ) : !info ? (
        <Loader2 className="mx-auto h-6 w-6 animate-spin text-primary" />
      ) : info.already_taken || done ? (
        <div className="glass rounded-2xl p-6 text-center">
          <CheckCircle2 className="mx-auto h-8 w-8 text-primary" />
          <h1 className="mt-3 text-xl font-semibold text-heading">{done ? "Thank you!" : "Already completed"}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {done ? "Your aptitude test has been recorded. The team will be in touch." : "You have already taken this test."}
          </p>
        </div>
      ) : (
        <>
          <div>
            <h1 className="font-display text-[26px] font-bold text-heading">Aptitude test — {info.job_title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {info.candidate_name ? `Hi ${info.candidate_name}. ` : ""}This is timed and can only be taken once.
            </p>
          </div>
          <IqTest jobId={info.job_id} onComplete={onComplete} />
        </>
      )}
    </section>
  );
}
