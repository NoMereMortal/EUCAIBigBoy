// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/index';
import { Prompt, CreatePromptRequest, UpdatePromptRequest } from '@/lib/types';

// Query keys for React Query
export const promptKeys = {
  all: ['prompts'] as const,
  lists: () => [...promptKeys.all, 'list'] as const,
  list: (filters: { limit?: number; category?: string } = {}) =>
    [...promptKeys.lists(), filters] as const,
  search: (query: string) => [...promptKeys.lists(), 'search', query] as const,
  details: () => [...promptKeys.all, 'detail'] as const,
  detail: (id: string) => [...promptKeys.details(), id] as const,
};

// Hook for fetching prompts list
export function usePrompts(limit = 100, category?: string) {
  return useQuery({
    queryKey: promptKeys.list({ limit, category }),
    queryFn: () => api.getPrompts(limit, undefined, category),
    select: (data) => data.prompts,
  });
}

// Hook for searching prompts
export function useSearchPrompts(query: string, limit = 100) {
  return useQuery({
    queryKey: promptKeys.search(query),
    queryFn: () => api.searchPrompts(query, limit),
    select: (data) => data.prompts,
    enabled: !!query,
  });
}

// Hook for fetching a single prompt
export function usePrompt(promptId: string) {
  return useQuery({
    queryKey: promptKeys.detail(promptId),
    queryFn: () => api.getPrompt(promptId),
    enabled: !!promptId,
  });
}

// Hook for creating a new prompt
export function useCreatePrompt() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CreatePromptRequest) => api.createPrompt(request),
    onSuccess: (newPrompt) => {
      // Invalidate prompt lists
      queryClient.invalidateQueries({ queryKey: promptKeys.lists() });

      // Add the new prompt to the cache
      queryClient.setQueryData(
        promptKeys.detail(newPrompt.prompt_id),
        newPrompt,
      );
    },
  });
}

// Hook for updating a prompt
export function useUpdatePrompt() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      promptId,
      request,
    }: {
      promptId: string;
      request: UpdatePromptRequest;
    }) => api.updatePrompt(promptId, request),
    onSuccess: (updatedPrompt) => {
      // Update the prompt in the cache
      queryClient.setQueryData(
        promptKeys.detail(updatedPrompt.prompt_id),
        updatedPrompt,
      );

      // Invalidate prompt lists to reflect the update
      queryClient.invalidateQueries({ queryKey: promptKeys.lists() });
    },
  });
}

// Hook for deleting a prompt
export function useDeletePrompt() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (promptId: string) => api.deletePrompt(promptId),
    onSuccess: (_, promptId) => {
      // Remove the prompt from the cache
      queryClient.removeQueries({ queryKey: promptKeys.detail(promptId) });

      // Invalidate prompt lists to reflect the deletion
      queryClient.invalidateQueries({ queryKey: promptKeys.lists() });
    },
  });
}
