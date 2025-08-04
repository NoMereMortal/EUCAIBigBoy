// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

/**
 * Debug logs package index
 *
 * This file allows easy importing of debug utilities and automatically
 * initializes the debug logging system when imported.
 */

// Export all debug utilities
export * from './debug-utils';

// Create monitoring object when imported
import {
  monitorForDuplicateEvents,
  printDiagnostics,
} from '@/lib/store/message/debug-logs/debug-utils';
import logger from '@/lib/utils/logger';

// Print initial diagnostics
logger.debug('MessageStoreDebug', 'Initial Message Store Diagnostics');
printDiagnostics();

// Set up a monitor that can be enabled via console if needed
let duplicateEventMonitor: any = null;

// Helper to start/stop event monitoring
export const toggleDuplicateEventMonitoring = (enable: boolean = true) => {
  if (enable && !duplicateEventMonitor) {
    logger.debug('MessageStoreDebug', 'Starting duplicate event monitoring');
    duplicateEventMonitor = monitorForDuplicateEvents();
    return true;
  } else if (!enable && duplicateEventMonitor) {
    logger.debug('MessageStoreDebug', 'Stopping duplicate event monitoring');
    duplicateEventMonitor.unsubscribe();
    const stats = duplicateEventMonitor.getStats();
    duplicateEventMonitor = null;
    console.log('Final monitoring stats:', stats);
    return false;
  }
  return !!duplicateEventMonitor;
};

// Add to window object for easy console access
if (typeof window !== 'undefined') {
  (window as any).toggleDuplicateEventMonitoring =
    toggleDuplicateEventMonitoring;
}

// Log that debug monitoring is available
console.log(`
📢 Message Store Debug Utilities Ready
-------------------------------------
Available in console:
- window.messageStoreDebug.printDiagnostics()
- window.toggleDuplicateEventMonitoring(true/false)
`);
