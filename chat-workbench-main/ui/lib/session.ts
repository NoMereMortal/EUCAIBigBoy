// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import 'server-only';
import { SignJWT, jwtVerify } from 'jose';
import { cookies } from 'next/headers';
import type { UserSessionData } from '@/lib/auth-actions';

export interface SessionPayload {
  userId: string;
  expiresAt: number | Date;
  [key: string]: any; // Index signature for JWT compatibility
}

let cachedSecretKey: string | null = null;
let secretKeyPromise: Promise<string> | null = null;

/**
 * Get the session secret key, either from environment variable (dev) or SSM Parameter Store (production)
 */
async function getSessionSecret(): Promise<string> {
  // Return cached key if available
  if (cachedSecretKey) {
    return cachedSecretKey;
  }

  // Return existing promise if one is in progress
  if (secretKeyPromise) {
    return secretKeyPromise;
  }

  // Create new promise to fetch the secret
  secretKeyPromise = (async () => {
    // First priority: Use SESSION_SECRET environment variable if available
    if (process.env.SESSION_SECRET) {
      cachedSecretKey = process.env.SESSION_SECRET;
      return cachedSecretKey;
    }

    // Second priority: Development mode fallback
    if (process.env.NODE_ENV === 'development') {
      const key = 'your-fallback-secret-key-change-in-production';
      cachedSecretKey = key;
      return key;
    }

    // Third priority: Fetch from Secrets Manager (for non-middleware contexts)
    if (process.env.SESSION_SECRET_NAME) {
      try {
        const { SecretsManagerClient, GetSecretValueCommand } = await import(
          '@aws-sdk/client-secrets-manager'
        );

        const client = new SecretsManagerClient({
          region: process.env.AWS_REGION || 'eu-west-1',
        });

        let response;
        try {
          response = await client.send(
            new GetSecretValueCommand({
              SecretId: process.env.SESSION_SECRET_NAME,
              VersionStage: 'AWSCURRENT', // VersionStage defaults to AWSCURRENT if unspecified
            }),
          );
        } catch (error) {
          // For a list of exceptions thrown, see
          // https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
          console.error('Secrets Manager API error:', error);
          throw error;
        }

        const secret = response.SecretString;
        if (!secret) {
          throw new Error(
            'Session secret not found in Secrets Manager response',
          );
        }

        // Parse the JSON secret string to extract the actual secret
        let secretData;
        try {
          secretData = JSON.parse(secret);
        } catch (parseError) {
          console.error('Failed to parse secret JSON:', parseError);
          throw new Error('Invalid JSON format in session secret');
        }

        const secretValue = secretData.secret;
        if (!secretValue) {
          throw new Error('Secret key "secret" not found in JSON');
        }

        cachedSecretKey = secretValue;
        console.debug(
          'Successfully loaded session secret from Secrets Manager',
        );
        return secretValue;
      } catch (error) {
        console.error(
          'Failed to load session secret from Secrets Manager:',
          error,
        );

        // If we're likely in middleware context (Edge Runtime), provide a more specific error
        const isEdgeRuntime =
          (typeof globalThis !== 'undefined' && 'EdgeRuntime' in globalThis) ||
          (typeof process !== 'undefined' &&
            process.env.NEXT_RUNTIME === 'edge');

        if (isEdgeRuntime) {
          throw new Error(
            'Session secret not available in middleware context. Ensure SESSION_SECRET environment variable is set during startup.',
          );
        } else {
          throw new Error(
            `Failed to load session secret from Secrets Manager: ${error instanceof Error ? error.message : 'Unknown error'}`,
          );
        }
      }
    }

    // Final fallback - should not be reached in production
    console.warn(
      'Using fallback session secret - not recommended for production',
    );
    const fallbackKey = 'your-fallback-secret-key-change-in-production';
    cachedSecretKey = fallbackKey;
    return fallbackKey;
  })();

  return secretKeyPromise;
}

/**
 * Encrypt session data into a JWT token
 */
export async function encrypt(payload: SessionPayload) {
  const secretKey = await getSessionSecret();
  const encodedKey = new TextEncoder().encode(secretKey);

  return new SignJWT(payload)
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(payload.expiresAt)
    .sign(encodedKey);
}

/**
 * Decrypt and verify JWT session token
 */
export async function decrypt(session: string | undefined = '') {
  try {
    const secretKey = await getSessionSecret();
    const encodedKey = new TextEncoder().encode(secretKey);

    const { payload } = await jwtVerify(session, encodedKey, {
      algorithms: ['HS256'],
    });
    return payload as SessionPayload;
  } catch (error) {
    console.log('Failed to verify session');
    return null;
  }
}

/**
 * Create session cookie after OIDC authentication
 */
export async function createSessionCookie(userData: UserSessionData) {
  if (!userData.userId || !userData.expiresAt) {
    throw new Error('Invalid user data for session creation');
  }

  const expiresAt = new Date(userData.expiresAt * 1000);
  const sessionData: SessionPayload = {
    userId: userData.userId,
    expiresAt,
  };

  const session = await encrypt(sessionData);
  const cookieStore = await cookies();

  cookieStore.set('session', session, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    expires: expiresAt,
    sameSite: 'lax',
    path: '/',
  });

  console.debug('HTTP cookie set for user:', userData.userId);
}

/**
 * Update/refresh session cookie
 */
export async function updateSessionCookie() {
  const cookieStore = await cookies();
  const session = cookieStore.get('session')?.value;
  const payload = await decrypt(session);

  if (!session || !payload) {
    return null;
  }

  // Extend session by 7 days
  const expires = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  const updatedPayload: SessionPayload = {
    ...payload,
    expiresAt: expires,
  };

  const newSession = await encrypt(updatedPayload);

  cookieStore.set('session', newSession, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    expires: expires,
    sameSite: 'lax',
    path: '/',
  });

  return updatedPayload;
}

/**
 * Delete session cookie
 */
export async function deleteSessionCookie() {
  const cookieStore = await cookies();
  cookieStore.delete('session');
  console.debug('HTTP cookie deleted');
}

/**
 * Get current session from cookie
 */
export async function getSession() {
  const cookieStore = await cookies();
  const session = cookieStore.get('session')?.value;
  return await decrypt(session);
}
