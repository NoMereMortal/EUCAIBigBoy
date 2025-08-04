// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

/**
 * registry.ts
 *
 * This module provides a global registry to track WebSocket handler initialization
 * outside the Zustand store, breaking circular dependencies and preventing
 * multiple handler registrations.
 */

// Track whether WebSocket handlers have been initialized
let wsHandlersInitialized = false;
let wsHandlerInitCount = 0;
let storeCreationCount = 0;
let authLogoutListenerCount = 0;

// Store instance registry
let messageStoreInstance: any = null;

// Debug info for diagnostics
const initTimeStamps: number[] = [];
const initStackTraces: string[] = [];

// Get stack trace for debugging
function getStackTrace(): string {
  const stack = new Error().stack || '';
  return stack.split('\n').slice(2).join('\n');
}

// Get the current timestamp
function timestamp(): string {
  return new Date().toISOString();
}

// API for tracking WebSocket handler initialization
export const wsHandlerRegistry = {
  // Check if handlers are already initialized
  isInitialized: () => wsHandlersInitialized,

  // Mark handlers as initialized
  markInitialized: () => {
    wsHandlersInitialized = true;
    wsHandlerInitCount++;
    initTimeStamps.push(Date.now());
    initStackTraces.push(getStackTrace());
    console.log(
      `[${timestamp()}] WebSocket handlers marked as initialized (count: ${wsHandlerInitCount})`,
    );
  },

  // Get initialization count (for debugging)
  getInitCount: () => wsHandlerInitCount,

  // Get debug info
  getDebugInfo: () => ({
    wsHandlersInitialized,
    wsHandlerInitCount,
    storeCreationCount,
    authLogoutListenerCount,
    initTimeStamps,
    initStackTraces,
  }),
};

// API for tracking store creation
export const storeRegistry = {
  // Check if store is already created
  hasStoreInstance: () => messageStoreInstance !== null,

  // Get store instance
  getStoreInstance: () => messageStoreInstance,

  // Register store instance
  registerStoreInstance: (instance: any) => {
    messageStoreInstance = instance;
    storeCreationCount++;
    console.log(
      `[${timestamp()}] Store instance registered (count: ${storeCreationCount})`,
    );
    return instance;
  },

  // Get store creation count (for debugging)
  getStoreCreationCount: () => storeCreationCount,
};

// API for tracking event listeners
export const listenerRegistry = {
  // Register auth logout listener
  registerAuthLogoutListener: () => {
    authLogoutListenerCount++;
    console.log(
      `[${timestamp()}] Auth logout listener registered (count: ${authLogoutListenerCount})`,
    );
    return authLogoutListenerCount;
  },

  // Get auth logout listener count (for debugging)
  getAuthLogoutListenerCount: () => authLogoutListenerCount,
};

// Log registry usage
console.log(`[${timestamp()}] Registry module loaded`);
