// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

export enum DebugLevel {
  OFF = 0,
  ERROR = 1,
  WARN = 2,
  INFO = 3,
  DEBUG = 4,
  TRACE = 5,
}

// Global debug state
let debugMode = false;
let debugLevel = DebugLevel.INFO;

/**
 * Get current debug mode status
 */
export function getDebugModeStatus(): boolean {
  return debugMode;
}

/**
 * Toggle debug mode on/off
 */
export function toggleDebugMode(): boolean {
  debugMode = !debugMode;
  console.log(`Debug mode ${debugMode ? 'enabled' : 'disabled'}`);
  return debugMode;
}

/**
 * Set debug level
 */
export function setDebugLevel(level: DebugLevel): void {
  debugLevel = level;
  console.log(`Debug level set to: ${DebugLevel[level]}`);
}

/**
 * Get current debug level
 */
export function getDebugLevel(): DebugLevel {
  return debugLevel;
}

/**
 * Check if debug logging should occur for given level
 */
export function shouldLog(level: DebugLevel): boolean {
  return debugMode && level <= debugLevel;
}
