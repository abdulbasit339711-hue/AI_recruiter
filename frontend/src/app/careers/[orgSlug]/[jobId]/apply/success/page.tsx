"use client";

import React, { Suspense } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Check, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Stagger, StaggerItem } from "@/components/ui/motion";
import { api } from "@/lib/api";
import type { Org } from "@/types";

const EASE = [0.22, 1, 0.36, 1] as const;

function SuccessContent() {
  const { orgSlug, jobId } = useParams<{ orgSlug: string; jobId: string }>();
  const router = useRouter();

  const { data: org } = useQuery<Org>({
    queryKey: ["orgs", orgSlug],
    queryFn: () => api.getOrgBySlug(orgSlug),
    staleTime: 60_000,
    enabled: !!orgSlug,
  });

  const orgName = org?.name || orgSlug;
  const color = org?.primary_color || "#1C99BF";

  return (
    <section className="flex min-h-[80vh] items-center justify-center p-4">
      <motion.div
        className="glass w-full max-w-lg rounded-2xl p-8 text-center"
        initial={{ opacity: 0, y: 24, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: EASE }}
      >
        <div className="relative mx-auto flex h-16 w-16 items-center justify-center">
          <motion.span
            className="absolute inset-0 rounded-full"
            style={{ background: color }}
            initial={{ scale: 0.6, opacity: 0.5 }}
            animate={{ scale: 1.6, opacity: 0 }}
            transition={{ duration: 1.1, ease: "easeOut", delay: 0.25 }}
          />
          <motion.span
            className="relative flex h-16 w-16 items-center justify-center rounded-2xl"
            style={{ background: `${color}22`, color }}
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 260, damping: 16, delay: 0.15 }}
          >
            <motion.svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round">
              <motion.path
                d="M20 6 9 17l-5-5"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.45, ease: EASE, delay: 0.4 }}
              />
            </motion.svg>
          </motion.span>
        </div>

        <Stagger delay={0.45} gap={0.09}>
          <StaggerItem>
            <h1 className="mt-5 font-display text-2xl font-bold text-heading">Application received</h1>
          </StaggerItem>
          <StaggerItem>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Your résumé is in. The {orgName} team is reviewing applications for this role now.
            </p>
          </StaggerItem>
          <StaggerItem>
            <div className="mt-6 flex items-start gap-3 rounded-xl border border-border bg-foreground/[0.03] p-4 text-left">
              <Mail className="mt-0.5 h-5 w-5 shrink-0" style={{ color }} />
              <p className="text-sm text-muted-foreground">
                If your profile matches, we&apos;ll email you an invitation to take the AI interview.
                No further action is needed right now.
              </p>
            </div>
          </StaggerItem>
          <StaggerItem>
            <button
              onClick={() => router.push(`/careers/${orgSlug}/${jobId}`)}
              className="mt-6 w-full rounded-xl px-4 py-3.5 text-sm font-semibold text-white transition hover:opacity-90"
              style={{ background: color }}
            >
              Back to job details
            </button>
          </StaggerItem>
        </Stagger>
      </motion.div>
    </section>
  );
}

export default function CareersSuccessPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center">Loading...</div>}>
      <SuccessContent />
    </Suspense>
  );
}
