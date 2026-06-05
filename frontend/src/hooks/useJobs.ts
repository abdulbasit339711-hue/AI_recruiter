import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import type { Job } from '../types';

export const useJobs = (status: 'Active' | 'Archived' = 'Active') => {
  return useQuery<Job[], Error>({
    queryKey: ['jobs', status],
    queryFn: () => api.getJobs(status),
    staleTime: 1000 * 60 * 5,
  });
};
