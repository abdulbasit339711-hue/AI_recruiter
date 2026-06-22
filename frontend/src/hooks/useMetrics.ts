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
  pendingReviewCount: number;
  interviewReadyCount: number;
  interviewPassedCount: number;
};

type MetricsFilters = {
  jobId?: number | null;
  fromDate?: string | null; // YYYY-MM-DD
  toDate?: string | null;   // YYYY-MM-DD
};

export const useMetrics = ({ jobId, fromDate, toDate }: MetricsFilters = {}) => {
  return useQuery<Metrics, Error>({
    queryKey: ["metrics", jobId ?? null, fromDate ?? null, toDate ?? null],
    queryFn: async () => {
      const params: Record<string, string | number> = {};
      if (jobId != null) params.job_id = jobId;
      if (fromDate) params.from_date = fromDate;
      if (toDate) params.to_date = toDate;
      const { data } = await axios.get("/metrics", { params });
      return data as Metrics;
    },
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
};
