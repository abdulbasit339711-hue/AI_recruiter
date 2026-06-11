"use client";

import React, { Suspense } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { CheckCircle2, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";

function SuccessContent() {
  const { jobId } = useParams<{ jobId: string }>();
  const router = useRouter();

  return (
    <section className="flex min-h-[80vh] items-center justify-center p-4">
      <motion.div
        className="w-full max-w-lg rounded-2xl border border-white/10 bg-card/90 p-8 text-center shadow-xl"
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
      >
        <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-400" />
        <h1 className="mt-4 text-2xl font-semibold">Application received</h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Thanks for applying! Your resume has been received and is being reviewed by our team.
        </p>

        <div className="mt-6 flex items-start gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-4 text-left">
          <Mail className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <p className="text-sm text-muted-foreground">
            If your profile matches the role, our recruiting team will email you an invitation to
            take the AI interview. No further action is needed right now.
          </p>
        </div>

        <Button
          onClick={() => router.push(`/applicant/${jobId}`)}
          className="mt-6 w-full"
          size="lg"
        >
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
