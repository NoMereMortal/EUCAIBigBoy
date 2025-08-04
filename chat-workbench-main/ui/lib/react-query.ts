// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { QueryClient } from '@tanstack/react-query';

// Create a client
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Default stale time of 5 minutes
      staleTime: 5 * 60 * 1000,
      // Default cache time of 10 minutes
      gcTime: 10 * 60 * 1000,
      // Retry failed queries 3 times
      retry: 3,
      // Don't refetch on window focus by default
      refetchOnWindowFocus: false,
    },
  },
});
