// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Re-export all auth-related hooks and utilities
// This provides a centralized import for consumers

// Provider and main hook
export {
  AuthProvider,
  useAuth,
  type AuthContextType,
} from './use-auth-provider';

// Configuration utilities
export {
  getAuthConfig,
  isAuthEnabled,
  getAuthHeader,
  type AuthConfig,
} from './use-auth-config';
