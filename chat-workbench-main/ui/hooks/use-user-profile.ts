// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useAuth } from '@/hooks/auth';

export type UserProfile = {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  groups: string[];
  isAdmin: boolean;
};

/**
 * Custom hook for accessing user profile information
 *
 * This hook provides a convenient way to access the current user's profile
 * information throughout the application. It returns null when the user
 * is not authenticated.
 */
export function useUserProfile() {
  const { userProfile, isLoading, error, isAdmin, refreshToken } = useAuth();

  return {
    userProfile,
    isLoading,
    error,
    isAdmin,
    refreshToken,
    // Convenience computed properties
    userId: userProfile?.id || null,
    email: userProfile?.email || null,
    fullName: userProfile
      ? `${userProfile.firstName} ${userProfile.lastName}`.trim()
      : null,
    firstName: userProfile?.firstName || null,
    lastName: userProfile?.lastName || null,
    groups: userProfile?.groups || [],
    getGreeting: () => {
      if (!userProfile) return 'Hello';
      const name = userProfile.firstName || '';
      const hour = new Date().getHours();
      if (hour < 12) return `Good morning, ${name}`;
      if (hour < 18) return `Good afternoon, ${name}`;
      return `Good evening, ${name}`;
    },
  };
}
