"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getJobEventsUrl } from "@/lib/api";
import type { CandidateSSEPayload } from "@/types";

/**
 * Admin: subscribe to all candidate updates for a job.
 * Invalidates candidates list when any applicant finishes evaluation.
 */
export function useJobEvaluationEvents(jobId: number | null | undefined) {
  const queryClient = useQueryClient();
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId || jobId <= 0) return;

    const es = new EventSource(getJobEventsUrl(jobId));
    esRef.current = es;

    es.addEventListener("evaluation_update", (ev) => {
      try {
        const data = JSON.parse(ev.data) as CandidateSSEPayload;
        if (data.terminal) {
          queryClient.invalidateQueries({ queryKey: ["candidates", jobId] });
          if (data.candidate_id) {
            queryClient.invalidateQueries({
              queryKey: ["candidate", data.candidate_id],
            });
          }
        }
      } catch {
        /* ignore parse errors */
      }
    });

    es.onerror = () => es.close();

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [jobId, queryClient]);
}
