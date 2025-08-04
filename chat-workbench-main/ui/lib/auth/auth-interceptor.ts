// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { authManager } from '@/lib/auth/auth-manager';

/**
 * HTTP Request/Response Interceptor for Authentication
 *
 * This class provides:
 * - Unified 401 handling
 * - Request queuing during token refresh
 * - Automatic retry logic
 * - Request deduplication
 */

interface QueuedRequest {
  execute: () => Promise<Response>;
  resolve: (value: Response) => void;
  reject: (reason: any) => void;
  url: string;
  init: RequestInit;
}

export class AuthInterceptor {
  private isRefreshing = false;
  private requestQueue: QueuedRequest[] = [];
  private refreshTokenFn: (() => Promise<void>) | null = null;

  constructor() {
    // Listen for auth state changes
    authManager.on('token-refreshed', () => {
      this.processQueue();
    });

    authManager.on('auth-error', () => {
      this.failQueue(new Error('Authentication failed'));
    });
  }

  /**
   * Set the token refresh function (will be provided by auth provider)
   */
  setRefreshTokenFn(refreshFn: () => Promise<void>) {
    this.refreshTokenFn = refreshFn;
  }

  /**
   * Intercept fetch requests to handle 401 errors
   */
  async interceptFetch(
    url: string | URL | Request,
    init?: RequestInit,
  ): Promise<Response> {
    // Add X-User-ID header to all requests if available
    const currentInit = init || {};
    const headers = new Headers(currentInit.headers || {});

    // Get user ID from authManager state
    const { userId } = authManager.getState();

    if (userId) {
      // Use authenticated user ID
      headers.set('X-User-ID', userId);
    } else {
      // Log warning for missing user ID - no fallbacks
      console.warn('No user ID available. Authentication required.');
    }

    // Update the init object with the modified headers
    currentInit.headers = headers;

    // If we're currently refreshing tokens, queue the request
    if (this.isRefreshing) {
      return this.queueRequest(url, currentInit);
    }

    // Make the initial request
    const response = await fetch(url, currentInit);

    // Handle 401 responses
    if (response.status === 401) {
      return this.handle401(url, currentInit, response);
    }

    return response;
  }

  /**
   * Handle 401 Unauthorized responses
   */
  private async handle401(
    url: string | URL | Request,
    init: RequestInit | undefined,
    originalResponse: Response,
  ): Promise<Response> {
    console.debug('Handling 401 response for:', url);

    // If we're already refreshing, queue this request
    if (this.isRefreshing) {
      return this.queueRequest(url, init);
    }

    // Check if we have a refresh function
    if (!this.refreshTokenFn) {
      console.error('No refresh token function available');
      return originalResponse; // Return original 401 response
    }

    // Start the refresh process
    this.isRefreshing = true;

    try {
      // Attempt to refresh the token
      await authManager.refreshToken(this.refreshTokenFn);

      // Token refresh successful, retry the original request
      console.debug('Token refreshed, retrying original request');
      const retryResponse = await fetch(url, init);

      // Process any queued requests
      this.processQueue();

      return retryResponse;
    } catch (error) {
      console.error('Token refresh failed:', error);

      // Fail all queued requests
      this.failQueue(
        error instanceof Error ? error : new Error('Token refresh failed'),
      );

      // Return the original 401 response
      return originalResponse;
    } finally {
      this.isRefreshing = false;
    }
  }

  /**
   * Queue a request during token refresh
   */
  private queueRequest(
    url: string | URL | Request,
    init?: RequestInit,
  ): Promise<Response> {
    return new Promise<Response>((resolve, reject) => {
      const queuedRequest: QueuedRequest = {
        execute: () => fetch(url, init),
        resolve,
        reject,
        url: url.toString(),
        init: init || {},
      };

      this.requestQueue.push(queuedRequest);
      console.debug(
        `Request queued: ${url} (queue length: ${this.requestQueue.length})`,
      );
    });
  }

  /**
   * Process all queued requests after successful token refresh
   */
  private processQueue() {
    console.debug(`Processing ${this.requestQueue.length} queued requests`);

    const queue = [...this.requestQueue];
    this.requestQueue = [];

    queue.forEach(async ({ execute, resolve, reject, url }) => {
      try {
        console.debug(`Executing queued request: ${url}`);
        const response = await execute();
        resolve(response);
      } catch (error) {
        console.error(`Queued request failed: ${url}`, error);
        reject(error);
      }
    });
  }

  /**
   * Fail all queued requests
   */
  private failQueue(error: Error) {
    console.debug(`Failing ${this.requestQueue.length} queued requests`);

    const queue = [...this.requestQueue];
    this.requestQueue = [];

    queue.forEach(({ reject, url }) => {
      console.debug(`Failing queued request: ${url}`);
      reject(error);
    });
  }

  /**
   * Get queue status (for debugging)
   */
  getQueueStatus() {
    return {
      isRefreshing: this.isRefreshing,
      queueLength: this.requestQueue.length,
      hasRefreshFn: !!this.refreshTokenFn,
    };
  }

  /**
   * Clear the queue (for cleanup)
   */
  clearQueue() {
    this.failQueue(new Error('Queue cleared'));
  }

  /**
   * Reset the interceptor state
   */
  reset() {
    this.isRefreshing = false;
    this.clearQueue();
    this.refreshTokenFn = null;
  }
}

// Export singleton instance
export const authInterceptor = new AuthInterceptor();
