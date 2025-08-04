// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useEffect } from 'react';
import { useAuth } from '@/hooks/auth';

/**
 * AuthInitializer Component
 *
 * This component is responsible for:
 * 1. Handling auth events for cleanup
 * 2. Managing React Query cache invalidation on auth changes
 *
 * Note: Token refresh is now handled automatically by the AuthManager,
 * so no manual refresh logic is needed here.
 *
 * It should be placed high in the component tree, such as in the app's layout.
 */
export function AuthInitializer() {
  const auth = useAuth();

  // Listen for auth state changes and invalidate React Query cache
  useEffect(() => {
    const handleAuthEvent = async () => {
      console.debug('Auth event detected, clearing cache');
      try {
        const { queryClient } = await import('@/lib/react-query');
        queryClient.clear();
      } catch (error) {
        console.error('Error clearing query cache:', error);
      }
    };

    window.addEventListener('auth:logout', handleAuthEvent);
    window.addEventListener('auth:login', handleAuthEvent);

    return () => {
      window.removeEventListener('auth:logout', handleAuthEvent);
      window.removeEventListener('auth:login', handleAuthEvent);
    };
  }, []);

  // This component doesn't render anything
  return null;
}
