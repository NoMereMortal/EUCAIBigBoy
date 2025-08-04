// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, useEffect } from 'react';

/**
 * Custom hook that returns whether a media query matches the current viewport
 * @param query The media query to check
 * @returns A boolean indicating whether the media query matches
 *
 * Note: This hook returns false during server-side rendering to ensure
 * consistent hydration. The actual value is only determined after
 * client-side hydration is complete.
 */
export function useMediaQuery(query: string): boolean {
  // Track whether we're mounted on the client
  const [mounted, setMounted] = useState(false);
  // Initialize with false to ensure consistent server/client rendering
  const [matches, setMatches] = useState<boolean>(false);

  // Set mounted to true after hydration
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    // Skip if not mounted yet (during SSR or before hydration)
    if (!mounted) return undefined;

    // Check if window is defined (client-side)
    if (typeof window !== 'undefined') {
      const mediaQuery = window.matchMedia(query);

      // Set the initial value
      setMatches(mediaQuery.matches);

      // Define a callback function to handle changes
      const handleChange = (event: MediaQueryListEvent) => {
        setMatches(event.matches);
      };

      // Add the event listener
      mediaQuery.addEventListener('change', handleChange);

      // Clean up
      return () => {
        mediaQuery.removeEventListener('change', handleChange);
      };
    }

    return undefined;
  }, [query, mounted]);

  // Always return false during SSR or before hydration
  return mounted ? matches : false;
}
