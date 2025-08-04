// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import {
  createContext,
  useContext,
  ReactNode,
  useEffect,
  useMemo,
  useCallback,
  useState,
} from 'react';
import {
  AuthProvider as OidcAuthProvider,
  useAuth as useOidcAuth,
} from 'react-oidc-context';
import type { User } from 'oidc-client-ts';
import { getAuthConfig } from '@/hooks/auth/use-auth-config';
import { setAuthObject } from '@/lib/api';
import { authManager } from '@/lib/auth/auth-manager';
import { authInterceptor } from '@/lib/auth/auth-interceptor';
import { getWebSocketClient } from '@/lib/services/websocket-service';
import { useMessageStore } from '@/lib/store/message/message-slice';
import { createAuthSession, deleteAuthSession } from '@/lib/auth-actions';

// Define the simplified auth context type
export interface AuthContextType {
  // Core state from AuthManager
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  userId: string | null;
  error: Error | null;

  // Session state
  isSessionReady: boolean;
  sessionError: string | null;

  // User profile information
  userProfile: {
    id: string;
    firstName: string;
    lastName: string;
    email: string;
    groups: string[];
    isAdmin: boolean;
  } | null;
  isAdmin: boolean;

  // Actions
  login: () => void;
  logout: () => void;
  refreshToken: () => Promise<void>;
}

// Create the context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Provider that combines all auth functionality
export function AuthProvider({ children }: { children: ReactNode }) {
  // Handle server-side rendering
  const isBrowser = typeof window !== 'undefined';

  // Get auth config (only on client)
  const authConfig = isBrowser ? getAuthConfig() : null;

  // Centralized logout logic to be called from handlers
  const handleLogout = () => {
    // This function will be called by the event handlers.
    // The actual logout logic with redirect is in the `logout` function
    // which will be triggered by the authManager.
    authManager.handleLogout();
  };

  // If we're in SSR or don't have config, render a mock provider
  if (!isBrowser || !authConfig) {
    // Create a default auth state for SSR
    const defaultAuthState: AuthContextType = {
      isAuthenticated: false,
      isLoading: false,
      user: null,
      userId: null,
      error: null,
      isSessionReady: false,
      sessionError: null,
      userProfile: null,
      isAdmin: false,
      login: () => {},
      logout: () => {},
      refreshToken: async () => {},
    };

    return (
      <AuthContext.Provider value={defaultAuthState}>
        {children}
      </AuthContext.Provider>
    );
  }

  // For client-side with valid config, use the OIDC provider
  return (
    <OidcAuthProvider {...authConfig}>
      <AuthStateProvider>{children}</AuthStateProvider>
    </OidcAuthProvider>
  );
}

// Inner provider that implements the actual functionality
function AuthStateProvider({ children }: { children: ReactNode }) {
  // Get the base OIDC auth
  const oidcAuth = useOidcAuth();

  // React state that mirrors AuthManager state
  const [authState, setAuthState] = useState(() => authManager.getState());

  // Session state management
  const [isSessionReady, setIsSessionReady] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  // Sync OIDC state with AuthManager
  useEffect(() => {
    authManager.handleOidcState({
      isAuthenticated: oidcAuth.isAuthenticated,
      isLoading: oidcAuth.isLoading,
      user: oidcAuth.user || null,
      error: oidcAuth.error || null,
    });
  }, [
    oidcAuth.isAuthenticated,
    oidcAuth.isLoading,
    oidcAuth.user,
    oidcAuth.error,
  ]);

  // Set up auth interceptor with refresh function
  useEffect(() => {
    authInterceptor.setRefreshTokenFn(async () => {
      await oidcAuth.signinSilent();
    });
  }, [oidcAuth]);

  // Listen for auth state changes from AuthManager and update React state
  useEffect(() => {
    const handleAuthChange = () => {
      const newAuthState = authManager.getState();
      setAuthState(newAuthState);

      // Update API client with auth object
      if (newAuthState.isAuthenticated && newAuthState.user) {
        setAuthObject({ user: newAuthState.user });
      } else {
        setAuthObject(null);
      }
    };

    // Set initial state
    handleAuthChange();

    // Listen for changes
    authManager.on('auth-changed', handleAuthChange);

    return () => {
      authManager.off('auth-changed', handleAuthChange);
    };
  }, []);

  // Initialize WebSocket connection when authenticated
  useEffect(() => {
    if (authState.isAuthenticated && authState.user && !authState.isLoading) {
      console.debug('Initializing WebSocket connection for authenticated user');

      try {
        const ws = getWebSocketClient();
        const messageStore = useMessageStore.getState();

        // Initialize WebSocket handlers first
        if (!messageStore.wsHandlersInitialized) {
          console.debug('Initializing WebSocket handlers');
          messageStore.initializeWsHandlers();
        }

        // Connect WebSocket if not already connected
        if (!ws.isConnected()) {
          console.debug('Connecting to WebSocket');
          ws.connect()
            .then(() => {
              console.debug('WebSocket connected successfully');
            })
            .catch((error) => {
              console.error('Failed to connect WebSocket:', error);
            });
        } else {
          console.debug('WebSocket already connected');
        }
      } catch (error) {
        console.error('Error initializing WebSocket:', error);
      }
    }
  }, [authState.isAuthenticated, authState.user, authState.isLoading]);

  // Create/manage session cookies when auth state changes
  useEffect(() => {
    if (authState.isAuthenticated && authState.user && !authState.isLoading) {
      // Reset session state
      setIsSessionReady(false);
      setSessionError(null);

      // Extract plain data from User object for server action
      const userData = {
        userId: authState.user.profile?.sub || '',
        expiresAt: authState.user.expires_at || 0,
      };

      // User has successfully authenticated - create session cookie
      createAuthSession(userData)
        .then((result) => {
          if (result.success) {
            console.debug('Session cookie created successfully');
            setIsSessionReady(true);
          } else {
            console.error('Failed to create session cookie:', result.error);
            setSessionError(result.error || 'Failed to create session');
          }
        })
        .catch((error) => {
          console.error('Error creating session cookie:', error);
          setSessionError(error.message || 'Session creation failed');
        });
    } else {
      // Reset session state when not authenticated
      setIsSessionReady(false);
      setSessionError(null);
    }
  }, [authState.isAuthenticated, authState.user, authState.isLoading]);

  // Listen for logout events
  useEffect(() => {
    const handleLogout = async () => {
      // Delete session cookie first
      try {
        const result = await deleteAuthSession();
        if (result.success) {
          console.debug('Session cookie deleted successfully');
        } else {
          console.error('Failed to delete session cookie:', result.error);
        }
      } catch (error) {
        console.error('Error deleting session cookie:', error);
      }

      // Disconnect any active websocket connections
      try {
        const ws = getWebSocketClient();
        if (ws.isConnected()) {
          ws.disconnect();
          console.debug('WebSocket connection closed');
        }
      } catch (error) {
        console.error('Error closing WebSocket connection:', error);
      }

      // Reset WebSocket handlers initialization flag
      try {
        const messageStore = useMessageStore.getState();
        messageStore.clearMessages(); // This will reset wsHandlersInitialized to false
        console.debug('WebSocket handlers reset for next login');
      } catch (error) {
        console.error('Error resetting WebSocket handlers:', error);
      }

      // Clear React Query cache
      try {
        const { queryClient } = await import('@/lib/react-query');
        queryClient.clear();
        console.debug('Query cache cleared');
      } catch (error) {
        console.error('Error clearing query cache:', error);
      }

      // Dispatch custom event for other components to clean up
      if (typeof window !== 'undefined') {
        const clearEvent = new CustomEvent('auth:logout');
        window.dispatchEvent(clearEvent);
        console.debug('Auth logout event dispatched for state clearing');
      }
    };

    authManager.on('logout', handleLogout);

    return () => {
      authManager.off('logout', handleLogout);
    };
  }, []);

  // Auth actions
  const login = useCallback(() => {
    oidcAuth.signinRedirect();
  }, [oidcAuth]);

  const logout = useCallback(() => {
    try {
      console.debug('Logging out and clearing application state...');

      // Notify AuthManager about logout to trigger cleanup
      authManager.handleLogout();

      // Clear auth interceptor state
      authInterceptor.reset();

      // Finally, redirect to OIDC provider to end session
      oidcAuth.signoutRedirect();

      console.debug('Redirecting to OIDC provider for logout.');
    } catch (error) {
      console.error('Error during logout:', error);
      // Still attempt to redirect even if other cleanup fails
      oidcAuth.signoutRedirect();
    }
  }, [oidcAuth]);

  const refreshToken = useCallback(async () => {
    await authManager.refreshToken(async () => {
      await oidcAuth.signinSilent();
    });
  }, [oidcAuth]);

  // Memoize auth context value to prevent unnecessary re-renders
  const authContextValue = useMemo<AuthContextType>(
    () => ({
      // Core state from AuthManager (via React state)
      isAuthenticated: authState.isAuthenticated,
      isLoading: authState.isLoading,
      user: authState.user,
      userId: authState.userId,
      error: authState.error,

      // Session state
      isSessionReady,
      sessionError,

      // User profile information
      userProfile: authState.userProfile,
      isAdmin: authState.isAdmin,

      // Actions
      login,
      logout,
      refreshToken,
    }),
    [
      authState.isAuthenticated,
      authState.isLoading,
      authState.user,
      authState.userId,
      authState.error,
      isSessionReady,
      sessionError,
      authState.userProfile,
      authState.isAdmin,
      login,
      logout,
      refreshToken,
    ],
  );

  return (
    <AuthContext.Provider value={authContextValue}>
      {children}
    </AuthContext.Provider>
  );
}

// Main hook to use auth context
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
