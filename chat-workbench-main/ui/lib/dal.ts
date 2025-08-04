// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import 'server-only';
import { cache } from 'react';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { decrypt } from '@/lib/session';

export interface VerifiedSession {
  isAuth: true;
  userId: string;
}

/**
 * Data Access Layer - Verify user session
 *
 * This function provides secure session verification for Server Components,
 * Server Actions, and Route Handlers. It checks both the HTTP cookie and
 * coordinates with the client-side OIDC state.
 *
 * Uses React's cache to avoid duplicate verification during a render pass.
 */
export const verifySession = cache(async (): Promise<VerifiedSession> => {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get('session')?.value;
  const session = await decrypt(sessionCookie);

  if (!session?.userId) {
    console.debug('No valid session found, redirecting to login');
    redirect('/login');
  }

  // Check if session is expired
  if (session.expiresAt) {
    const expiryDate =
      typeof session.expiresAt === 'number'
        ? new Date(session.expiresAt * 1000)
        : new Date(session.expiresAt);
    if (expiryDate < new Date()) {
      console.debug('Session expired, redirecting to login');
      redirect('/login');
    }
  }

  console.debug('Session verified for user:', session.userId);
  return { isAuth: true, userId: session.userId };
});

/**
 * Get current session without redirecting
 * Useful for optional auth checks
 */
export const getCurrentSession = cache(async () => {
  try {
    const cookieStore = await cookies();
    const sessionCookie = cookieStore.get('session')?.value;
    const session = await decrypt(sessionCookie);

    if (!session?.userId) {
      return null;
    }

    // Check if session is expired
    if (session.expiresAt) {
      const expiryDate =
        typeof session.expiresAt === 'number'
          ? new Date(session.expiresAt * 1000)
          : new Date(session.expiresAt);
      if (expiryDate < new Date()) {
        return null;
      }
    }

    return { isAuth: true, userId: session.userId };
  } catch (error) {
    console.debug('Error getting current session:', error);
    return null;
  }
});

/**
 * Check if user is authenticated (optimistic check)
 * Returns boolean without redirecting
 */
export const isAuthenticated = cache(async (): Promise<boolean> => {
  const session = await getCurrentSession();
  return session?.isAuth ?? false;
});
