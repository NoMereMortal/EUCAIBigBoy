// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { apiClient } from '@/lib/api/client';

export interface ModelFeature {
  name: string;
  description: string;
}

export interface Model {
  id: string;
  name: string;
  provider: string;
  description: string;
  features: ModelFeature[];
  provider_link: string;
  order: number;
  is_available: boolean;
}

export interface ListModelsResponse {
  models: Model[];
}

/**
 * Model management API resource
 */
export const modelApi = {
  /**
   * Fetch all available models
   * @param provider Optional provider filter
   * @returns List of models
   */
  getModels: async (provider?: string): Promise<Model[]> => {
    try {
      const params: Record<string, string | number | boolean> = {};
      if (provider) {
        params.provider = provider;
      }

      const response = await apiClient.get<ListModelsResponse>(
        'models',
        params,
      );
      return response.models;
    } catch (error) {
      console.error('Error fetching models:', error);
      return [];
    }
  },

  /**
   * Get detailed information about a specific model
   * @param modelId The ID of the model to fetch
   * @returns Model details or null if not found
   */
  getModel: async (modelId: string): Promise<Model | null> => {
    try {
      const response = await apiClient.get<Model>(`models/${modelId}`);
      return response;
    } catch (error) {
      console.error(`Error fetching model ${modelId}:`, error);
      return null;
    }
  },
};

// For backward compatibility
export const getModels = modelApi.getModels;
export const getModel = modelApi.getModel;
