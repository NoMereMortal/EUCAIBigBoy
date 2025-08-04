// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useMemo } from 'react';
import { useModels } from '@/hooks/use-models';
import { Model } from '@/lib/api/resources/model';

/**
 * Custom hook that provides default model selection logic
 * Returns the first available model sorted by order as the default
 */
export function useDefaultModel() {
  const { data: models, isLoading, error } = useModels();

  const defaultModel = useMemo((): Model | null => {
    // Always return null if models are not available yet or empty
    if (!models || models.length === 0) {
      return null;
    }

    // Filter available models and sort by order
    const availableModels = models
      .filter((model) => model.is_available)
      .sort((a, b) => (a.order || 0) - (b.order || 0));

    // Return the first available model (lowest order value) or null
    return availableModels.length > 0 ? availableModels[0] : null;
  }, [models]);

  return {
    defaultModel: defaultModel || null, // Ensure never undefined
    isLoading,
    error,
    hasModels: Boolean(models && models.length > 0),
    hasAvailableModels: Boolean(defaultModel),
  };
}

/**
 * Get the effective model ID (selected or default)
 * @param selectedModelId - The explicitly selected model ID
 * @param defaultModel - The default model from useDefaultModel
 * @returns The model ID to use, or null if no models available
 */
export function getEffectiveModelId(
  selectedModelId: string | null,
  defaultModel: Model | null,
): string | null {
  // If user has explicitly selected a model, use that
  if (selectedModelId) {
    return selectedModelId;
  }

  // Otherwise, fall back to the default model
  return defaultModel?.id || null;
}
