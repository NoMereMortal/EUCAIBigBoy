// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { decrypt } from '@/lib/session';

/**
 * Authentication middleware for protected routes
 *
 * This middleware provides optimistic auth checks by verifying
 * session cookies before client-side code runs. It follows Next.js
 * best practices for middleware-based authentication.
 *
 * Integrates with OIDC authentication via session cookie bridge.
 */
export async function middleware(request: NextRequest) {
  // Check if we're trying to access a protected route
  const isProtectedRoute = request.nextUrl.pathname.startsWith('/chat');

  // Allow non-protected routes to pass through
  if (!isProtectedRoute) {
    return NextResponse.next();
  }

  // Skip during build time to prevent build errors
  const isBuildTime =
    typeof process !== 'undefined' &&
    process.env.NEXT_PHASE === 'phase-production-build';
  if (isBuildTime) {
    return NextResponse.next();
  }

  // Option to bypass auth check in development only
  const bypassAuth =
    process.env.NODE_ENV === 'development' &&
    process.env.NEXT_PUBLIC_BYPASS_AUTH === 'true';
  if (bypassAuth) {
    console.debug('Auth bypassed in development mode');
    return NextResponse.next();
  }

  // Check for session cookie (optimistic check)
  const sessionCookie = request.cookies.get('session')?.value;

  if (!sessionCookie) {
    console.debug('No session cookie found, redirecting to home');
    return NextResponse.redirect(new URL('/', request.url));
  }

  // Verify session cookie
  try {
    const session = await decrypt(sessionCookie);

    if (!session?.userId) {
      console.debug('Invalid session cookie, redirecting to home');
      return NextResponse.redirect(new URL('/', request.url));
    }

    // Check if session is expired
    if (session.expiresAt) {
      const expiryDate =
        typeof session.expiresAt === 'number'
          ? new Date(session.expiresAt * 1000)
          : new Date(session.expiresAt);
      if (expiryDate < new Date()) {
        console.debug('Session expired, redirecting to home');
        return NextResponse.redirect(new URL('/', request.url));
      }
    }

    // Session is valid - allow access
    console.debug('Valid session found for user:', session.userId);
    return NextResponse.next();
  } catch (error) {
    console.error('Session verification failed:', error);

    // Provide more specific error logging for debugging
    if (error instanceof Error) {
      if (
        error.message.includes(
          'Session secret not available in middleware context',
        )
      ) {
        console.error(
          'Session secret not available - check startup script and SESSION_SECRET environment variable',
        );
      } else if (error.message.includes('Credential is missing')) {
        console.error(
          'AWS credentials missing - session secret should be loaded at startup',
        );
      }
    }

    return NextResponse.redirect(new URL('/', request.url));
  }
}

// Only run middleware on specific paths that need protection
export const config = {
  matcher: ['/chat/:path*'],
};
