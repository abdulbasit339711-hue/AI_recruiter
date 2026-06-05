"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { UploadResponse } from "@/types";

export const useUploadResume = (jobId: number) => {
  const queryClient = useQueryClient();

  return useMutation<UploadResponse, Error, File>({
    mutationFn: (file) => api.uploadResume(jobId, file),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["candidates", jobId] });
      return data;
    },
  });
};
