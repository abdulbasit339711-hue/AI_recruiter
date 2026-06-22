"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Org } from "@/types";

export const useOrgs = () =>
  useQuery<Org[], Error>({
    queryKey: ["orgs"],
    queryFn: () => api.getOrgs(),
    staleTime: 1000 * 60 * 5,
  });

export const useOrgBySlug = (slug: string) =>
  useQuery<Org, Error>({
    queryKey: ["orgs", slug],
    queryFn: () => api.getOrgBySlug(slug),
    staleTime: 1000 * 60 * 5,
    enabled: !!slug,
  });

export const useCreateOrg = () => {
  const qc = useQueryClient();
  return useMutation<Org, Error, Parameters<typeof api.createOrg>[0]>({
    mutationFn: (params) => api.createOrg(params),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orgs"] }),
  });
};

export const useUpdateOrg = () => {
  const qc = useQueryClient();
  return useMutation<Org, Error, { id: number } & Parameters<typeof api.updateOrg>[1]>({
    mutationFn: ({ id, ...params }) => api.updateOrg(id, params),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orgs"] }),
  });
};

export const useDeleteOrg = () => {
  const qc = useQueryClient();
  return useMutation<{ message: string; org_id: number }, Error, number>({
    mutationFn: (id) => api.deleteOrg(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orgs"] }),
  });
};
