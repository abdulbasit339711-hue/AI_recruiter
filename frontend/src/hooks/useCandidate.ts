"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Candidate } from "@/types";

export function useCandidate(
  candidateId: number | null | undefined,
  enabled = true
) {
  return useQuery<Candidate>({
    queryKey: ["candidate", candidateId],
    queryFn: () => api.getCandidate(candidateId!),
    enabled: enabled && candidateId != null && candidateId > 0,
    refetchInterval: false,
  });
}
