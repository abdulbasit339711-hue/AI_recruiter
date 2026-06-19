"use client";
import { useQuery } from "@tanstack/react-query";
import { api, type InterviewResult } from "@/lib/api";

export const useInterviewResult = (candidateId: number) =>
  useQuery<InterviewResult, Error>({
    queryKey: ["interview", candidateId],
    queryFn: () => api.getInterviewResult(candidateId),
    staleTime: 1000 * 60,
    enabled: candidateId > 0,
  });
