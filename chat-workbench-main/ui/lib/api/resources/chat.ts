// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { apiClient, isServer, getHeaders } from '@/lib/api/client';
import { ChatSession, CreateChatRequest, UpdateChatRequest } from '@/lib/types';

/**
 * Chat API endpoints
 */
export const chatApi = {
  /**
   * Create a new chat session
   */
  createChat: async (request: CreateChatRequest): Promise<ChatSession> => {
    // Skip API calls during SSR
    if (isServer()) {
      console.warn('Cannot create chat during server-side rendering');
      return Promise.reject(
        new Error('Cannot create chat during server-side rendering'),
      );
    }

    console.debug('Creating chat with request:', request);

    // Validate the user ID
    if (!request.user_id) {
      console.error('Missing user ID in createChat request');
      throw new Error('User ID is required to create a chat');
    }

    try {
      const headers = getHeaders();
      console.debug('Using auth headers:', headers);

      const chat = await apiClient.post<ChatSession>('chat', request);
      console.debug('Chat creation successful:', chat);
      return chat;
    } catch (error) {
      console.error('Chat creation failed:', error);
      if (error instanceof Error) {
        console.error('Error details:', error.message, error.stack);
      }
      throw error;
    }
  },

  /**
   * Get a list of chat sessions
   */
  getChats: async (
    limit = 10,
    userId?: string,
    lastKey?: string,
  ): Promise<{ chats: ChatSession[]; last_evaluated_key: any }> => {
    // Skip API calls during SSR
    if (isServer()) {
      console.warn('Cannot get chat list during server-side rendering');
      return { chats: [], last_evaluated_key: null };
    }

    // Require user ID to be provided explicitly
    if (!userId) {
      console.error('No user ID provided for getChats');
      throw new Error('User ID is required for chat operations');
    }

    console.debug('Using provided user ID:', userId);

    const params: Record<string, string | number | boolean> = {
      limit: limit,
      with_messages: 1,
      user_id: userId,
    };

    // Add lastKey only if it's defined
    if (lastKey) {
      params.last_key = lastKey;
    }

    return apiClient.get<{ chats: ChatSession[]; last_evaluated_key: any }>(
      'chat',
      params,
    );
  },

  /**
   * Get a specific chat session by ID
   */
  getChat: async (chatId: string): Promise<ChatSession> => {
    // Skip API calls during SSR
    if (isServer()) {
      console.warn('Cannot get chat during server-side rendering');
      return Promise.reject(
        new Error('Cannot get chat during server-side rendering'),
      );
    }

    // Verify we have a valid chat ID
    if (!chatId) {
      throw new Error('No chat ID provided for getChat operation');
    }

    return apiClient.get<ChatSession>(`chat/${chatId}`);
  },

  /**
   * Update a chat session
   */
  updateChat: async (
    chatId: string,
    request: UpdateChatRequest,
  ): Promise<ChatSession> => {
    // Skip API calls during SSR
    if (isServer()) {
      console.warn('Cannot update chat during server-side rendering');
      return Promise.reject(
        new Error('Cannot update chat during server-side rendering'),
      );
    }
    return apiClient.put<ChatSession>(`chat/${chatId}`, request);
  },

  /**
   * Delete a chat session
   */
  deleteChat: async (chatId: string): Promise<ChatSession> => {
    // Skip API calls during SSR
    if (isServer()) {
      console.warn('Cannot delete chat during server-side rendering');
      return Promise.reject(
        new Error('Cannot delete chat during server-side rendering'),
      );
    }
    return apiClient.delete<ChatSession>(`chat/${chatId}`);
  },
};
