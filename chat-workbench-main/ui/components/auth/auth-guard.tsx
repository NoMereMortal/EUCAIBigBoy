// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

/**
 * AuthGuard Component
 *
 * Protects routes that require authentication.
 * Redirects unauthenticated users to the home page.
 * Handles loading states and SSR gracefully.
 */

'use client';

import { ReactNode, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/auth';
import { isServerSide } from '@/hooks/auth/utils';
import { ClientLoadingIndicator, AuthError } from '@/components/auth/auth-ui';

interface AuthGuardProps {
  children: ReactNode;
  fallback?: ReactNode;
  showError?: boolean;
}

export function AuthGuard({
  children,
  fallback,
  showError = false,
}: AuthGuardProps) {
  const { isAuthenticated, isLoading, error } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Only redirect if authentication has been attempted and failed
    if (!isLoading && !isAuthenticated) {
      console.debug('User not authenticated, redirecting to home');
      router.push('/');
    }
  }, [isAuthenticated, isLoading, router]);

  // Handle server-side rendering and initial loading state safely
  // This prevents the "flash of loading indicator" during hydration
  if (isServerSide()) {
    return null;
  }

  // After hydration, show loading indicator only on the client-side
  if (isLoading) {
    return <ClientLoadingIndicator message="Verifying authentication..." />;
  }

  // If there's an auth error and we want to show it
  if (error && showError) {
    return <AuthError error={error} onRetry={() => window.location.reload()} />;
  }

  // Show custom fallback or null when not authenticated
  // (redirect will happen in useEffect)
  if (!isAuthenticated) {
    return fallback || null;
  }

  // If there's an auth error, log it even if we don't show it
  if (error) {
    console.error('Authentication error:', error);
  }

  // User is authenticated, render protected content
  return <>{children}</>;
}
