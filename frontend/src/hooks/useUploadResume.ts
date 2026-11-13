"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { UploadResponse } from "@/types";

interface UploadInput {
  file: File;
  iqToken?: string; // optional IQ screen result token to attach
  consent?: boolean; // applicant ticked the AI-processing consent box
}

export const useUploadResume = (jobId: number) => {
  const queryClient = useQueryClient();

  return useMutation<UploadResponse, Error, UploadInput>({
    mutationFn: ({ file, iqToken, consent }) => api.uploadResume(jobId, file, iqToken, consent),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["candidates", jobId] });
      return data;
    },
  });
};
