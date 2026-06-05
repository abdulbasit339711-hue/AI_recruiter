// src/hooks/useCreateJob.ts
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Job } from "@/types";

type NewJob = {
  title: string;
  department: string;
  job_description: string;
  llm_prompt?: string;
};

export const useCreateJob = () => {
  const queryClient = useQueryClient();
  return useMutation<Job, Error, NewJob>({
    mutationFn: (newJob) => api.createJob(newJob),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
};
