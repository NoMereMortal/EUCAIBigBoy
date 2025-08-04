// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useEffect } from 'react';
import { useMessageStore } from '@/lib/store/message/message-slice';

/**
 * Provider component that initializes WebSocket handlers for messaging
 * This should be added near the root of the application to ensure
 * WebSocket functionality is available throughout the app
 */
export function MessageProvider({ children }: { children: React.ReactNode }) {
  const { initializeWsHandlers } = useMessageStore();

  // Initialize WebSocket handlers on component mount
  useEffect(() => {
    // Set up WebSocket handlers when the provider mounts
    initializeWsHandlers();

    // No cleanup needed as WebSocket connections are handled by the store
  }, [initializeWsHandlers]);

  // Simply render children - this component only handles initialization
  return <>{children}</>;
}
