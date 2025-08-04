// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useEffect, useState } from 'react';
import { authManager } from '@/lib/auth/auth-manager';
import { authInterceptor } from '@/lib/auth/auth-interceptor';

/**
 * AuthStatus Component
 *
 * Provides user feedback during authentication operations:
 * - Token refresh progress
 * - Auth error states
 * - Queue status during token operations
 */

interface AuthStatusState {
  isRefreshing: boolean;
  queueLength: number;
  error: Error | null;
  showStatus: boolean;
}

export function AuthStatus() {
  const [status, setStatus] = useState<AuthStatusState>({
    isRefreshing: false,
    queueLength: 0,
    error: null,
    showStatus: false,
  });

  useEffect(() => {
    // Listen for auth manager events
    const handleTokenRefresh = () => {
      const queueStatus = authInterceptor.getQueueStatus();
      setStatus((prev) => ({
        ...prev,
        isRefreshing: queueStatus.isRefreshing,
        queueLength: queueStatus.queueLength,
        showStatus: queueStatus.isRefreshing || queueStatus.queueLength > 0,
      }));
    };

    const handleTokenRefreshed = () => {
      setStatus((prev) => ({
        ...prev,
        isRefreshing: false,
        queueLength: 0,
        error: null,
        showStatus: false,
      }));
    };

    const handleAuthError = (event: any) => {
      setStatus((prev) => ({
        ...prev,
        isRefreshing: false,
        error: event.data?.error || new Error('Authentication error'),
        showStatus: true,
      }));

      // Auto-hide error after 5 seconds
      setTimeout(() => {
        setStatus((prev) => ({
          ...prev,
          error: null,
          showStatus: prev.isRefreshing || prev.queueLength > 0,
        }));
      }, 5000);
    };

    // Subscribe to auth manager events
    authManager.on('auth-changed', handleTokenRefresh);
    authManager.on('token-refreshed', handleTokenRefreshed);
    authManager.on('auth-error', handleAuthError);

    // Check initial queue status
    handleTokenRefresh();

    return () => {
      authManager.off('auth-changed', handleTokenRefresh);
      authManager.off('token-refreshed', handleTokenRefreshed);
      authManager.off('auth-error', handleAuthError);
    };
  }, []);

  // Don't render anything if there's nothing to show
  if (!status.showStatus) {
    return null;
  }

  return (
    <div className="fixed top-4 right-4 z-50">
      {status.isRefreshing && (
        <div className="bg-blue-100 border border-blue-300 text-blue-700 px-4 py-2 rounded-md shadow-sm flex items-center space-x-2">
          <div className="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full"></div>
          <span className="text-sm">
            Refreshing authentication...
            {status.queueLength > 0 &&
              ` (${status.queueLength} requests queued)`}
          </span>
        </div>
      )}

      {status.error && (
        <div className="bg-red-100 border border-red-300 text-red-700 px-4 py-2 rounded-md shadow-sm">
          <div className="flex items-center space-x-2">
            <svg
              className="h-4 w-4 text-red-600"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            <div>
              <p className="text-sm font-medium">Authentication Error</p>
              <p className="text-xs text-red-600">{status.error.message}</p>
            </div>
          </div>
        </div>
      )}

      {!status.isRefreshing && !status.error && status.queueLength > 0 && (
        <div className="bg-yellow-100 border border-yellow-300 text-yellow-700 px-4 py-2 rounded-md shadow-sm">
          <span className="text-sm">
            {status.queueLength} request{status.queueLength === 1 ? '' : 's'}{' '}
            waiting for authentication
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * Hook to get current auth status for components that need it
 */
export function useAuthStatus() {
  const [status, setStatus] = useState(() => ({
    ...authInterceptor.getQueueStatus(),
    error: authManager.getState().error,
  }));

  useEffect(() => {
    const updateStatus = () => {
      setStatus({
        ...authInterceptor.getQueueStatus(),
        error: authManager.getState().error,
      });
    };

    // Update on auth events
    authManager.on('auth-changed', updateStatus);
    authManager.on('token-refreshed', updateStatus);
    authManager.on('auth-error', updateStatus);

    return () => {
      authManager.off('auth-changed', updateStatus);
      authManager.off('token-refreshed', updateStatus);
      authManager.off('auth-error', updateStatus);
    };
  }, []);

  return status;
}
