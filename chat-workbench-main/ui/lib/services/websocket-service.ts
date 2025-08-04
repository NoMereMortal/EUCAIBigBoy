// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import logger from '@/lib/utils/logger';
import { getApiConfig } from '@/lib/constants';
import {
  WSMessageType,
  WSConnectionEstablishedMessage,
  StreamingEvent,
  ContentEvent,
  ReasoningEvent,
  ResponseStartEvent,
  ResponseEndEvent,
  StatusEvent,
  ErrorEvent,
  ToolCallEvent,
  ToolReturnEvent,
  MetadataEvent,
  DocumentEvent,
  CitationEvent,
} from './websocket-types';

// Central logger for WebSocket operations
const wsLogger = logger.forMessageStream();

// WebSocket client class - handles connection and message sending
export class WebSocketClient {
  private socket: WebSocket | null = null;
  private messageQueue: any[] = [];
  private connected: boolean = false;
  private connectionPromise: Promise<void> | null = null;
  private messageHandlers: Map<WSMessageType, ((data: any) => void)[]> =
    new Map();
  private streamingEventHandlers: Map<
    string,
    ((event: StreamingEvent) => void)[]
  > = new Map();
  private errorHandlers: ((error: any) => void)[] = [];
  private closeHandlers: (() => void)[] = [];
  private pingInterval: NodeJS.Timeout | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectDelay: number = 2000; // Start with 2 second delay
  private autoReconnect: boolean = true;

  /**
   * Create a new WebSocket client instance
   * @param {boolean} autoReconnect Whether to auto-reconnect when connection is lost
   */
  constructor(autoReconnect: boolean = true) {
    this.autoReconnect = autoReconnect;
  }

  /**
   * Connect to the WebSocket endpoint
   * Returns a promise that resolves when the connection is established
   */
  async connect(): Promise<void> {
    // Prevent unnecessary connection attempts at startup
    if (typeof window === 'undefined') {
      return Promise.resolve(); // No-op during SSR
    }

    // If already connected or connecting, return the existing promise
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      return Promise.resolve();
    }

    if (this.socket && this.socket.readyState === WebSocket.CONNECTING) {
      return this.connectionPromise || Promise.resolve();
    }

    this.connectionPromise = new Promise((resolve, reject) => {
      try {
        // Get the API configuration
        const { BASE_URL, API_VERSION, WS_URL } = getApiConfig();

        // Determine the WebSocket URL
        let wsUrl: string;

        // Using the configured WebSocket URL
        if (WS_URL) {
          // Use the configured WebSocket URL directly
          wsUrl = `${WS_URL}/api/${API_VERSION}/generate/ws`;
          wsLogger.info('Using configured WebSocket URL', {
            configuredWsUrl: WS_URL,
            finalWsUrl: wsUrl,
          });
        } else {
          // Derive from BASE_URL
          const wsProtocol = BASE_URL.startsWith('https') ? 'wss:' : 'ws:';
          const baseUrlObj = new URL(BASE_URL);
          wsUrl = `${wsProtocol}//${baseUrlObj.host}/api/${API_VERSION}/generate/ws`;
          wsLogger.info('WebSocket URL derived from API config', {
            apiUrl: BASE_URL,
            wsUrl,
          });
        }

        console.log('Final WebSocket URL:', wsUrl);
        console.log('API Config:', {
          BASE_URL,
          API_VERSION,
          WS_URL,
        });

        wsLogger.info('Connecting to WebSocket', { url: wsUrl });

        // Create WebSocket connection
        this.socket = new WebSocket(wsUrl);

        // Set up event handlers
        this.socket.onopen = () => {
          this.connected = true;
          this.reconnectAttempts = 0; // Reset reconnect attempts on successful connection
          this.flushQueue();
          wsLogger.info('WebSocket connection established');

          // Start heartbeat ping
          this.startHeartbeat();

          resolve();
        };

        this.socket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            const { type, data } = message;

            wsLogger.debug('Received WebSocket message', { type });

            // Handle streaming events
            if (type === WSMessageType.EVENT) {
              this.handleStreamingEvent(data);
            } else if (type === WSMessageType.ERROR) {
              // Special handling for error messages - logging as warning instead of error
              wsLogger.warn('WebSocket error message', {
                error_message: data?.error,
                error_type: data?.error_type,
                response_id: data?.response_id,
                details: data?.details,
              });

              // Handle both through message handlers and through streaming event handlers
              // for better compatibility
              const handlers =
                this.messageHandlers.get(type as WSMessageType) || [];
              handlers.forEach((handler) => handler(data));

              // Also dispatch through streaming event system for consistency
              const errorStreamingHandlers =
                this.streamingEventHandlers.get('error') || [];
              if (errorStreamingHandlers.length > 0) {
                // Convert to streaming event format
                const errorEvent: ErrorEvent = {
                  type: 'error',
                  error_type: data?.error_type || 'Error',
                  message: data?.error || 'Unknown error',
                  details: data?.details || null,
                  response_id: data?.response_id,
                  timestamp: new Date().toISOString(),
                  sequence: data?.sequence || 0,
                };

                errorStreamingHandlers.forEach((handler) => {
                  try {
                    handler(errorEvent);
                  } catch (error) {
                    wsLogger.warn('Error in WebSocket error event handler', {
                      error,
                    });
                  }
                });
              }
            } else {
              // Handle other message types (connection_established, status, pong)
              const handlers =
                this.messageHandlers.get(type as WSMessageType) || [];
              handlers.forEach((handler) => handler(data));
            }
          } catch (error) {
            wsLogger.error('Error processing WebSocket message', { error });
            this.errorHandlers.forEach((handler) => handler(error));
          }
        };

        this.socket.onerror = (error) => {
          wsLogger.error('WebSocket error', { error });
          this.errorHandlers.forEach((handler) => handler(error));
          reject(error);
        };

        this.socket.onclose = (event) => {
          wsLogger.info('WebSocket connection closed', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
          });

          this.stopHeartbeat();
          this.connected = false;
          this.socket = null;
          this.closeHandlers.forEach((handler) => handler());

          // Attempt to reconnect if enabled and not a clean close
          if (
            this.autoReconnect &&
            this.reconnectAttempts < this.maxReconnectAttempts &&
            !event.wasClean
          ) {
            this.attemptReconnect();
          }
        };
      } catch (error) {
        wsLogger.error('Failed to connect to WebSocket', { error });
        reject(error);
      }
    });

    return this.connectionPromise;
  }

  /**
   * Send a message through the WebSocket connection
   * If not connected yet, queue the message to be sent once connected
   */
  send(type: WSMessageType, data: any): void {
    const message = { type, data };

    if (
      !this.connected ||
      !this.socket ||
      this.socket.readyState !== WebSocket.OPEN
    ) {
      // Queue message to be sent once connected
      this.messageQueue.push(message);

      // Try to connect if not already connecting
      if (!this.socket || this.socket.readyState !== WebSocket.CONNECTING) {
        this.connect().catch((error) => {
          wsLogger.error('Failed to connect while trying to send message', {
            error,
          });
        });
      }
      return;
    }

    this.socket.send(JSON.stringify(message));
  }

  /**
   * Send any queued messages
   */
  private flushQueue(): void {
    if (
      !this.connected ||
      !this.socket ||
      this.socket.readyState !== WebSocket.OPEN
    )
      return;

    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      if (message) {
        this.socket.send(JSON.stringify(message));
      }
    }
  }

  /**
   * Register a handler for a specific message type
   */
  onMessage(type: WSMessageType, handler: (data: any) => void): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, []);
    }

    this.messageHandlers.get(type)!.push(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(type) || [];
      const index = handlers.indexOf(handler);
      if (index !== -1) {
        handlers.splice(index, 1);
      }
    };
  }

  /**
   * Register a handler for streaming events by event type
   */
  onStreamingEvent(
    eventType: string,
    handler: (event: StreamingEvent) => void,
  ): () => void {
    if (!this.streamingEventHandlers.has(eventType)) {
      this.streamingEventHandlers.set(eventType, []);
    }

    this.streamingEventHandlers.get(eventType)!.push(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.streamingEventHandlers.get(eventType) || [];
      const index = handlers.indexOf(handler);
      if (index !== -1) {
        handlers.splice(index, 1);
      }
    };
  }

  /**
   * Register a handler for WebSocket errors
   */
  onError(handler: (error: any) => void): () => void {
    this.errorHandlers.push(handler);

    // Return unsubscribe function
    return () => {
      const index = this.errorHandlers.indexOf(handler);
      if (index !== -1) {
        this.errorHandlers.splice(index, 1);
      }
    };
  }

  /**
   * Register a handler for WebSocket close events
   */
  onClose(handler: () => void): () => void {
    this.closeHandlers.push(handler);

    // Return unsubscribe function
    return () => {
      const index = this.closeHandlers.indexOf(handler);
      if (index !== -1) {
        this.closeHandlers.splice(index, 1);
      }
    };
  }

  /**
   * Interrupt the current generation
   */
  interrupt(): void {
    this.send(WSMessageType.INTERRUPT, {});
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return (
      this.connected &&
      this.socket !== null &&
      this.socket.readyState === WebSocket.OPEN
    );
  }

  /**
   * Close the WebSocket connection
   */
  disconnect(): void {
    this.stopHeartbeat();
    this.autoReconnect = false; // Disable auto-reconnect when manually disconnected

    if (this.socket) {
      this.socket.close();
      this.socket = null;
      this.connected = false;
    }
  }

  /**
   * Start sending periodic heartbeat pings
   */
  private startHeartbeat(): void {
    this.stopHeartbeat(); // Clear any existing interval

    // Send ping every 30 seconds to keep connection alive
    this.pingInterval = setInterval(() => {
      if (this.isConnected()) {
        this.send(WSMessageType.PING, { timestamp: Date.now() });
        wsLogger.debug('Heartbeat ping sent');
      } else {
        this.stopHeartbeat();
      }
    }, 30000); // 30 second interval
  }

  /**
   * Stop the heartbeat ping interval
   */
  private stopHeartbeat(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private attemptReconnect(): void {
    const delay = Math.min(
      30000,
      this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts),
    );
    this.reconnectAttempts++;

    wsLogger.info(
      `Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${delay}ms`,
    );

    setTimeout(() => {
      this.connect().catch((error) => {
        wsLogger.error('Reconnection attempt failed', {
          error,
          attempt: this.reconnectAttempts,
        });
      });
    }, delay);
  }

  /**
   * Handle streaming events from the WebSocket
   */
  private handleStreamingEvent(streamingEvent: StreamingEvent): void {
    // Structured logging for streaming events
    const eventInfo: Record<string, any> = {
      type: streamingEvent.type,
      response_id: streamingEvent.response_id,
      timestamp: streamingEvent.timestamp,
      sequence: streamingEvent.sequence,
    };

    // Add type-specific information
    if (streamingEvent.type === 'content' && 'content' in streamingEvent) {
      eventInfo.content_length =
        (streamingEvent as ContentEvent).content?.length || 0;
    } else if (
      streamingEvent.type === 'response_start' &&
      'request_id' in streamingEvent
    ) {
      const startEvent = streamingEvent as ResponseStartEvent;
      eventInfo.request_id = startEvent.request_id;
      eventInfo.chat_id = startEvent.chat_id;
      eventInfo.model_id = startEvent.model_id;
    } else if (
      streamingEvent.type === 'response_end' &&
      'status' in streamingEvent
    ) {
      const endEvent = streamingEvent as ResponseEndEvent;
      eventInfo.status = endEvent.status;
      eventInfo.usage = endEvent.usage ? Object.keys(endEvent.usage) : [];
    }

    wsLogger.debug('Raw streaming event received:', eventInfo);

    // Find handlers for this event type
    const eventTypeHandlers =
      this.streamingEventHandlers.get(streamingEvent.type) || [];

    if (eventTypeHandlers.length === 0) {
      wsLogger.warn('No handlers registered for streaming event type', {
        type: streamingEvent.type,
        availableTypes: Array.from(this.streamingEventHandlers.keys()),
      });
    } else {
      wsLogger.debug('Dispatching to event handlers', {
        type: streamingEvent.type,
        handlerCount: eventTypeHandlers.length,
      });
    }

    // Call handlers registered for this specific event type
    eventTypeHandlers.forEach((handler) => {
      try {
        handler(streamingEvent);
      } catch (error) {
        wsLogger.error('Error in streaming event handler', {
          type: streamingEvent.type,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    });

    // Call handlers registered for 'all' event types
    const allHandlers = this.streamingEventHandlers.get('*') || [];
    allHandlers.forEach((handler) => {
      try {
        handler(streamingEvent);
      } catch (error) {
        wsLogger.error('Error in universal streaming event handler', {
          type: streamingEvent.type,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    });
  }
}

// Singleton instance
let wsClient: WebSocketClient | null = null;
let wsClientInitialized = false; // Track if we've ever created a client

// Get or create the WebSocket client
export function getWebSocketClient(): WebSocketClient {
  // Only create when actually needed
  if (!wsClient) {
    wsClient = new WebSocketClient();
    wsClientInitialized = true;
  }
  return wsClient;
}

// Add lazy connection method to prevent automatic connections
export function ensureWebSocketClient(): WebSocketClient | null {
  // Only return if already initialized (don't create on demand)
  return wsClient;
}

// Add cleanup method for app shutdown/page navigation
export function cleanupWebSocketClient(): void {
  if (wsClient) {
    wsClient.disconnect();
    wsClient = null;
  }
}

// Simplified message event handler types for the new format
export interface WebSocketMessageHandlers {
  // New streaming event handlers
  onContentEvent?: (event: ContentEvent) => void;
  onReasoningEvent?: (event: ReasoningEvent) => void;
  onResponseStartEvent?: (event: ResponseStartEvent) => void;
  onResponseEndEvent?: (event: ResponseEndEvent) => void;
  onStatusEvent?: (event: StatusEvent) => void;
  onErrorEvent?: (event: ErrorEvent) => void;
  onToolCallEvent?: (event: ToolCallEvent) => void;
  onToolReturnEvent?: (event: ToolReturnEvent) => void;
  onMetadataEvent?: (event: MetadataEvent) => void;
  onDocumentEvent?: (event: DocumentEvent) => void;
  onCitationEvent?: (event: CitationEvent) => void;

  // Connection events
  onConnectionEstablished?: (data: WSConnectionEstablishedMessage) => void;
  onError?: (error: any) => void;
  onClose?: () => void;
}

// Convenience method to register multiple handlers at once
export function registerWebSocketHandlers(
  client: WebSocketClient,
  handlers: WebSocketMessageHandlers,
): () => void {
  const unsubscribeFunctions: (() => void)[] = [];

  // Register streaming event handlers (using snake_case event types from backend)
  if (handlers.onContentEvent) {
    unsubscribeFunctions.push(
      client.onStreamingEvent('content', (event) =>
        handlers.onContentEvent!(event as ContentEvent),
      ),
    );
  }
  if (handlers.onReasoningEvent) {
    unsubscribeFunctions.push(
      client.onStreamingEvent('reasoning', (event) =>
        handlers.onReasoningEvent!(event as ReasoningEvent),
      ),
    );
  }
  if (handlers.onResponseStartEvent) {
    unsubscribeFunctions.push(
      client.onStreamingEvent('response_start', (event) =>
        handlers.onResponseStartEvent!(event as ResponseStartEvent),
      ),
    );
  }
  if (handlers.onResponseEndEvent) {
    unsubscribeFunctions.push(
      client.onStreamingEvent('response_end', (event) =>
        handlers.onResponseEndEvent!(event as ResponseEndEvent),
      ),
    );
  }
  if (handlers.onStatusEvent) {
    unsubscribeFunctions.push(
      client.onStreamingEvent('status', (event) =>
        handlers.onStatusEvent!(event as StatusEvent),
      ),
    );
  }
  if (handlers.onErrorEvent) {
    unsubscribeFunctions.push(
      client.onStreamingEvent('error', (event) =>
        handlers.onErrorEvent!(event as ErrorEvent),
      ),
    );
  }
  if (handlers.onToolCallEvent) {
    unsubscribeFunctions.push(
      client.onStreamingEvent('tool_call', (event) =>
        handlers.onToolCallEvent!(event as ToolCallEvent),
      ),
    );
  }
  if (handlers.onToolReturnEvent) {
    unsubscribeFunctions.push(
      client.onStreamingEvent('tool_return', (event) =>
        handlers.onToolReturnEvent!(event as ToolReturnEvent),
      ),
    );
  }
  if (handlers.onMetadataEvent) {
    unsubscribeFunctions.push(
      client.onStreamingEvent('metadata', (event) =>
        handlers.onMetadataEvent!(event as MetadataEvent),
      ),
    );
  }
  if (handlers.onDocumentEvent) {
    unsubscribeFunctions.push(
      client.onStreamingEvent('document', (event) =>
        handlers.onDocumentEvent!(event as DocumentEvent),
      ),
    );
  }
  if (handlers.onCitationEvent) {
    unsubscribeFunctions.push(
      client.onStreamingEvent('citation', (event) =>
        handlers.onCitationEvent!(event as CitationEvent),
      ),
    );
  }

  // Register connection event handlers
  if (handlers.onConnectionEstablished) {
    unsubscribeFunctions.push(
      client.onMessage(
        WSMessageType.CONNECTION_ESTABLISHED,
        handlers.onConnectionEstablished,
      ),
    );
  }
  if (handlers.onError) {
    unsubscribeFunctions.push(client.onError(handlers.onError));
  }
  if (handlers.onClose) {
    unsubscribeFunctions.push(client.onClose(handlers.onClose));
  }

  // Return function to unsubscribe from all handlers
  return () => {
    unsubscribeFunctions.forEach((unsub) => unsub());
  };
}
