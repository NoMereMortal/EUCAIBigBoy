// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

/**
 * debug-utils.ts
 *
 * Debugging utilities to help diagnose and monitor message store issues,
 * particularly focusing on duplicate handler registrations and token replication.
 */

import { wsHandlerRegistry } from '@/lib/store/message/registry';
import { getWebSocketClient } from '@/lib/services/websocket-service';
import logger from '@/lib/utils/logger';

/**
 * Print diagnostic information about the message store and WebSocket handlers
 */
export const printDiagnostics = () => {
  // Get debug info from registry
  const registryInfo = wsHandlerRegistry.getDebugInfo();
  const wsClient = getWebSocketClient();

  logger.debug(
    'MessageStoreDiagnostics',
    'Message Store Diagnostics - Registry Status',
    {
      wsHandlersInitialized: registryInfo.wsHandlersInitialized,
      wsHandlerInitCount: registryInfo.wsHandlerInitCount,
      storeCreationCount: registryInfo.storeCreationCount,
      authLogoutListenerCount: registryInfo.authLogoutListenerCount,
    },
  );

  // Check WebSocket client status
  console.log('🔹 WebSocket Client:', {
    initialized: !!wsClient,
    connected: wsClient?.isConnected() || false,
  });

  // Log initialization timestamps
  if (registryInfo.initTimeStamps.length > 0) {
    console.log('🔹 WebSocket Handler Initialization Timestamps:');
    registryInfo.initTimeStamps.forEach((timestamp, index) => {
      const date = new Date(timestamp);
      console.log(`   ${index + 1}. ${date.toISOString()}`);
    });
  }

  // Only show stack traces in verbose mode - they're large
  console.log(
    '🔹 Initialization Stack Traces Available:',
    registryInfo.initStackTraces.length,
  );

  console.groupEnd();

  // Return true if there are any signs of multiple initialization
  const hasDuplicates =
    registryInfo.wsHandlerInitCount > 1 ||
    registryInfo.storeCreationCount > 1 ||
    registryInfo.authLogoutListenerCount > 1;

  return {
    hasDuplicates,
    wsHandlerCount: registryInfo.wsHandlerInitCount,
    storeCount: registryInfo.storeCreationCount,
    listenerCount: registryInfo.authLogoutListenerCount,
  };
};

/**
 * Monitor for duplicate WebSocket events by tracking content events
 * This can be attached to the WebSocket client to detect duplicate event processing
 */
export const monitorForDuplicateEvents = () => {
  const wsClient = getWebSocketClient();
  if (!wsClient) {
    console.error('Cannot monitor WebSocket events: client not initialized');
    return;
  }

  // Track content events to detect duplicates
  const contentEvents: Record<string, { count: number; timestamps: number[] }> =
    {};

  // Catch-all event handler for monitoring
  const unsubscribe = wsClient.onStreamingEvent('content', (event: any) => {
    const eventKey = `${event.response_id || 'unknown'}-${event.content}`;

    if (!contentEvents[eventKey]) {
      contentEvents[eventKey] = { count: 0, timestamps: [] };
    }

    contentEvents[eventKey].count++;
    contentEvents[eventKey].timestamps.push(Date.now());

    // Alert on duplicates (same content processed multiple times)
    if (contentEvents[eventKey].count > 1) {
      const timeDiff =
        contentEvents[eventKey].timestamps[contentEvents[eventKey].count - 1] -
        contentEvents[eventKey].timestamps[0];

      console.warn(
        `⚠️ Duplicate content event detected! Count: ${contentEvents[eventKey].count}, Time diff: ${timeDiff}ms`,
      );
      console.warn(`   Content: "${event.content?.substring(0, 30)}..."`);
    }
  });

  // Return unsubscribe function and stats accessor
  return {
    unsubscribe,
    getStats: () => ({
      totalTrackedEvents: Object.keys(contentEvents).length,
      duplicateEvents: Object.entries(contentEvents)
        .filter(([_, data]) => data.count > 1)
        .map(([key, data]) => ({ key, count: data.count })),
    }),
  };
};

/**
 * Test logging that will execute when this module is imported
 */
console.log(`Debug utilities loaded at ${new Date().toISOString()}`);
if (typeof window !== 'undefined') {
  // Expose debug utilities to global scope for console access
  (window as any).messageStoreDebug = {
    printDiagnostics,
    monitorForDuplicateEvents,
    registryInfo: wsHandlerRegistry.getDebugInfo,
  };
  console.log('Debug utilities exposed as window.messageStoreDebug');
}
