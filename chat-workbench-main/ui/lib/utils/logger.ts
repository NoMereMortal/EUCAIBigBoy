// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

/**
 * Logger utility for consistent logging across the application
 * Provides structured logging with timestamp and context information
 */

// Log levels for filtering
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

// Configure the minimum log level to display
// Can be controlled by environment variable in production
const MIN_LOG_LEVEL =
  process.env.NODE_ENV === 'production' ? LogLevel.INFO : LogLevel.DEBUG;

// Optional: enable persistent logging (e.g. to localStorage)
const ENABLE_PERSISTENT_LOGGING = false;
const MAX_LOG_ENTRIES = 1000;

// Storage for logs if persistence is enabled
const logHistory: LogEntry[] = [];

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  category: string;
  message: string;
  data?: any;
  correlationId?: string;
}

/**
 * Format a log entry for console output
 */
function formatLogEntry(entry: LogEntry): string {
  const levelLabels = ['DEBUG', 'INFO', 'WARN', 'ERROR'];
  const levelLabel = levelLabels[entry.level];

  let formatted = `[${entry.timestamp}] [${levelLabel}] [${entry.category}]`;

  if (entry.correlationId) {
    formatted += ` [${entry.correlationId}]`;
  }

  formatted += `: ${entry.message}`;

  return formatted;
}

/**
 * Core logging function
 */
function logEntry(
  level: LogLevel,
  category: string,
  message: string,
  data?: any,
  correlationId?: string,
) {
  if (level < MIN_LOG_LEVEL) return;

  const timestamp = new Date().toISOString();
  const entry: LogEntry = {
    timestamp,
    level,
    category,
    message,
    correlationId,
    data,
  };

  // Format for console
  const formattedMessage = formatLogEntry(entry);

  // Log to console with appropriate level
  switch (level) {
    case LogLevel.DEBUG:
      console.debug(formattedMessage, data || '');
      break;
    case LogLevel.INFO:
      console.info(formattedMessage, data || '');
      break;
    case LogLevel.WARN:
      console.warn(formattedMessage, data || '');
      break;
    case LogLevel.ERROR:
      console.error(formattedMessage, data || '');
      break;
  }

  // Store in history if persistence is enabled
  if (ENABLE_PERSISTENT_LOGGING) {
    logHistory.push(entry);

    // Trim history if needed
    if (logHistory.length > MAX_LOG_ENTRIES) {
      logHistory.shift();
    }

    // Could also store to localStorage here if needed
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('appLogs', JSON.stringify(logHistory));
      } catch (e) {
        // Handle storage failures silently
      }
    }
  }
}

/**
 * Message Stream specific logging with enhanced context
 */
export class MessageStreamLogger {
  private category = 'MessageStream';
  private messageId: string | null = null;
  private chatId: string | null = null;
  private startTime: number | null = null;

  constructor(chatId?: string, messageId?: string) {
    if (chatId) this.chatId = chatId;
    if (messageId) this.messageId = messageId;
  }

  /**
   * Set or update metadata for the logger instance
   */
  setContext(chatId?: string, messageId?: string) {
    if (chatId) this.chatId = chatId;
    if (messageId) this.messageId = messageId;
    return this;
  }

  /**
   * Start timing an operation
   */
  startTimer() {
    this.startTime = performance.now();
    return this;
  }

  /**
   * Get elapsed time since startTimer was called
   */
  getElapsedMs(): number | null {
    if (this.startTime === null) return null;
    return Math.round(performance.now() - this.startTime);
  }

  /**
   * Reset the timer
   */
  resetTimer() {
    this.startTime = null;
    return this;
  }

  /**
   * Get correlation ID from context
   */
  private getCorrelationId(): string {
    const parts: string[] = [];
    if (this.chatId) parts.push(`chat:${this.chatId}`);
    if (this.messageId) parts.push(`msg:${this.messageId}`);
    return parts.length ? parts.join('|') : 'connection';
  }

  /**
   * Log a state transition
   */
  logStateChange(from: string, to: string, details?: Record<string, any>) {
    const elapsedMs = this.getElapsedMs();
    const data = {
      ...details,
      states: { from, to },
      ...(elapsedMs !== null ? { elapsedMs } : {}),
    };

    logEntry(
      LogLevel.INFO,
      this.category,
      `State change: ${from} -> ${to}`,
      data,
      this.getCorrelationId(),
    );

    return this;
  }

  /**
   * Log message streaming events
   */
  logStreamEvent(
    event: 'start' | 'update' | 'complete' | 'error',
    details?: Record<string, any>,
  ) {
    const elapsedMs = this.getElapsedMs();
    const data = {
      ...details,
      ...(elapsedMs !== null ? { elapsedMs } : {}),
    };

    logEntry(
      event === 'error' ? LogLevel.ERROR : LogLevel.INFO,
      this.category,
      `Stream ${event}`,
      data,
      this.getCorrelationId(),
    );

    return this;
  }

  /**
   * General debug log
   */
  debug(message: string, data?: any) {
    logEntry(
      LogLevel.DEBUG,
      this.category,
      message,
      data,
      this.getCorrelationId(),
    );
    return this;
  }

  /**
   * General info log
   */
  info(message: string, data?: any) {
    logEntry(
      LogLevel.INFO,
      this.category,
      message,
      data,
      this.getCorrelationId(),
    );
    return this;
  }

  /**
   * Warning log
   */
  warn(message: string, data?: any) {
    logEntry(
      LogLevel.WARN,
      this.category,
      message,
      data,
      this.getCorrelationId(),
    );
    return this;
  }

  /**
   * Error log
   */
  error(message: string, data?: any) {
    logEntry(
      LogLevel.ERROR,
      this.category,
      message,
      data,
      this.getCorrelationId(),
    );
    return this;
  }
}

// Create default logger instances
export const logger = {
  debug: (
    category: string,
    message: string,
    data?: any,
    correlationId?: string,
  ) => logEntry(LogLevel.DEBUG, category, message, data, correlationId),

  info: (
    category: string,
    message: string,
    data?: any,
    correlationId?: string,
  ) => logEntry(LogLevel.INFO, category, message, data, correlationId),

  warn: (
    category: string,
    message: string,
    data?: any,
    correlationId?: string,
  ) => logEntry(LogLevel.WARN, category, message, data, correlationId),

  error: (
    category: string,
    message: string,
    data?: any,
    correlationId?: string,
  ) => logEntry(LogLevel.ERROR, category, message, data, correlationId),

  // Create a MessageStream specific logger
  forMessageStream: (chatId?: string, messageId?: string) =>
    new MessageStreamLogger(chatId, messageId),

  // Expose log history if persistence is enabled
  getLogHistory: () => (ENABLE_PERSISTENT_LOGGING ? [...logHistory] : []),
};

export default logger;
