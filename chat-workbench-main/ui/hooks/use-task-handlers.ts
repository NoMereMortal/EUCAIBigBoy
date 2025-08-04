// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useQuery } from '@tanstack/react-query';
import { taskHandlerApi } from '@/lib/api/resources/task-handler';

// Query keys for React Query
export const taskHandlerKeys = {
  all: ['taskHandlers'] as const,
  lists: () => [...taskHandlerKeys.all, 'list'] as const,
  list: () => [...taskHandlerKeys.lists()] as const,
  details: () => [...taskHandlerKeys.all, 'detail'] as const,
  detail: (name: string) => [...taskHandlerKeys.details(), name] as const,
};

export function useTaskHandlers() {
  return useQuery({
    queryKey: taskHandlerKeys.list(),
    queryFn: () => taskHandlerApi.getTaskHandlers(),
    staleTime: 5 * 60 * 1000, // 5 minutes - task handlers don't change often
    gcTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useTaskHandler(handlerName: string) {
  return useQuery({
    queryKey: taskHandlerKeys.detail(handlerName),
    queryFn: () => taskHandlerApi.getTaskHandler(handlerName),
    enabled: !!handlerName,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  });
}
