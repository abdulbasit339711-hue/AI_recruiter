"use client";
import { useQuery } from "@tanstack/react-query";
import { api, type InterviewResult } from "@/lib/api";

export const useInterviewResult = (candidateId: number) =>
  useQuery<InterviewResult, Error>({
    queryKey: ["interview", candidateId],
    queryFn: () => api.getInterviewResult(candidateId),
    // Poll every 10 s while no interview exists yet — stops automatically once
    // has_interview is true (refetchInterval returns false to cancel polling).
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || !data.has_interview) return 10_000;
      return false;
    },
    staleTime: 1000 * 30,
    enabled: candidateId > 0,
  });
