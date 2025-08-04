// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Authentication-related types

// User profile and authentication types could be defined here
export interface UserProfile {
  user_id: string;
  name?: string;
  email?: string;
  roles?: string[];
  preferences?: Record<string, any>;
  metadata?: Record<string, any>;
}

export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: UserProfile | null;
  error: string | null;
}

export interface AuthConfig {
  authEndpoint: string;
  clientId: string;
  redirectUri: string;
  logoutRedirectUri: string;
  scopes: string[];
}

// Authentication API related types
export interface LoginRequest {
  username: string;
  password: string;
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  tokenType: string;
  user: UserProfile;
}
