// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { create } from 'zustand';
import { SettingsState } from '@/lib/store/types';
import { api } from '@/lib/api';

// Load persisted values from localStorage
const loadPersistedSettings = () => {
  if (typeof window === 'undefined') {
    return { selectedModelId: null, selectedTaskHandler: null };
  }

  try {
    const storedModelId = localStorage.getItem('selectedModelId');
    const storedTaskHandler = localStorage.getItem('selectedTaskHandler');
    return {
      selectedModelId: storedModelId || null,
      selectedTaskHandler: storedTaskHandler || null,
    };
  } catch (error) {
    console.error('Failed to load persisted settings:', error);
    return { selectedModelId: null, selectedTaskHandler: null };
  }
};

// Get initial state with persisted values
const initialState = loadPersistedSettings();

export const useSettingsStore = create<SettingsState>((set, get) => ({
  // Model, persona, prompt, and task handler selection states
  selectedModelId: initialState.selectedModelId, // Load from localStorage or null
  selectedPersonaId: null,
  selectedPromptId: null,
  selectedPrompt: null,
  selectedTaskHandler: initialState.selectedTaskHandler || 'chat', // Load from localStorage or default to chat

  // Get effective model ID (selected or default fallback)
  getEffectiveModelId: (defaultModelId?: string | null) => {
    const state = get();
    // If user has explicitly selected a model, use that
    if (state.selectedModelId) {
      return state.selectedModelId;
    }
    // Otherwise, fall back to the provided default model
    return defaultModelId || null;
  },

  // Set selected model
  setSelectedModel: (modelId) => {
    set({ selectedModelId: modelId });
    // Persist to localStorage
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('selectedModelId', modelId);
      } catch (error) {
        console.error('Failed to persist selectedModelId:', error);
      }
    }
  },

  // Set selected persona
  setSelectedPersona: (personaId) => {
    set({ selectedPersonaId: personaId });
  },

  // Set selected task handler
  setSelectedTaskHandler: (taskHandler) => {
    console.debug('Setting task handler:', taskHandler);
    set({ selectedTaskHandler: taskHandler });
    // Persist to localStorage
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('selectedTaskHandler', taskHandler);
        console.debug(
          'Persisted selectedTaskHandler to localStorage:',
          taskHandler,
          'Current localStorage value:',
          localStorage.getItem('selectedTaskHandler'),
        );
      } catch (error) {
        console.error('Failed to persist selectedTaskHandler:', error);
      }
    }
  },

  // Set selected prompt
  setSelectedPrompt: async (promptId) => {
    if (!promptId) {
      set({ selectedPromptId: null, selectedPrompt: null });
      return;
    }

    // Skip API calls during SSR
    if (typeof window === 'undefined') return;

    try {
      const prompt = await api.getPrompt(promptId);
      set({
        selectedPromptId: promptId,
        selectedPrompt: prompt,
      });
    } catch (error) {
      console.error('Failed to fetch prompt:', error);
      set({ selectedPromptId: null, selectedPrompt: null });
    }
  },

  // Clear selected prompt
  clearSelectedPrompt: () => {
    set({ selectedPromptId: null, selectedPrompt: null });
  },

  // Fetch prompts
  fetchPrompts: async (limit = 100, lastKey, category) => {
    // Skip API calls during SSR
    if (typeof window === 'undefined') {
      return { prompts: [], last_evaluated_key: null };
    }

    try {
      return await api.getPrompts(limit, lastKey, category);
    } catch (error) {
      console.error('Failed to fetch prompts:', error);
      return { prompts: [], last_evaluated_key: null };
    }
  },

  // Search prompts
  searchPrompts: async (query, limit = 100, lastKey) => {
    // Skip API calls during SSR
    if (typeof window === 'undefined') {
      return { prompts: [], last_evaluated_key: null };
    }

    try {
      return await api.searchPrompts(query, limit, lastKey);
    } catch (error) {
      console.error('Failed to search prompts:', error);
      return { prompts: [], last_evaluated_key: null };
    }
  },
}));
