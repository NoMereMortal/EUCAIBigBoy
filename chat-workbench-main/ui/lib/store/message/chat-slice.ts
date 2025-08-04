// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// lib/store/chat-slice.ts
import { MessageState } from '@/lib/store/message/message-types';
import { api } from '@/lib/api/index';
import { ChatSession } from '@/lib/types';

// Fetch all chats for the current user
export const fetchChats = async (
  get: () => MessageState,
  set: (state: Partial<MessageState>) => void,
  userId?: string,
  limit: number = 100,
) => {
  const { isLoadingChats } = get();

  // Don't fetch if we're already loading
  if (isLoadingChats) {
    return;
  }

  set({ isLoadingChats: true });
  try {
    if (!userId) {
      console.error('No user ID provided for fetchChats');
      set({ isLoadingChats: false });
      return;
    }

    const response = await api.getChats(limit, userId);
    set({
      chats: response.chats as unknown as ChatSession[],
      isLoadingChats: false,
    });
  } catch (error) {
    console.error('Failed to fetch chats:', error);
    set({ isLoadingChats: false });
  }
};

// Fetch a single chat by ID
export const fetchChat = async (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  chatId: string,
) => {
  // Skip API calls during SSR
  if (typeof window === 'undefined') return null;

  // Check for provided chat ID
  if (!chatId) {
    console.warn('No chat ID provided for fetchChat');
    return null;
  }

  try {
    const chat = (await api.getChat(chatId)) as unknown as ChatSession;

    // Update the chat in the store
    set((state) => {
      const updatedChats = state.chats.map((c) =>
        c.chat_id === chatId ? chat : c,
      );

      // Add the chat if it doesn't exist in the store
      if (!updatedChats.some((c) => c.chat_id === chatId)) {
        updatedChats.push(chat);
      }

      return {
        chats: updatedChats,
      };
    });

    return chat;
  } catch (error) {
    console.error('Failed to fetch chat:', error);
    return null;
  }
};

// Create a new chat
export const createChat = async (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  title: string,
  userId?: string,
) => {
  // Skip API calls during SSR - return early without throwing an error
  if (typeof window === 'undefined') {
    console.warn('Cannot create chat during server-side rendering');
    return Promise.reject(
      new Error('Cannot create chat during server-side rendering'),
    );
  }

  try {
    console.debug('Creating new chat:', { title, userId });

    if (!userId) {
      console.error('No user ID provided for createChat');
      throw new Error('No authenticated user ID provided');
    }

    const createRequest = {
      title,
      user_id: userId,
    };

    const newChat = (await api.createChat(
      createRequest,
    )) as unknown as ChatSession;

    // Update state with new chat
    set((state) => ({
      chats: [newChat, ...state.chats],
    }));

    return newChat;
  } catch (error) {
    console.error('Failed to create chat:', error);
    throw error;
  }
};

// Update chat title
export const updateChatTitle = async (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  chatId: string,
  title: string,
) => {
  // Skip API calls during SSR
  if (typeof window === 'undefined') return;

  try {
    await api.updateChat(chatId, { title });

    set((state) => {
      const updatedChats = state.chats.map((chat) =>
        chat.chat_id === chatId ? { ...chat, title } : chat,
      );

      return { chats: updatedChats };
    });
  } catch (error) {
    console.error('Failed to update chat title:', error);
  }
};

// Delete chat
export const deleteChat = async (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  chatId: string,
) => {
  // Skip API calls during SSR
  if (typeof window === 'undefined') {
    console.warn('Cannot delete chat during server-side rendering');
    return Promise.reject(
      new Error('Cannot delete chat during server-side rendering'),
    );
  }

  try {
    await api.deleteChat(chatId);

    set((state) => {
      // Remove the chat from the list
      const updatedChats = state.chats.filter(
        (chat) => chat.chat_id !== chatId,
      );

      // Clean up related message state
      const { [chatId]: _, ...remainingMessagesByChat } = state.messagesByChat;
      const { [chatId]: __, ...remainingActivePath } = state.activeMessagePath;

      // Remove messages for this chat
      const updatedMessages = { ...state.messages };
      const chatMessageIds = state.messagesByChat[chatId] || [];
      chatMessageIds.forEach((msgId) => {
        delete updatedMessages[msgId];
      });

      return {
        chats: updatedChats,
        messagesByChat: remainingMessagesByChat,
        activeMessagePath: remainingActivePath,
        messages: updatedMessages,
      };
    });
  } catch (error) {
    console.error('Failed to delete chat:', error);
    throw error;
  }
};

// Fetch messages for a specific chat
export const fetchMessages = async (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  chatId: string,
) => {
  try {
    // Skip API calls during SSR
    if (typeof window === 'undefined') return;

    console.debug('Fetching messages for chat:', chatId);
    const chatResponse = await api.getChat(chatId);

    if (!chatResponse || !chatResponse.messages) {
      console.error('No messages returned for chat', chatId);
      return;
    }

    console.debug('Received messages:', chatResponse.messages.length);

    set((state) => {
      // Process and organize messages
      const messagesById: Record<string, any> = {};
      const chatMessageIds: string[] = [];

      // First pass to collect all messages by ID
      chatResponse.messages.forEach((message) => {
        messagesById[message.message_id] = message;
        chatMessageIds.push(message.message_id);
      });

      // Build the active message path
      let messagePath: string[] = [];
      if (chatResponse.messages.length > 0) {
        // Find root messages (those without parents or with parents outside the chat)
        const rootMessages = chatResponse.messages
          .filter(
            (msg) => !msg.parent_id || !chatMessageIds.includes(msg.parent_id),
          )
          .sort(
            (a, b) =>
              new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
          );

        if (rootMessages.length > 0) {
          // Start with the oldest root message
          const currentMessage = rootMessages[0];

          // Track IDs that have already been included to prevent duplicates
          const seenMessageIds = new Set<string>([currentMessage.message_id]);

          // Helper function to get full descendant tree with duplicate prevention
          const getDescendantTree = (parentId: string): string[] => {
            const children = chatResponse.messages
              .filter((msg) => msg.parent_id === parentId)
              .sort(
                (a, b) =>
                  new Date(a.timestamp).getTime() -
                  new Date(b.timestamp).getTime(),
              );

            const result: string[] = [];
            for (const child of children) {
              // Only add if not already seen
              if (!seenMessageIds.has(child.message_id)) {
                result.push(child.message_id);
                seenMessageIds.add(child.message_id);
                // Get descendants, but only ones not already included
                result.push(...getDescendantTree(child.message_id));
              }
            }
            return result;
          };

          // Build path starting with root and including ALL descendants
          messagePath = [
            currentMessage.message_id,
            ...getDescendantTree(currentMessage.message_id),
          ];

          // Double check that there are no duplicates (protection layer)
          messagePath = messagePath.filter(
            (id, index) => messagePath.indexOf(id) === index,
          );
        }
      }

      // Preserve existing active path if we have streaming messages
      const currentPath = state.activeMessagePath[chatId] || [];
      const isStreaming = state.isStreaming && state.currentStreamingId;
      const hasStreamingMessage =
        isStreaming && currentPath.includes(state.currentStreamingId || '');

      // Use existing path if streaming, otherwise use the computed path
      const finalMessagePath = hasStreamingMessage ? currentPath : messagePath;

      console.debug('Active path decision:', {
        chatId,
        isStreaming,
        currentStreamingId: state.currentStreamingId,
        hasStreamingMessage,
        currentPathLength: currentPath.length,
        computedPathLength: messagePath.length,
        usingExistingPath: hasStreamingMessage,
      });

      return {
        messages: { ...state.messages, ...messagesById },
        messagesByChat: {
          ...state.messagesByChat,
          [chatId]: chatMessageIds,
        },
        activeMessagePath: {
          ...state.activeMessagePath,
          [chatId]: finalMessagePath,
        },
      };
    });
  } catch (error) {
    console.error('Failed to fetch messages:', error);
  }
};

// Clear messages for a specific chat
export const clearChatMessages = (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  chatId: string,
) => {
  set((state) => {
    // Get message IDs for this chat
    const chatMessageIds = state.messagesByChat[chatId] || [];

    // Create new messages object without this chat's messages
    const updatedMessages = { ...state.messages };
    chatMessageIds.forEach((messageId) => {
      delete updatedMessages[messageId];
    });

    // Remove chat from messagesByChat
    const { [chatId]: _, ...remainingMessagesByChat } = state.messagesByChat;

    // Remove chat from activeMessagePath
    const { [chatId]: __, ...remainingActivePaths } = state.activeMessagePath;

    return {
      messages: updatedMessages,
      messagesByChat: remainingMessagesByChat,
      activeMessagePath: remainingActivePaths,
    };
  });
};
