// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useQuery } from '@tanstack/react-query';
import { modelApi } from '@/lib/api/resources/model';

// Query keys for React Query
export const modelKeys = {
  all: ['models'] as const,
  lists: () => [...modelKeys.all, 'list'] as const,
  list: (filters: { provider?: string } = {}) =>
    [...modelKeys.lists(), filters] as const,
  details: () => [...modelKeys.all, 'detail'] as const,
  detail: (id: string) => [...modelKeys.details(), id] as const,
};

export function useModels(provider?: string) {
  return useQuery({
    queryKey: modelKeys.list({ provider }),
    queryFn: () => modelApi.getModels(provider),
  });
}

export function useModel(modelId: string) {
  return useQuery({
    queryKey: modelKeys.detail(modelId),
    queryFn: () => modelApi.getModel(modelId),
    enabled: !!modelId,
  });
}
