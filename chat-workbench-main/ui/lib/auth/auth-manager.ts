// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import type { User } from 'oidc-client-ts';

/**
 * Centralized Authentication Manager
 *
 * This class coordinates all authentication operations:
 * - Token lifecycle management
 * - Automatic refresh with proper locking
 * - Auth state synchronization
 * - Event emission for state changes
 */

export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  userId: string | null;
  userProfile: {
    id: string;
    firstName: string;
    lastName: string;
    email: string;
    groups: string[];
    isAdmin: boolean;
  } | null;
  isAdmin: boolean;
  error: Error | null;
}

export type AuthEventType =
  | 'auth-changed'
  | 'token-refreshed'
  | 'auth-error'
  | 'logout';

export interface AuthEvent {
  type: AuthEventType;
  data?: any;
}

export class AuthManager {
  private authState: AuthState = {
    isAuthenticated: false,
    isLoading: true,
    user: null,
    userId: null,
    userProfile: null,
    isAdmin: false,
    error: null,
  };

  private listeners: Map<AuthEventType, Set<(event: AuthEvent) => void>> =
    new Map();
  private refreshPromise: Promise<void> | null = null;
  private refreshTimer: NodeJS.Timeout | null = null;

  constructor() {
    // Initialize event listener maps
    this.listeners.set('auth-changed', new Set());
    this.listeners.set('token-refreshed', new Set());
    this.listeners.set('auth-error', new Set());
    this.listeners.set('logout', new Set());
  }

  /**
   * Get current auth state
   */
  getState(): AuthState {
    return { ...this.authState };
  }

  /**
   * Update auth state and emit events
   */
  updateState(newState: Partial<AuthState>) {
    const oldState = { ...this.authState };
    this.authState = { ...this.authState, ...newState };

    // Extract user ID and profile from user if available
    if (this.authState.user?.profile?.sub) {
      this.authState.userId = this.authState.user.profile.sub;

      // Extract user profile information
      const profile = this.authState.user.profile;
      const groups = this.extractGroups(profile);
      const isAdmin = this.checkIfUserIsAdmin(groups, profile);

      this.authState.userProfile = {
        id: profile.sub,
        firstName: profile.given_name || profile.name?.split(' ')[0] || '',
        lastName:
          profile.family_name ||
          profile.name?.split(' ').slice(1).join(' ') ||
          '',
        email: profile.email || '',
        groups,
        isAdmin,
      };
      this.authState.isAdmin = isAdmin;
    } else {
      this.authState.userId = null;
      this.authState.userProfile = null;
      this.authState.isAdmin = false;
    }

    console.debug('State updated:', this.authState);

    // Emit auth-changed event if authentication status changed
    if (
      oldState.isAuthenticated !== this.authState.isAuthenticated ||
      oldState.user?.access_token !== this.authState.user?.access_token
    ) {
      this.emit('auth-changed', this.authState);
    }

    // Schedule token refresh if user is authenticated
    this.scheduleTokenRefresh();
  }

  /**
   * Handle OIDC auth state changes
   */
  handleOidcState(oidcState: {
    isAuthenticated: boolean;
    isLoading: boolean;
    user: User | null;
    error?: Error | null;
  }) {
    this.updateState({
      isAuthenticated: oidcState.isAuthenticated,
      isLoading: oidcState.isLoading,
      user: oidcState.user,
      error: oidcState.error || null,
    });
  }

  /**
   * Perform token refresh with proper locking
   */
  async refreshToken(oidcRefreshFn: () => Promise<void>): Promise<void> {
    // Prevent concurrent refreshes
    if (this.refreshPromise) {
      console.debug('Token refresh already in progress, waiting...');
      return this.refreshPromise;
    }

    this.refreshPromise = this.performRefresh(oidcRefreshFn);

    try {
      await this.refreshPromise;
    } finally {
      this.refreshPromise = null;
    }
  }

  private async performRefresh(
    oidcRefreshFn: () => Promise<void>,
  ): Promise<void> {
    try {
      console.debug('Starting token refresh');
      await oidcRefreshFn();
      console.debug('Token refresh successful');
      this.emit('token-refreshed', { success: true });
    } catch (error) {
      const refreshError =
        error instanceof Error ? error : new Error('Token refresh failed');
      console.error('Token refresh failed:', refreshError);

      this.updateState({ error: refreshError });
      this.emit('auth-error', { error: refreshError });
      throw refreshError;
    }
  }

  /**
   * Schedule automatic token refresh before expiration
   */
  private scheduleTokenRefresh() {
    // Clear existing timer
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }

    // Only schedule if authenticated and have expiration time
    if (!this.authState.isAuthenticated || !this.authState.user?.expires_at) {
      return;
    }

    const expiresAt = this.authState.user.expires_at * 1000; // Convert to milliseconds
    const currentTime = Date.now();
    const refreshBuffer = 5 * 60 * 1000; // 5 minutes before expiration
    const timeToRefresh = Math.max(0, expiresAt - currentTime - refreshBuffer);

    this.refreshTimer = setTimeout(() => {
      console.debug('Auto-refreshing token before expiration');
      // This will be called by the auth provider with the actual refresh function
      this.emit('auth-changed', { ...this.authState, needsRefresh: true });
    }, timeToRefresh);

    console.debug(
      `Token refresh scheduled in ${Math.round(timeToRefresh / 1000 / 60)} minutes`,
    );
  }

  /**
   * Handle logout
   */
  handleLogout() {
    console.debug('Handling logout');

    // Clear refresh timer
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }

    // Reset state
    this.updateState({
      isAuthenticated: false,
      isLoading: false,
      user: null,
      userId: null,
      error: null,
    });

    // Emit logout event
    this.emit('logout', {});
  }

  /**
   * Event system
   */
  on(eventType: AuthEventType, callback: (event: AuthEvent) => void) {
    const listeners = this.listeners.get(eventType);
    if (listeners) {
      listeners.add(callback);
    }
  }

  off(eventType: AuthEventType, callback: (event: AuthEvent) => void) {
    const listeners = this.listeners.get(eventType);
    if (listeners) {
      listeners.delete(callback);
    }
  }

  private emit(eventType: AuthEventType, data?: any) {
    const listeners = this.listeners.get(eventType);
    if (listeners) {
      const event: AuthEvent = { type: eventType, data };
      listeners.forEach((callback) => {
        try {
          callback(event);
        } catch (error) {
          console.error(`Error in event listener for ${eventType}:`, error);
        }
      });
    }
  }

  /**
   * Extract groups from user profile
   */
  private extractGroups(profile: any): string[] {
    const groups: string[] = [];

    // Check various common group claim names
    const possibleGroupClaims = [
      'groups',
      'cognito:groups',
      'custom:groups',
      'roles',
    ];

    for (const claim of possibleGroupClaims) {
      if (profile[claim]) {
        if (Array.isArray(profile[claim])) {
          groups.push(...profile[claim]);
        } else if (typeof profile[claim] === 'string') {
          groups.push(profile[claim]);
        }
      }
    }

    return Array.from(new Set(groups)); // Remove duplicates
  }

  /**
   * Check if user has admin privileges
   */
  private checkIfUserIsAdmin(groups: string[], profile: any): boolean {
    // Check for admin groups
    const adminGroups = ['admin', 'administrators', 'Admin', 'Administrators'];
    const hasAdminGroup = groups.some((group) => adminGroups.includes(group));

    if (hasAdminGroup) return true;

    // Check for admin role in profile
    if (profile.role === 'admin' || profile['custom:role'] === 'admin') {
      return true;
    }

    return false;
  }

  /**
   * Cleanup method
   */
  destroy() {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }

    // Clear all listeners
    this.listeners.forEach((listeners) => listeners.clear());

    this.refreshPromise = null;
  }
}

// Export singleton instance
export const authManager = new AuthManager();
