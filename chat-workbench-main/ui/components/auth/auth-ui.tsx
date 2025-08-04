// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import React from 'react';
import { isServerSide } from '@/hooks/auth/utils';

/**
 * Loading indicator component with consistent styling
 * Used across authentication flows
 */
interface LoadingIndicatorProps {
  message?: string;
  className?: string;
}

export function LoadingIndicator({
  message,
  className = '',
}: LoadingIndicatorProps) {
  // Ensure there's no trailing space when className is empty
  const combinedClassName = className
    ? `flex flex-col h-full items-center justify-center ${className}`
    : 'flex flex-col h-full items-center justify-center';

  return (
    <div className={combinedClassName}>
      <div className="animate-spin rounded-full h-12 w-12 border-4 border-t-transparent border-primary mb-4" />
      {message && (
        <div className="text-sm text-muted-foreground">{message}</div>
      )}
    </div>
  );
}

/**
 * Client-side only version of the LoadingIndicator
 * This prevents hydration mismatches between server and client rendering
 */
export const ClientLoadingIndicator = withClientSideRendering(LoadingIndicator);

/**
 * Higher-order component that only renders on the client side
 * Prevents hydration errors and SSR issues with authentication components
 *
 * @param Component The component to wrap
 * @returns A component that only renders on the client
 */
export function withClientSideRendering<P extends object>(
  Component: React.ComponentType<P>,
): React.FC<P> {
  const ClientSideOnly = (props: P) => {
    const [isMounted, setIsMounted] = React.useState(false);

    React.useEffect(() => {
      setIsMounted(true);
    }, []);

    // During SSR, don't render anything
    if (isServerSide() || !isMounted) {
      return null;
    }

    // On client side, render the component
    return <Component {...props} />;
  };

  // Set display name for debugging
  const displayName = Component.displayName || Component.name || 'Component';
  ClientSideOnly.displayName = `ClientSideOnly(${displayName})`;

  return ClientSideOnly;
}

/**
 * Error display component for auth failures
 */
interface AuthErrorProps {
  error: Error | string;
  onRetry?: () => void;
}

export function AuthError({ error, onRetry }: AuthErrorProps) {
  const errorMessage = typeof error === 'string' ? error : error.message;

  return (
    <div className="flex flex-col items-center justify-center p-4 rounded-md bg-red-50 text-red-900">
      <h3 className="font-medium mb-2">Authentication Error</h3>
      <p className="text-sm text-red-700 mb-4">{errorMessage}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-red-100 hover:bg-red-200 text-red-800 rounded-md text-sm"
        >
          Retry
        </button>
      )}
    </div>
  );
}
