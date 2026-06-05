// src/hooks/useJob.ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Job } from "@/types";

export const useJob = (jobId: number) => {
  return useQuery<Job, Error>({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId),
    staleTime: 1000 * 60 * 5,
    enabled: !!jobId,
  });
};
