"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getJobEventsUrl } from "@/lib/api";
import { openReconnectingSSE } from "@/lib/sse";
import type { CandidateSSEPayload } from "@/types";

/**
 * Admin: subscribe to all candidate updates for a job.
 * Invalidates candidates list when any applicant finishes evaluation.
 */
export function useJobEvaluationEvents(jobId: number | null | undefined) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!jobId || jobId <= 0) return;

    const handle = openReconnectingSSE(() => getJobEventsUrl(jobId), {
      setup: (es) => {
        es.addEventListener("evaluation_update", (ev) => {
          try {
            const data = JSON.parse((ev as MessageEvent).data) as CandidateSSEPayload;
            if (data.terminal) {
              queryClient.invalidateQueries({ queryKey: ["candidates", jobId] });
              if (data.candidate_id) {
                queryClient.invalidateQueries({ queryKey: ["candidate", data.candidate_id] });
              }
            }
          } catch {
            /* ignore parse errors */
          }
        });
      },
    });

    return () => handle.close();
  }, [jobId, queryClient]);
}
