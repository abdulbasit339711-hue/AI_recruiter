"use client";

import React, { Suspense } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Phone, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";

function SuccessContent() {
  const { jobId } = useParams<{ jobId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("t");

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
          Your resume has been queued for review.
          {token
            ? " You can take your AI interview right now — it only takes a few minutes."
            : " Our recruiting team will follow up if your profile matches the role."}
        </p>

        {token && (
          <div className="mt-6 rounded-xl border border-primary/20 bg-primary/10 p-5">
            <p className="text-sm font-medium">Ready to start your AI interview?</p>
            <p className="mt-1 text-xs text-muted-foreground">
              You&apos;ll speak with our AI recruiter. Make sure your microphone is enabled.
            </p>
            <Link href={`/interview/${token}`}>
              <Button className="mt-4 w-full gap-2" size="lg">
                <Phone className="h-4 w-4" /> Start AI interview now
              </Button>
            </Link>
          </div>
        )}

        <Button
          onClick={() => router.push(`/applicant/${jobId}`)}
          className="mt-4 w-full"
          size="lg"
          variant={token ? "ghost" : "default"}
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
