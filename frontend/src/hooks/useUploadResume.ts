"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { UploadResponse } from "@/types";

interface UploadInput {
  file: File;
  iqToken?: string; // optional IQ screen result token to attach
}

export const useUploadResume = (jobId: number) => {
  const queryClient = useQueryClient();

  return useMutation<UploadResponse, Error, UploadInput>({
    mutationFn: ({ file, iqToken }) => api.uploadResume(jobId, file, iqToken),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["candidates", jobId] });
      return data;
    },
  });
};
