// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { apiClient } from '@/lib/api/client';
import { UserProfile } from '@/lib/types';

/**
 * User API endpoints
 */
export const userApi = {
  /**
   * Get the current user's profile
   */
  getCurrentUser: async (): Promise<UserProfile> => {
    return apiClient.get<UserProfile>('user/profile');
  },

  /**
   * Update the current user's profile
   */
  updateProfile: async (
    updates: Partial<UserProfile>,
  ): Promise<UserProfile> => {
    return apiClient.put<UserProfile>('user/profile', updates);
  },

  /**
   * Get user preferences
   */
  getPreferences: async (): Promise<Record<string, any>> => {
    return apiClient.get<Record<string, any>>('user/preferences');
  },

  /**
   * Update user preferences
   */
  updatePreferences: async (
    preferences: Record<string, any>,
  ): Promise<Record<string, any>> => {
    return apiClient.put<Record<string, any>>('user/preferences', preferences);
  },
};
