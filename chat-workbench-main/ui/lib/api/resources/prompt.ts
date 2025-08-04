// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { apiClient, isServer } from '@/lib/api/client';
import {
  CreatePromptRequest,
  ListPromptsResponse,
  Prompt,
  UpdatePromptRequest,
} from '@/lib/types';

/**
 * Prompt library API endpoints
 */
export const promptApi = {
  /**
   * Create a new prompt
   */
  createPrompt: async (request: CreatePromptRequest): Promise<Prompt> => {
    return apiClient.post<Prompt>('prompt', request);
  },

  /**
   * Get a specific prompt by ID
   */
  getPrompt: async (promptId: string): Promise<Prompt> => {
    // Skip API calls during SSR
    if (isServer()) {
      return {
        prompt_id: promptId,
        name: 'Loading...',
        content: '',
        description: '',
        category: '',
        tags: [],
        metadata: {},
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    }

    return apiClient.get<Prompt>(`prompt/${promptId}`);
  },

  /**
   * Get list of prompts with optional filtering
   */
  getPrompts: async (
    limit = 100,
    lastKey?: string,
    category?: string,
    isActive = true,
  ): Promise<ListPromptsResponse> => {
    // Skip API calls during SSR
    if (isServer()) {
      return { prompts: [], last_evaluated_key: null };
    }

    const params: Record<string, string | number | boolean> = {
      limit: limit,
      is_active: isActive,
    };

    if (lastKey) {
      params.last_key = lastKey;
    }

    if (category) {
      params.category = category;
    }

    return apiClient.get<ListPromptsResponse>('prompt', params);
  },

  /**
   * Search prompts by query string
   */
  searchPrompts: async (
    query: string,
    limit = 100,
    lastKey?: string,
  ): Promise<ListPromptsResponse> => {
    // Skip API calls during SSR
    if (isServer()) {
      return { prompts: [], last_evaluated_key: null };
    }

    const params: Record<string, string | number | boolean> = {
      query: query,
      limit: limit,
    };

    if (lastKey) {
      params.last_key = lastKey;
    }

    return apiClient.get<ListPromptsResponse>('prompt/search', params);
  },

  /**
   * Update a prompt
   */
  updatePrompt: async (
    promptId: string,
    request: UpdatePromptRequest,
  ): Promise<Prompt> => {
    return apiClient.put<Prompt>(`prompt/${promptId}`, request);
  },

  /**
   * Delete a prompt
   */
  deletePrompt: async (promptId: string): Promise<Prompt> => {
    return apiClient.delete<Prompt>(`prompt/${promptId}`);
  },
};
