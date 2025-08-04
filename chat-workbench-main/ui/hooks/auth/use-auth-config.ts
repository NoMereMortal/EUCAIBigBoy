// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Authentication configuration utilities

export interface AuthConfig {
  authority: string;
  client_id: string;
  redirect_uri: string;
  post_logout_redirect_uri: string;
  scope: string;
  response_type: string;
  loadUserInfo: boolean;
  metadata: {
    authorization_endpoint: string;
    token_endpoint: string;
    userinfo_endpoint: string;
    end_session_endpoint: string;
  };
}

// Mock auth config for local development
export const mockAuthConfig: AuthConfig = {
  authority: 'https://mock-authority.example.com',
  client_id: 'mock-client-id',
  redirect_uri:
    typeof window !== 'undefined'
      ? `${window.location.origin}/auth/callback`
      : 'http://localhost:3000/auth/callback',
  post_logout_redirect_uri:
    typeof window !== 'undefined'
      ? window.location.origin
      : 'http://localhost:3000',
  scope: 'openid profile email',
  response_type: 'code',
  loadUserInfo: true,
  metadata: {
    authorization_endpoint:
      'https://mock-authority.example.com/oauth2/authorize',
    token_endpoint: 'https://mock-authority.example.com/oauth2/token',
    userinfo_endpoint: 'https://mock-authority.example.com/oauth2/userInfo',
    end_session_endpoint: 'https://mock-authority.example.com/logout',
  },
};

/**
 * Get the authentication configuration
 */
export const getAuthConfig = (): AuthConfig | null => {
  // During build/SSR, return empty config
  if (typeof window === 'undefined') {
    return null;
  }

  // In browser, return runtime config
  if ((window as any).env?.COGNITO) {
    return (window as any).env.COGNITO;
  }

  // If we don't have auth config, return null
  return null;
};

/**
 * Check if authentication is enabled
 */
export const isAuthEnabled = (): boolean => {
  // In development, we consider auth enabled even without config
  if (process.env.NODE_ENV === 'development') {
    return true;
  }
  return getAuthConfig() !== null;
};

/**
 * Get auth header for API requests
 */
export const getAuthHeader = (auth: any): Record<string, string> => {
  if (auth?.user?.access_token) {
    return {
      Authorization: `Bearer ${auth.user.access_token}`,
    };
  }
  return {};
};
