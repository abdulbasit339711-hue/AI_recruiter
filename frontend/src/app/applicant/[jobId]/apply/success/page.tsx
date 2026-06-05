"use client";

import React, { Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { useCandidateEvaluation } from "@/hooks/useCandidateEvaluation";

function SuccessContent() {
  const { jobId } = useParams<{ jobId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const candidateId = Number(searchParams.get("candidateId"));
  const evaluation = useCandidateEvaluation(candidateId > 0 ? candidateId : null);

  return (
    <section className="flex min-h-screen items-center justify-center bg-mesh p-4">
      <motion.div
        className="w-full max-w-lg rounded-md border border-white/10 bg-card/90 p-8 text-center shadow-xl"
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
      >
        <h1 className="text-2xl font-semibold">Application received</h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Your resume has been queued for review. Our recruiting team will follow up if your profile matches the role.
        </p>

        {candidateId > 0 && !evaluation.isComplete && (
          <div className="mt-6 rounded-md border border-white/10 bg-background/60 p-4">
            <p className="text-sm text-muted-foreground">Current status</p>
            <p className="mt-1 text-base font-medium">{evaluation.status ?? "Queued"}</p>
            <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-muted">
              <motion.div
                className="h-full bg-primary"
                initial={{ width: "12%" }}
                animate={{ width: "85%" }}
                transition={{ repeat: Infinity, duration: 1.5, repeatType: "reverse" }}
              />
            </div>
          </div>
        )}

        {evaluation.isComplete && (
          <div className="mt-6 rounded-md border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm text-emerald-200">
            Screening received. Your application is now with the recruiting team.
          </div>
        )}

        {evaluation.error && (
          <p className="mt-4 text-sm text-amber-200">{evaluation.error}</p>
        )}

        <Button onClick={() => router.push(`/applicant/${jobId}`)} className="mt-6 w-full" size="lg">
          Back to job details
        </Button>
      </motion.div>
    </section>
  );
}

export default function UploadSuccessPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center">Loading...</div>}>
      <SuccessContent />
    </Suspense>
  );
}
