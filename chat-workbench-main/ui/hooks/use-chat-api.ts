// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/index';
import {
  ChatSession,
  CreateChatRequest,
  UpdateChatRequest,
  GenerateRequest,
  MessagePart,
} from '@/lib/types';
import { useAuth } from 'react-oidc-context';

// Query keys for React Query
export const chatKeys = {
  all: ['chats'] as const,
  lists: () => [...chatKeys.all, 'list'] as const,
  list: (filters: { userId?: string; limit?: number } = {}) =>
    [...chatKeys.lists(), filters] as const,
  details: () => [...chatKeys.all, 'detail'] as const,
  detail: (id: string) => [...chatKeys.details(), id] as const,
};

// Hook for fetching chat list
export function useChats(userId?: string, limit = 100) {
  const auth = useAuth();
  // Use the provided userId or get it from auth context
  const currentUserId = userId || auth.user?.profile.sub;

  // Log the auth state and user ID for debugging
  console.debug('Auth state:', {
    isAuthenticated: auth.isAuthenticated,
    hasUser: !!auth.user,
    hasToken: !!auth.user?.access_token,
    userId: currentUserId,
    providedUserId: userId,
  });

  return useQuery({
    queryKey: chatKeys.list({ userId: currentUserId, limit }),
    queryFn: () => {
      console.debug('Making API call with userId:', currentUserId);
      // Always explicitly pass the user ID in the API call
      return api.getChats(limit, currentUserId);
    },
    select: (data) => {
      console.debug('Received chats:', data);
      return data.chats;
    },
    enabled: !!currentUserId && auth.isAuthenticated, // Only run query when authenticated with valid user ID
    staleTime: 30000, // 30 seconds
    retry: 1,
  });
}

// Hook for fetching a single chat
export function useChat(chatId: string) {
  // Get current user ID from auth context
  const auth = useAuth();
  const currentUserId = auth.user?.profile.sub;

  return useQuery({
    queryKey: chatKeys.detail(chatId),
    queryFn: () => api.getChat(chatId),
    // Only fetch when we have both a valid chat ID and authenticated user
    enabled: chatId !== 'new' && !!currentUserId && auth.isAuthenticated,
  });
}

// Hook for creating a new chat
export function useCreateChat() {
  const queryClient = useQueryClient();
  const auth = useAuth();
  const userId = auth.user?.profile.sub;

  return useMutation({
    mutationFn: (request: CreateChatRequest) => {
      // Always ensure there's a user_id in the request
      if (!request.user_id && userId) {
        request.user_id = userId;
      }

      if (!request.user_id) {
        throw new Error('No authenticated user found for creating chat');
      }

      return api.createChat(request);
    },
    onSuccess: (newChat) => {
      // Invalidate chat lists
      queryClient.invalidateQueries({ queryKey: chatKeys.lists() });

      // Add the new chat to the cache
      queryClient.setQueryData(chatKeys.detail(newChat.chat_id), newChat);
    },
  });
}

// Hook for updating a chat
export function useUpdateChat() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      chatId,
      request,
    }: {
      chatId: string;
      request: UpdateChatRequest;
    }) => api.updateChat(chatId, request),
    onSuccess: (updatedChat) => {
      // Update the chat in the cache
      queryClient.setQueryData(
        chatKeys.detail(updatedChat.chat_id),
        updatedChat,
      );

      // Invalidate chat lists to reflect the update
      queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
    },
  });
}

// Hook for deleting a chat
export function useDeleteChat() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (chatId: string) => api.deleteChat(chatId),
    onSuccess: (_, chatId) => {
      // Remove the chat from the cache
      queryClient.removeQueries({ queryKey: chatKeys.detail(chatId) });

      // Invalidate chat lists to reflect the deletion
      queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
    },
  });
}

// Hook for sending a message and generating a response
export function useSendMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      chatId,
      content,
      modelId,
      personaId,
      createChatIfNeeded = true,
      title,
    }: {
      chatId: string | null;
      content: string;
      modelId: string;
      personaId: string | null;
      createChatIfNeeded?: boolean;
      title?: string;
    }) => {},
  });
}
