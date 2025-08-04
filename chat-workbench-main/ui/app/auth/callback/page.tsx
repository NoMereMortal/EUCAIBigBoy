// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useEffect, useState, useRef } from 'react';
import { useAuth } from '@/hooks/auth';

export default function AuthCallback() {
  const {
    isAuthenticated,
    isLoading,
    error,
    user,
    isSessionReady,
    sessionError,
  } = useAuth();
  const [authError, setAuthError] = useState<string | null>(null);
  const [redirectAttempted, setRedirectAttempted] = useState(false);
  const [showManualRedirect, setShowManualRedirect] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Don't attempt redirect multiple times
    if (redirectAttempted) {
      return;
    }

    // Wait for auth state to stabilize (not loading)
    if (isLoading) {
      return;
    }

    // Handle successful authentication - wait for session to be ready
    if (isAuthenticated && user) {
      if (isSessionReady) {
        setRedirectAttempted(true);

        try {
          // Redirect to home page
          window.location.replace('/');

          // Set a backup timer to show manual redirect button if redirect doesn't work
          timeoutRef.current = setTimeout(() => {
            setShowManualRedirect(true);
          }, 3000);
        } catch (error) {
          console.error('Redirect failed:', error);
          setShowManualRedirect(true);
        }

        return () => {
          if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
          }
        };
      } else if (sessionError) {
        setAuthError(`Session setup failed: ${sessionError}`);

        // Redirect to home after showing error
        timeoutRef.current = setTimeout(() => {
          window.location.replace('/');
        }, 3000);

        return () => {
          if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
          }
        };
      } else {
        // Authenticated but session not ready yet - keep waiting
        return;
      }
    }

    // Handle authentication error
    if (error) {
      setAuthError(`Authentication failed: ${error.message}`);

      // Redirect to home after showing error
      timeoutRef.current = setTimeout(() => {
        window.location.replace('/');
      }, 3000);

      return () => {
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }
      };
    }

    // Handle case where loading finished but no auth success or error
    if (!isLoading && !isAuthenticated && !error) {
      setAuthError(
        'Authentication process completed but no result received. Please try signing in again.',
      );

      timeoutRef.current = setTimeout(() => {
        window.location.replace('/');
      }, 2000);

      return () => {
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }
      };
    }
  }, [
    isAuthenticated,
    isLoading,
    error,
    user,
    isSessionReady,
    sessionError,
    redirectAttempted,
  ]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Use a client-side effect to handle the loading state change
  // This ensures consistent rendering between server and client
  const [clientSideLoading, setClientSideLoading] = useState(true);
  const [clientSideReady, setClientSideReady] = useState(false);

  useEffect(() => {
    // On client side, update the loading state to match the auth state
    setClientSideReady(true);
    setClientSideLoading(isLoading);
  }, [isLoading]);

  // Manual redirect handler for fallback button
  const handleManualRedirect = () => {
    try {
      window.location.replace('/');
    } catch (error) {
      console.error('Manual redirect failed:', error);
      // Force page reload as absolute last resort
      window.location.reload();
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background">
      {/* Loading spinner */}
      {(clientSideReady ? clientSideLoading : true) && !authError && (
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-t-transparent border-white mb-4"></div>
      )}

      {/* Error display */}
      {authError ? (
        <div className="text-red-500 bg-red-50 px-4 py-2 rounded-md mb-4 max-w-md text-center">
          {authError}
        </div>
      ) : (
        <div className="text-prose dark:text-prose-dark mb-4">
          {isAuthenticated && isSessionReady
            ? 'Authentication complete! Redirecting...'
            : isAuthenticated
              ? 'Setting up your session...'
              : 'Completing sign in...'}
        </div>
      )}

      {/* Manual redirect button - shown if automatic redirect fails */}
      {showManualRedirect && (
        <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md text-center">
          <p className="text-yellow-800 mb-3">
            Automatic redirect seems to have failed. Please click the button
            below to continue:
          </p>
          <button
            onClick={handleManualRedirect}
            className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            Continue to Home Page
          </button>
        </div>
      )}
    </div>
  );
}
