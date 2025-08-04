// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

/**
 * AdminGuard Component
 *
 * Protects routes that require admin privileges.
 * Shows a loading state during authentication checks.
 * Renders a fallback component for non-admin users if provided.
 * Uses the centralized auth context to efficiently check admin status.
 */

'use client';

import { ReactNode } from 'react';
import { useAuth } from '@/hooks/auth';
import { isServerSide } from '@/hooks/auth/utils';
import { LoadingIndicator, AuthError } from '@/components/auth/auth-ui';

interface AdminGuardProps {
  children: ReactNode;
  fallback?: ReactNode;
  showLoading?: boolean;
  showError?: boolean;
}

export function AdminGuard({
  children,
  fallback,
  showLoading = true,
  showError = false,
}: AdminGuardProps) {
  // Use centralized auth state
  const { isAdmin, isLoading, error, isAuthenticated } = useAuth();

  // Handle server-side rendering
  if (isServerSide()) {
    return null;
  }

  // Show loading state if enabled
  if (isLoading && showLoading) {
    return <LoadingIndicator message="Checking admin permissions..." />;
  }

  // Show authentication errors if enabled
  if (error && showError) {
    return <AuthError error={error} onRetry={() => window.location.reload()} />;
  } else if (error) {
    // Just log the error if we don't want to show it
    console.error('Authentication error in AdminGuard:', error);
  }

  // If user is authenticated and has admin privileges, render children
  if (isAuthenticated && isAdmin) {
    return <>{children}</>;
  }

  // If user is not admin and fallback is provided, render fallback
  if (fallback) {
    return <>{fallback}</>;
  }

  // Otherwise render nothing
  return null;
}
