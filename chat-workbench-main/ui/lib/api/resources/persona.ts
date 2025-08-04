// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { apiClient, isServer } from '@/lib/api/client';
import { Persona } from '@/lib/types';

// Interface definitions for API requests/responses
interface CreatePersonaRequest {
  name: string;
  prompt: string;
  is_active?: boolean;
}

interface UpdatePersonaRequest {
  name?: string;
  prompt?: string;
  is_active?: boolean;
}

interface ListPersonasResponse {
  personas: Persona[];
  last_key?: string;
}

/**
 * Persona API endpoints
 */
export const personaApi = {
  /**
   * Create a new persona
   */
  createPersona: async (request: CreatePersonaRequest): Promise<Persona> => {
    return apiClient.post<Persona>('persona', request);
  },

  /**
   * Get a specific persona by ID
   */
  getPersona: async (personaId: string): Promise<Persona> => {
    // Skip API calls during SSR
    if (isServer()) {
      return {
        persona_id: personaId,
        name: 'Loading...',
        description: '',
        prompt: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        metadata: {},
        is_active: true,
      } as Persona;
    }

    return apiClient.get<Persona>(`persona/${personaId}`);
  },

  /**
   * Get list of personas with optional filtering
   */
  getPersonas: async (
    limit = 100,
    lastKey?: string,
    isActive = true,
  ): Promise<ListPersonasResponse> => {
    // Skip API calls during SSR
    if (isServer()) {
      return { personas: [], last_key: undefined };
    }

    const params: Record<string, string | number | boolean> = {
      limit: limit,
      is_active: isActive,
    };

    if (lastKey) {
      params.last_key = lastKey;
    }

    return apiClient.get<ListPersonasResponse>('persona', params);
  },

  /**
   * Update a persona
   */
  updatePersona: async (
    personaId: string,
    request: UpdatePersonaRequest,
  ): Promise<Persona> => {
    return apiClient.put<Persona>(`persona/${personaId}`, request);
  },

  /**
   * Delete a persona
   */
  deletePersona: async (personaId: string): Promise<Persona> => {
    return apiClient.delete<Persona>(`persona/${personaId}`);
  },
};
