// src/hooks/useMetrics.ts
"use client";

import { useQuery, keepPreviousData } from "@tanstack/react-query";
import axios from "@/lib/api";

type Metrics = {
  totalJobs: number;
  totalCandidates: number;
  avgScore: number;
  pendingCount: number;
  processedCount: number;
  failedCount: number;
  scoreDistribution: { label: string; count: number }[];
  shortlistedCount: number;
  topScore: number;
};

export const useMetrics = (jobId?: number | null) => {
  return useQuery<Metrics, Error>({
    queryKey: ['metrics', jobId ?? null],
    queryFn: async () => {
      const params = jobId != null ? { job_id: jobId } : {};
      const { data } = await axios.get('/metrics', { params });
      return data as Metrics;
    },
    staleTime: 30_000, // 30 s — short so dashboard stays fresh
    placeholderData: keepPreviousData,
  });
};
