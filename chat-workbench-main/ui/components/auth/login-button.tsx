// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, forwardRef } from 'react';
import { useAuth } from '@/hooks/auth';
import { Button } from '@/components/ui/button';
import { LogIn, Loader2, AlertTriangle } from 'lucide-react';
import { isServerSide } from '@/hooks/auth/utils';

interface LoginButtonProps {
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

export const LoginButton = forwardRef<HTMLButtonElement, LoginButtonProps>(
  (
    {
      className,
      label = 'Sign In',
      variant = 'ghost',
      size = 'sm',
      onClick,
      ...props
    },
    ref,
  ) => {
    const { isAuthenticated, isLoading, login } = useAuth();
    const [error, setError] = useState<string | null>(null);
    const [isAttemptingLogin, setIsAttemptingLogin] = useState(false);

    // Handle server-side rendering
    if (isServerSide()) {
      return null;
    }

    // Don't show if already authenticated
    if (isAuthenticated) {
      return null; // Let LogoutButton handle this case
    }

    const handleLogin = async (e: React.MouseEvent<HTMLButtonElement>) => {
      try {
        setIsAttemptingLogin(true);
        setError(null);

        // If there's a parent onClick handler, call it first
        if (onClick) {
          onClick(e);
        }

        login();
      } catch (err) {
        setError('Login failed. Please try again.');
        console.error('Login error:', err);
      } finally {
        // If login redirects, this won't execute
        // but it's here for completeness
        setIsAttemptingLogin(false);
      }
    };

    if (isLoading || isAttemptingLogin) {
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
          Loading...
        </Button>
      );
    }

    if (error) {
      return (
        <Button
          variant="destructive"
          size={size}
          onClick={handleLogin}
          className={className}
          title={error}
          ref={ref}
          {...props}
        >
          <AlertTriangle className="mr-2 h-4 w-4" />
          Retry
        </Button>
      );
    }

    return (
      <Button
        variant={variant}
        size={size}
        onClick={handleLogin}
        className={className}
        ref={ref}
        {...props}
      >
        <LogIn className="mr-2 h-4 w-4" />
        {label}
      </Button>
    );
  },
);

// Add display name for better debugging
LoginButton.displayName = 'LoginButton';
