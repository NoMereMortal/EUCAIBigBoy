// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use server';

import { createSessionCookie, deleteSessionCookie } from '@/lib/session';

export interface UserSessionData {
  userId: string;
  expiresAt: number;
}

/**
 * Server Action: Create session cookie after OIDC authentication
 */
export async function createAuthSession(userData: UserSessionData) {
  try {
    await createSessionCookie(userData);
    return { success: true };
  } catch (error) {
    console.error('Failed to create session cookie:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * Server Action: Delete session cookie on logout
 */
export async function deleteAuthSession() {
  try {
    await deleteSessionCookie();
    return { success: true };
  } catch (error) {
    console.error('Failed to delete session cookie:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}
