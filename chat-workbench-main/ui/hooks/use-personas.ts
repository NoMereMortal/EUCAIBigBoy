// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/index';
import {
  Persona,
  CreatePersonaRequest,
  UpdatePersonaRequest,
} from '@/lib/types';

// Query keys for React Query
export const personaKeys = {
  all: ['personas'] as const,
  lists: () => [...personaKeys.all, 'list'] as const,
  list: (filters: { limit?: number } = {}) =>
    [...personaKeys.lists(), filters] as const,
  details: () => [...personaKeys.all, 'detail'] as const,
  detail: (id: string) => [...personaKeys.details(), id] as const,
};

// Hook for fetching personas list
export function usePersonas(limit = 100) {
  return useQuery({
    queryKey: personaKeys.list({ limit }),
    queryFn: () => api.getPersonas(limit),
    select: (data) => data.personas,
  });
}

// Hook for fetching a single persona
export function usePersona(personaId: string) {
  return useQuery({
    queryKey: personaKeys.detail(personaId),
    queryFn: () => api.getPersona(personaId),
    enabled: !!personaId && personaId !== 'none',
  });
}

// Hook for creating a new persona
export function useCreatePersona() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CreatePersonaRequest) => api.createPersona(request),
    onSuccess: (newPersona) => {
      // Invalidate persona lists
      queryClient.invalidateQueries({ queryKey: personaKeys.lists() });

      // Add the new persona to the cache
      queryClient.setQueryData(
        personaKeys.detail(newPersona.persona_id),
        newPersona,
      );
    },
  });
}

// Hook for updating a persona
export function useUpdatePersona() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      personaId,
      request,
    }: {
      personaId: string;
      request: UpdatePersonaRequest;
    }) => api.updatePersona(personaId, request),
    onSuccess: (updatedPersona) => {
      // Update the persona in the cache
      queryClient.setQueryData(
        personaKeys.detail(updatedPersona.persona_id),
        updatedPersona,
      );

      // Invalidate persona lists to reflect the update
      queryClient.invalidateQueries({ queryKey: personaKeys.lists() });
    },
  });
}

// Hook for deleting a persona
export function useDeletePersona() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (personaId: string) => api.deletePersona(personaId),
    onSuccess: (_, personaId) => {
      // Remove the persona from the cache
      queryClient.removeQueries({ queryKey: personaKeys.detail(personaId) });

      // Invalidate persona lists to reflect the deletion
      queryClient.invalidateQueries({ queryKey: personaKeys.lists() });
    },
  });
}
