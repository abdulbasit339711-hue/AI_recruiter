// src/hooks/useMetrics.ts
"use client";

import { useQuery } from "@tanstack/react-query";
import axios from "@/lib/api";

type Metrics = {
  totalJobs: number;
  totalCandidates: number;
  avgScore: number;
  pendingCount: number;
  processedCount: number;
  failedCount: number;
};

export const useMetrics = () => {
  return useQuery<Metrics, Error>({
    queryKey: ['metrics'],
    queryFn: async () => {
      const { data } = await axios.get('/metrics');
      return data as Metrics;
    },
    staleTime: 1000 * 60 * 5,
  });
};
