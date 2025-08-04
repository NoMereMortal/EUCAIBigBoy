// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Application constants

// Define type for the window.env object
declare global {
  interface Window {
    env?: {
      API_URI?: string;
      API_VERSION?: string;
      UI_TITLE?: string;
      NEXT_PUBLIC_BYPASS_AUTH?: string;
      COGNITO?: {
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
      };
    };
  }
}

// More robust server-side rendering detection
export const isServer = () => typeof window === 'undefined';

// Function to get API configuration values at runtime
export function getApiConfig() {
  // Start with safe defaults that won't cause unintended network requests
  const config = {
    BASE_URL: '', // Empty string initially
    API_VERSION: 'v1',
    WS_URL: null as string | null,
  };

  try {
    // Check if we're in a browser environment
    const isBrowser = !isServer();

    if (isBrowser) {
      // Browser environment - ALWAYS prioritize window.env (from public/env.js)
      if (window.env?.API_URI) {
        config.BASE_URL = window.env.API_URI;
        console.debug('Using API_URI from env.js:', config.BASE_URL);
      }

      if (window.env?.API_VERSION) {
        config.API_VERSION = window.env.API_VERSION;
        console.debug('Using API_VERSION from env.js:', config.API_VERSION);
      }

      // Only fall back to process.env if window.env is missing values
      if (config.BASE_URL === '' && process.env.NEXT_PUBLIC_API_URI) {
        config.BASE_URL = process.env.NEXT_PUBLIC_API_URI;
        console.debug('Falling back to NEXT_PUBLIC_API_URI:', config.BASE_URL);
      }

      if (!config.API_VERSION && process.env.NEXT_PUBLIC_API_VERSION) {
        config.API_VERSION = process.env.NEXT_PUBLIC_API_VERSION;
        console.debug(
          'Falling back to NEXT_PUBLIC_API_VERSION:',
          config.API_VERSION,
        );
      }
    }
    // Server environment (SSR) - use environment variables that were populated from env.js
    else {
      if (process.env.NEXT_PUBLIC_API_URI) {
        config.BASE_URL = process.env.NEXT_PUBLIC_API_URI;
        console.debug(
          'Using NEXT_PUBLIC_API_URI in SSR context:',
          config.BASE_URL,
        );
      } else {
        console.warn(
          'NEXT_PUBLIC_API_URI not found during SSR. Using server hostname.',
        );
        // Use server's own hostname for API calls in SSR context when needed
        // This assumes API routes are on the same host but under /api path
        try {
          // This should be the server's own hostname
          config.BASE_URL = ''; // Empty string will result in relative URLs to the same host
          console.debug('Using relative URL for API in SSR context');
        } catch (err) {
          console.error('Failed to determine server hostname:', err);
        }
      }

      if (process.env.NEXT_PUBLIC_API_VERSION) {
        config.API_VERSION = process.env.NEXT_PUBLIC_API_VERSION;
        console.debug(
          'Using NEXT_PUBLIC_API_VERSION in SSR context:',
          config.API_VERSION,
        );
      } else {
        console.debug(
          'Using default API_VERSION in SSR context:',
          config.API_VERSION,
        );
      }
    }

    // Validation and fixing any protocol issues
    if (isBrowser) {
      if (!config.BASE_URL) {
        console.error('No API_URI found in env.js or environment variables!');
        console.error(
          'Please check that public/env.js exists and contains valid configuration.',
        );

        // Before falling back to a dummy URL, try to use the current origin
        // This is especially useful when API is on the same domain via ALB routing
        try {
          config.BASE_URL = window.location.origin;
          console.debug(
            'Using current origin as API_URI fallback:',
            config.BASE_URL,
          );
        } catch (e) {
          // If we can't access window.location, use the explicit fallback
          config.BASE_URL = 'http://api-not-configured';
          console.debug('Using explicit fallback API_URI');
        }
      } else {
        // Ensure we're using HTTPS when the page is loaded over HTTPS
        // This prevents mixed content blocking, but don't enforce for localhost
        try {
          // More comprehensive localhost check
          const isLocalhost =
            config.BASE_URL.includes('localhost') ||
            config.BASE_URL.includes('127.0.0.1') ||
            config.BASE_URL.includes('0.0.0.0');

          console.debug(
            `BASE_URL: ${config.BASE_URL}, isLocalhost: ${isLocalhost}`,
          );

          const pageProtocol = window.location.protocol;

          // Never upgrade protocol for localhost
          if (isLocalhost) {
            console.debug(
              `Not upgrading protocol for localhost URL: ${config.BASE_URL}`,
            );

            // Ensure localhost URLs have http:// prefix if no protocol specified
            if (config.BASE_URL && !config.BASE_URL.startsWith('http')) {
              config.BASE_URL = `http://${config.BASE_URL}`;
              console.debug(
                `Adding http:// protocol to localhost URL: ${config.BASE_URL}`,
              );
            }
          }
          // Upgrade non-localhost HTTP to HTTPS when page is loaded via HTTPS
          else if (
            pageProtocol === 'https:' &&
            config.BASE_URL.startsWith('http:')
          ) {
            const originalUrl = config.BASE_URL;
            config.BASE_URL = config.BASE_URL.replace('http:', 'https:');
            console.debug(
              `Upgraded API_URI protocol from HTTP to HTTPS: ${originalUrl} -> ${config.BASE_URL}`,
            );
          }
        } catch (e) {
          console.error('Error checking/upgrading protocol:', e);
        }
      }
    }
    // For SSR, use a placeholder if needed
    else if (!config.BASE_URL) {
      config.BASE_URL = 'http://ssr-placeholder';
      console.debug('Using placeholder BASE_URL for SSR');
    }
  } catch (error) {
    console.error('Error loading API configuration:', error);
    // Set a safe fallback that will fail explicitly
    config.BASE_URL = !isServer()
      ? 'http://api-configuration-error'
      : 'http://ssr-placeholder';
  }

  return config;
}
