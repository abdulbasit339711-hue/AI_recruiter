// src/hooks/useUpdateJob.ts
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Job } from "@/types";

// `id` identifies the job; `created_at` is server-managed and not editable.
type UpdateJobPayload = Partial<Omit<Job, 'id' | 'created_at'>> & { id: number };

export const useUpdateJob = () => {
  const queryClient = useQueryClient();
  return useMutation<Job, Error, UpdateJobPayload>({
    mutationFn: ({ id, ...payload }) => api.updateJob(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
};
