"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getCandidateEventsUrl } from "@/lib/api";
import { openReconnectingSSE } from "@/lib/sse";
import type { CandidateSSEPayload, CandidateStatus } from "@/types";
import { isTerminalStatus } from "@/types";

interface UseCandidateEvaluationOptions {
  /** Fetch full candidate record (scores, summary) when evaluation completes */
  onTerminal?: (candidateId: number, status: CandidateStatus) => void;
}

/**
 * Subscribes to SSE for one applicant/candidate.
 * On terminal event, invalidates React Query cache so useCandidate refetches scores.
 */
export function useCandidateEvaluation(
  candidateId: number | null | undefined,
  options: UseCandidateEvaluationOptions = {}
) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<CandidateStatus | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const onTerminalRef = useRef(options.onTerminal);
  onTerminalRef.current = options.onTerminal;

  const handlePayload = useCallback(
    (payload: CandidateSSEPayload) => {
      setStatus(payload.status);
      if (payload.terminal || isTerminalStatus(payload.status)) {
        setIsComplete(true);
        if (candidateId) {
          queryClient.invalidateQueries({ queryKey: ["candidate", candidateId] });
          onTerminalRef.current?.(candidateId, payload.status);
        }
      }
    },
    [candidateId, queryClient]
  );

  useEffect(() => {
    if (!candidateId || candidateId <= 0) return;

    setError(null);
    setIsComplete(false);
    setIsConnected(false);

    const handle = openReconnectingSSE(() => getCandidateEventsUrl(candidateId), {
      // Transient drops auto-reconnect; we only flip the connected flag (no hard error).
      onError: () => setIsConnected(false),
      setup: (es, done) => {
        es.addEventListener("connected", () => setIsConnected(true));

        es.addEventListener("evaluation_update", (ev) => {
          try {
            handlePayload(JSON.parse((ev as MessageEvent).data) as CandidateSSEPayload);
          } catch {
            setError("Failed to parse evaluation event");
          }
        });

        es.addEventListener("evaluation_complete", (ev) => {
          try {
            const data = JSON.parse((ev as MessageEvent).data) as {
              candidate_id: number;
              status: CandidateStatus;
            };
            setStatus(data.status);
            setIsComplete(true);
            queryClient.invalidateQueries({ queryKey: ["candidate", candidateId] });
            onTerminalRef.current?.(data.candidate_id, data.status);
          } catch {
            setError("Failed to parse completion event");
          }
          done(); // evaluation finished — stop the stream for good
        });
      },
    });

    return () => handle.close();
  }, [candidateId, handlePayload, queryClient]);

  return {
    status,
    isConnected,
    isComplete,
    isProcessing: status === "Queued" || status === "Processing",
    error,
  };
}
