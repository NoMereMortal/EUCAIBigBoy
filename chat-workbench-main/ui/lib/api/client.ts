// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { getApiConfig } from '@/lib/constants';
import { getAuthHeader } from '@/hooks/auth';
import { authInterceptor } from '@/lib/auth/auth-interceptor';
import { authManager } from '@/lib/auth/auth-manager';

// More robust server-side rendering detection
export const isServer = () => typeof window === 'undefined';

import type { User } from 'oidc-client-ts';

// Store the auth object for API calls - will be managed by AuthManager
export let authObject: { user?: User } | null = null;

// Simple function to set the auth object
export const setAuthObject = (auth: { user?: User } | null) => {
  authObject = auth;
};

// Add immediate debug log to confirm this code is loaded
console.log(
  'API Client loaded with auth fix - timestamp:',
  new Date().toISOString(),
);

// Function to get auth headers
export const getHeaders = (contentType = 'application/json') => {
  const headers: Record<string, string> = {
    'Content-Type': contentType,
  };

  console.log('getHeaders called, checking for auth token...');

  // Primary: Use centralized AuthManager for consistent auth state
  const authState = authManager.getState();
  if (authState.isAuthenticated && authState.user && authState.userId) {
    // Add X-User-ID header from centralized auth state (works with Cognito sub claim)
    headers['X-User-ID'] = authState.userId;

    if (authState.user.access_token) {
      headers['Authorization'] = `Bearer ${authState.user.access_token}`;
      console.log('Using token from AuthManager');
      return headers;
    }
  }

  // Fallback: Try legacy authObject for backward compatibility
  if (authObject) {
    const authHeaders = getAuthHeader(authObject);
    Object.assign(headers, authHeaders);

    // Add X-User-ID header if we have a user (Cognito sub claim)
    if (authObject.user?.profile?.sub) {
      headers['X-User-ID'] = authObject.user.profile.sub;
    }

    if (authObject.user?.access_token) {
      headers['Authorization'] = `Bearer ${authObject.user.access_token}`;
      console.log('Using token from legacy authObject');
      return headers;
    }
  }

  // Final fallback: Get token directly from sessionStorage (for immediate use)
  try {
    const authData = sessionStorage.getItem(
      'oidc.user:http://localhost:8080/realms/chat-workbench:chat-workbench-ui',
    );
    if (authData) {
      const parsedAuth = JSON.parse(authData);
      if (parsedAuth?.access_token) {
        headers['Authorization'] = `Bearer ${parsedAuth.access_token}`;
        // Try to extract user ID from sessionStorage token for X-User-ID header
        if (parsedAuth?.profile?.sub) {
          headers['X-User-ID'] = parsedAuth.profile.sub;
        }
        console.log('Using token from sessionStorage fallback');
        return headers;
      }
    }
  } catch (error) {
    console.warn('Failed to read token from sessionStorage:', error);
  }

  console.log('No auth token found');
  return headers;
};

/**
 * Core HTTP client with consistent error handling
 */
export class ApiClient {
  private baseUrl: string;
  private apiVersion: string;

  constructor() {
    const config = getApiConfig();
    this.baseUrl = config.BASE_URL;
    this.apiVersion = config.API_VERSION;
  }

  /**
   * Builds a complete API URL
   */
  buildUrl(
    path: string,
    params?: Record<string, string | number | boolean>,
  ): string {
    // First get the current window location if we're in the browser
    const currentDomain = !isServer() ? window.location.origin : null;

    // Check if this is a localhost URL - more comprehensive check
    const isLocalhost =
      this.baseUrl.includes('localhost') ||
      this.baseUrl.includes('127.0.0.1') ||
      this.baseUrl.includes('0.0.0.0') ||
      (currentDomain && currentDomain.includes('localhost'));

    console.debug(
      `API endpoint: ${this.baseUrl}, isLocalhost: ${isLocalhost}, path: ${path}, current domain: ${currentDomain || 'none'}`,
    );

    // If it's a localhost URL and doesn't have a protocol, add http://
    let effectiveBaseUrl = this.baseUrl;
    if (
      isLocalhost &&
      effectiveBaseUrl &&
      !effectiveBaseUrl.startsWith('http')
    ) {
      effectiveBaseUrl = `http://${effectiveBaseUrl}`;
      console.debug(`Adding protocol to localhost URL: ${effectiveBaseUrl}`);
    }

    // Check if baseUrl is the same as the current domain or empty
    // If so, we can use a relative URL since the ALB will route /api/ to the API server
    const isSameDomain =
      !isLocalhost &&
      currentDomain &&
      (this.baseUrl === currentDomain ||
        this.baseUrl === '' ||
        // Handle case where baseUrl might have trailing slash
        this.baseUrl === `${currentDomain}/` ||
        // Also handle the case where it's explicitly set to the same domain
        (this.baseUrl && new URL(this.baseUrl).origin === currentDomain));

    console.debug(
      `Using API endpoint: ${this.baseUrl}${isSameDomain ? ' (same domain)' : ''}, isSameDomain: ${isSameDomain}`,
    );

    // Special handling for localhost - always use the full URL
    if (isLocalhost) {
      const localhostUrl = `${effectiveBaseUrl}/api/${this.apiVersion}/${path}`;
      console.debug(
        `Using localhost API endpoint - preserving full URL: ${localhostUrl}`,
      );
      return localhostUrl;
    }

    // When baseUrl is the same as current domain, use a relative URL so the ALB can route properly
    // This is also important to prevent mixed content issues
    let url = isSameDomain
      ? `/api/${this.apiVersion}/${path}`
      : `${this.baseUrl}/api/${this.apiVersion}/${path}`;

    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        // Only add parameter if it has a real value (not empty string, null or undefined)
        if (value !== undefined && value !== null && value !== '') {
          searchParams.append(key, String(value));
        }
      });

      const queryString = searchParams.toString();
      if (queryString) {
        url += `?${queryString}`;
      }
    }

    return url;
  }

  /**
   * Check and ensure authentication before making requests
   * Attempts to refresh authentication if needed
   */
  private async ensureAuthenticated(): Promise<boolean> {
    try {
      // Check if auth is required but missing
      const { isAuthenticated, user } = authManager.getState();

      if (!isAuthenticated || !user) {
        console.log('Not authenticated, attempting to refresh auth...');

        // We can't directly trigger a token refresh from here since emit is private
        // Instead, we'll check if the token is about to expire and let the interceptor
        // handle the 401 response if needed

        // Check for token expiration
        const tokenExpired =
          !user || !user.expires_at || user.expires_at * 1000 < Date.now();

        if (tokenExpired) {
          console.log('Token expired or missing, continuing with request.');
          // The request will likely fail with 401, and the interceptor will handle it
          return true; // Allow the request to proceed to the interceptor
        }

        // If we get here, something else is wrong with authentication
        console.error('Authentication state is invalid');
        return false;
      }

      // Check token expiration
      if (user.expires_at && user.expires_at * 1000 < Date.now()) {
        console.log(
          'Token has expired, continuing to let interceptor handle refresh',
        );
        // Let the request go through and the interceptor will handle the 401
        return true;
      }

      // Already authenticated with valid token
      return true;
    } catch (error) {
      console.error('Error checking authentication:', error);
      return false;
    }
  }

  /**
   * Generic request method with error handling
   */
  async request<T>(
    path: string,
    method: string = 'GET',
    data?: any,
    params?: Record<string, string | number | boolean>,
    customHeaders?: Record<string, string>,
  ): Promise<T> {
    // Skip API calls during server-side rendering to prevent hydration mismatches
    if (isServer()) {
      console.debug(`Skipping API call in SSR: ${path}`);
      // Return an empty response that matches the expected type
      return {} as T;
    }

    // Ensure we're authenticated before making the request
    const isAuthenticated = await this.ensureAuthenticated();
    if (!isAuthenticated) {
      throw new Error('Authentication required. Please log in again.');
    }

    // Validate params to ensure we don't send empty user_id
    if (params && 'user_id' in params) {
      const userId = params.user_id;
      if (!userId || userId === '') {
        throw new Error('Authentication required: No user ID provided');
      }
    }

    const url = this.buildUrl(path, params);

    const headers = {
      ...getHeaders(),
      ...(customHeaders || {}),
    };

    const init: RequestInit = { method, headers };

    if (data) {
      init.body = JSON.stringify(data);
    }

    try {
      // Use auth interceptor for all requests to handle 401s
      const response = await authInterceptor.interceptFetch(url, init);

      if (!response.ok) {
        // Special case for 422 in chat endpoints
        if (response.status === 422 && path.startsWith('chat/')) {
          return Promise.reject({
            type: 'INVALID_CHAT_ID',
            chatId: path.split('/')[1],
          });
        }

        console.error(
          `API request failed: ${response.status} ${response.statusText}`,
          { url, method, data },
        );
        throw new Error(
          `API request failed: ${response.status} ${response.statusText}`,
        );
      }

      // If response is empty, return empty object
      if (response.status === 204) {
        return {} as T;
      }

      return response.json();
    } catch (error) {
      console.error(`API request error for ${url}:`, error);
      throw error;
    }
  }

  /**
   * GET request helper
   */
  async get<T>(
    path: string,
    params?: Record<string, string | number | boolean>,
    customHeaders?: Record<string, string>,
  ): Promise<T> {
    return this.request<T>(path, 'GET', undefined, params, customHeaders);
  }

  /**
   * POST request helper
   */
  async post<T>(
    path: string,
    data: any,
    params?: Record<string, string | number | boolean>,
    customHeaders?: Record<string, string>,
  ): Promise<T> {
    return this.request<T>(path, 'POST', data, params, customHeaders);
  }

  /**
   * PUT request helper
   */
  async put<T>(
    path: string,
    data: any,
    params?: Record<string, string | number | boolean>,
    customHeaders?: Record<string, string>,
  ): Promise<T> {
    return this.request<T>(path, 'PUT', data, params, customHeaders);
  }

  /**
   * DELETE request helper
   */
  async delete<T>(
    path: string,
    params?: Record<string, string | number | boolean>,
    customHeaders?: Record<string, string>,
  ): Promise<T> {
    return this.request<T>(path, 'DELETE', undefined, params, customHeaders);
  }

  /**
   * Stream request helper
   */
  async stream(
    path: string,
    data: any,
    params?: Record<string, string | number | boolean>,
  ): Promise<ReadableStream<Uint8Array> | null> {
    // Skip streaming in server-side rendering
    if (isServer()) {
      console.debug(`Skipping stream request in SSR: ${path}`);
      return null;
    }

    // Ensure we're authenticated before making the request
    const isAuthenticated = await this.ensureAuthenticated();
    if (!isAuthenticated) {
      throw new Error('Authentication required. Please log in again.');
    }

    const url = this.buildUrl(path, params);

    const headers = {
      ...getHeaders(),
      Accept: 'text/event-stream',
    };

    const init: RequestInit = {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
    };

    const response = await authInterceptor.interceptFetch(url, init);

    if (!response.ok) {
      throw new Error(
        `Stream request failed: ${response.status} ${response.statusText}`,
      );
    }

    return response.body;
  }

  /**
   * FormData POST request helper
   * Special handling for multipart/form-data uploads that can't use JSON.stringify
   */
  async postFormData<T>(
    path: string,
    formData: FormData,
    params?: Record<string, string | number | boolean>,
  ): Promise<T> {
    // Skip API calls during server-side rendering
    if (isServer()) {
      console.debug(`Skipping FormData API call in SSR: ${path}`);
      return {} as T;
    }

    // Ensure we're authenticated before making the request
    const isAuthenticated = await this.ensureAuthenticated();
    if (!isAuthenticated) {
      throw new Error('Authentication required. Please log in again.');
    }

    const url = this.buildUrl(path, params);

    // Get auth headers but explicitly skip Content-Type
    const headers = getHeaders();
    delete headers['Content-Type']; // Let browser set this for FormData with boundary

    const init: RequestInit = {
      method: 'POST',
      headers,
      body: formData,
    };

    try {
      console.debug(`Making FormData POST request to: ${url}`);
      const response = await authInterceptor.interceptFetch(url, init);

      if (!response.ok) {
        // Handle error response
        try {
          const errorData = await response.json();
          console.error(
            `FormData API request failed: ${response.status}`,
            errorData,
          );
          throw new Error(
            errorData.detail ||
              `FormData API request failed: ${response.status}`,
          );
        } catch (parseError) {
          // If response can't be parsed as JSON
          throw new Error(
            `FormData API request failed: ${response.status} ${response.statusText}`,
          );
        }
      }

      // If response is empty, return empty object
      if (response.status === 204) {
        return {} as T;
      }

      return response.json();
    } catch (error) {
      console.error(`FormData API request error for ${url}:`, error);
      throw error;
    }
  }
}

// Export a singleton instance
export const apiClient = new ApiClient();
