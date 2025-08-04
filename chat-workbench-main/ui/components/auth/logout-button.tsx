// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, forwardRef } from 'react';
import { useAuth } from '@/hooks/auth';
import { Button } from '@/components/ui/button';
import { LogOut, Loader2, AlertTriangle } from 'lucide-react';
import { isServerSide } from '@/hooks/auth/utils';

interface LogoutButtonProps {
  className?: string;
  label?: string;
  variant?:
    | 'default'
    | 'destructive'
    | 'outline'
    | 'secondary'
    | 'ghost'
    | 'link';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  // Allow any other props that might come from parent components like DropdownMenuItem
  [key: string]: any;
}

export const LogoutButton = forwardRef<HTMLButtonElement, LogoutButtonProps>(
  (
    {
      className,
      label = 'Sign Out',
      variant = 'ghost',
      size = 'sm',
      onClick,
      ...props
    },
    ref,
  ) => {
    const { isAuthenticated, logout } = useAuth();
    const [isLoggingOut, setIsLoggingOut] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // During SSR, don't render anything
    if (isServerSide()) {
      return null;
    }

    // Only show when authenticated
    if (!isAuthenticated) {
      return null;
    }

    const handleSignOut = async (e: React.MouseEvent<HTMLButtonElement>) => {
      try {
        setIsLoggingOut(true);
        setError(null);

        // If there's a parent onClick handler, call it first
        if (onClick) {
          onClick(e);
        }

        // Perform logout
        await logout();
        // Note: After logout, the page will likely redirect or refresh
      } catch (err) {
        console.error('Logout error:', err);
        setError('Sign out failed');
        setIsLoggingOut(false);
      }
    };

    if (isLoggingOut) {
      return (
        <Button
          variant={variant}
          size={size}
          disabled
          className={className}
          ref={ref}
          {...props}
        >
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Signing out...
        </Button>
      );
    }

    if (error) {
      return (
        <Button
          variant="destructive"
          size={size}
          onClick={handleSignOut}
          className={className}
          title={error}
          ref={ref}
          {...props}
        >
          <AlertTriangle className="mr-2 h-4 w-4" />
          Retry sign out
        </Button>
      );
    }

    return (
      <Button
        variant={variant}
        size={size}
        onClick={handleSignOut}
        className={className}
        ref={ref}
        {...props}
      >
        <LogOut className="mr-2 h-4 w-4" />
        {label}
      </Button>
    );
  },
);

// Add display name for better debugging
LogoutButton.displayName = 'LogoutButton';
