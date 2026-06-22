"use client";

import React, { Suspense } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Check, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Stagger, StaggerItem } from "@/components/ui/motion";

const EASE = [0.22, 1, 0.36, 1] as const;

function SuccessContent() {
  const { jobId } = useParams<{ jobId: string }>();
  const router = useRouter();

  return (
    <section className="flex min-h-[80vh] items-center justify-center p-4">
      <motion.div
        className="glass w-full max-w-lg rounded-2xl p-8 text-center"
        initial={{ opacity: 0, y: 24, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: EASE }}
      >
        {/* Checkmark: ring pulse + spring pop + drawn tick */}
        <div className="relative mx-auto flex h-16 w-16 items-center justify-center">
          <motion.span
            className="absolute inset-0 rounded-full"
            style={{ background: "var(--strong)" }}
            initial={{ scale: 0.6, opacity: 0.5 }}
            animate={{ scale: 1.6, opacity: 0 }}
            transition={{ duration: 1.1, ease: "easeOut", delay: 0.25 }}
          />
          <motion.span
            className="relative flex h-16 w-16 items-center justify-center rounded-2xl"
            style={{ background: "var(--strong-bg)", color: "var(--strong)" }}
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 260, damping: 16, delay: 0.15 }}
          >
            <motion.svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round">
              <motion.path d="M20 6 9 17l-5-5"
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
                transition={{ duration: 0.45, ease: EASE, delay: 0.4 }} />
            </motion.svg>
          </motion.span>
        </div>

        <Stagger delay={0.45} gap={0.09}>
          <StaggerItem><h1 className="mt-5 font-display text-2xl font-bold text-heading">Application received</h1></StaggerItem>
          <StaggerItem>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Your résumé is in.{" "}
              {process.env.NEXT_PUBLIC_ORG_NAME
                ? `The ${process.env.NEXT_PUBLIC_ORG_NAME} team`
                : "Our team"}{" "}
              is reviewing applications for this role now.
            </p>
          </StaggerItem>
          <StaggerItem>
            <div className="mt-6 flex items-start gap-3 rounded-xl border border-border bg-foreground/[0.03] p-4 text-left">
              <Mail className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <p className="text-sm text-muted-foreground">
                If your profile matches, we&apos;ll email you an invitation to take the AI interview.
                No further action is needed right now.
              </p>
            </div>
          </StaggerItem>
          <StaggerItem>
            <Button onClick={() => router.push(`/applicant/${jobId}`)} className="mt-6 w-full" size="lg">
              Back to job details
            </Button>
          </StaggerItem>
        </Stagger>
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
