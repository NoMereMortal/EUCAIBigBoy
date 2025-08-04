// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { apiClient } from '@/lib/api/client';
import { GenerateRequest } from '@/lib/types';
import { WSMessageType } from '@/lib/services/websocket-types';
import {
  WebSocketClient,
  getWebSocketClient,
} from '@/lib/services/websocket-service';

/**
 * Message generation API endpoints
 */
export const messageApi = {
  /**
   * Generate a message with streaming response
   */
  generateMessageStream: async (
    request: GenerateRequest,
  ): Promise<ReadableStream<Uint8Array> | null> => {
    return apiClient.stream('generate/stream', request);
  },

  /**
   * Generate a message with non-streaming response
   */
  generateMessage: async (request: GenerateRequest): Promise<any> => {
    return apiClient.post<any>('generate/invoke', request);
  },

  /**
   * Generate a message using WebSocket connection
   * Allows for bi-directional communication during generation
   */
  generateMessageWebSocket: async (
    request: GenerateRequest,
  ): Promise<WebSocketClient> => {
    // Skip API calls during SSR
    if (typeof window === 'undefined') {
      throw new Error('Cannot use WebSockets during server-side rendering');
    }

    // Use the singleton client instance from our service
    const wsClient = getWebSocketClient();
    await wsClient.connect();

    // Send initialization message
    wsClient.send(WSMessageType.INITIALIZE, request);

    return wsClient;
  },
};
