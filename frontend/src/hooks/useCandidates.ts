// src/hooks/useCandidates.ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CandidateStatus, PaginatedCandidates } from "@/types";

type CandidateFilters = {
  jobId?: number;
  page?: number;
  pageSize?: number;
  status?: CandidateStatus;
  hrStatus?: string;
  sortBy?: string;
  order?: string;
};

export const useCandidates = (filters: CandidateFilters = {}) => {
  const jobId = filters.jobId;
  const page = filters.page ?? 1;
  const pageSize = filters.pageSize ?? 50;

  return useQuery<PaginatedCandidates, Error>({
    queryKey: [
      "candidates",
      jobId,
      page,
      pageSize,
      filters.status,
      filters.hrStatus,
      filters.sortBy,
      filters.order,
    ],
    queryFn: () =>
      api.getJobCandidates(
        jobId!,
        page,
        pageSize,
        filters.status,
        filters.hrStatus,
        filters.sortBy,
        filters.order
      ),
    enabled: jobId != null && jobId > 0,
    staleTime: 1000 * 30,
  });
};
