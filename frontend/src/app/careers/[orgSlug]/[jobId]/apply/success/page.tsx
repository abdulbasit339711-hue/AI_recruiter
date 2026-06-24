"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { Stagger, StaggerItem } from "@/components/ui/motion";
import { api } from "@/lib/api";
import type { Org } from "@/types";

const EASE = [0.22, 1, 0.36, 1] as const;
const POLL_MS = 2500;
const TIMEOUT_MS = 90_000;

function SuccessContent() {
  const { orgSlug, jobId } = useParams<{ orgSlug: string; jobId: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const cid = searchParams.get("cid");

  const { data: org } = useQuery<Org>({
    queryKey: ["orgs", orgSlug],
    queryFn: () => api.getOrgBySlug(orgSlug),
    staleTime: 60_000,
    enabled: !!orgSlug,
  });

  const orgName = org?.name || orgSlug;
  const color = org?.primary_color || "#1C99BF";

  const [done, setDone] = useState(!cid);
  const startedAt = useRef(Date.now());
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!cid) return;
    let cancelled = false;

    async function poll() {
      if (cancelled) return;
      try {
        const res = await api.pollCandidateStatus(Number(cid));
        if (cancelled) return;
        if (res.terminal) {
          if (res.qualified && res.availability_token) {
            router.push(`/availability/${res.availability_token}`);
            return;
          }
          setDone(true);
          return;
        }
      } catch {
        // keep polling on transient network errors
      }
      if (Date.now() - startedAt.current > TIMEOUT_MS) {
        setDone(true);
        return;
      }
      if (!cancelled) timer.current = setTimeout(poll, POLL_MS);
    }

    poll();
    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [cid, router]);

  if (!done) {
    return (
      <section className="flex min-h-[80vh] items-center justify-center p-4">
        <div
          className="w-full max-w-lg rounded-2xl p-10 text-center"
          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
        >
          <div
            className="mx-auto flex h-12 w-12 animate-spin items-center justify-center rounded-full border-2"
            style={{ borderColor: `${color}40`, borderTopColor: color }}
          />
          <Loader2 className="mx-auto mt-4 h-0 w-0" />
          <h1 className="mt-5 text-xl font-semibold text-white">Evaluating your résumé…</h1>
          <p className="mt-2 text-sm text-gray-400">This takes about 30 seconds. Please stay on this page.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="flex min-h-[80vh] items-center justify-center p-4">
      <motion.div
        className="w-full max-w-lg rounded-2xl p-8 text-center"
        style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
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
            <h1 className="mt-5 text-2xl font-semibold text-white">Application received</h1>
          </StaggerItem>
          <StaggerItem>
            <p className="mt-3 text-sm leading-6 text-gray-400">
              Thank you for applying to {orgName}. Our team will review your application and be in touch soon.
            </p>
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
