// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { apiClient, isServer } from '@/lib/api/client';
import {
  GuardrailCreate,
  GuardrailDetail,
  GuardrailInfo,
  GuardrailUpdate,
  GuardrailVersion,
  ListGuardrailsResponse,
} from '@/lib/types';

/**
 * Guardrail API endpoints
 */
export const guardrailApi = {
  /**
   * Get list of guardrails
   */
  getGuardrails: async (): Promise<ListGuardrailsResponse> => {
    // Skip API calls during SSR
    if (isServer()) {
      return { guardrails: [], last_evaluated_key: null };
    }

    return apiClient.get<ListGuardrailsResponse>('admin/guardrail');
  },

  /**
   * Get a specific guardrail by ID and optional version
   */
  getGuardrail: async (
    guardrailId: string,
    version?: string,
  ): Promise<GuardrailDetail> => {
    const params: Record<string, string | number | boolean> = {};

    if (version) {
      params.guardrail_version = version;
    }

    return apiClient.get<GuardrailDetail>(
      `admin/guardrail/${guardrailId}`,
      params,
    );
  },

  /**
   * Create a new guardrail
   */
  createGuardrail: async (request: GuardrailCreate): Promise<GuardrailInfo> => {
    return apiClient.post<GuardrailInfo>('admin/guardrail', request);
  },

  /**
   * Update a guardrail
   */
  updateGuardrail: async (
    guardrailId: string,
    request: GuardrailUpdate,
  ): Promise<GuardrailInfo> => {
    return apiClient.put<GuardrailInfo>(
      `admin/guardrail/${guardrailId}`,
      request,
    );
  },

  /**
   * Delete a guardrail
   */
  deleteGuardrail: async (guardrailId: string): Promise<void> => {
    return apiClient.delete<void>(`admin/guardrail/${guardrailId}`);
  },

  /**
   * Publish a new guardrail version
   */
  publishGuardrailVersion: async (
    guardrailId: string,
    description?: string,
  ): Promise<GuardrailVersion> => {
    const params: Record<string, string | number | boolean> = {};

    if (description) {
      params.description = description;
    }

    return apiClient.post<GuardrailVersion>(
      `admin/guardrail/${guardrailId}/publish`,
      null,
      params,
    );
  },
};
