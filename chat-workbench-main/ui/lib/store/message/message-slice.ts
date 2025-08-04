// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// lib/store/message-slice.ts
import { create } from 'zustand';
import { MessageState } from '@/lib/store/message/message-types';
import { MessagePart } from '@/lib/types';
import { storeRegistry, listenerRegistry } from '@/lib/store/message/registry';

// Import debug utilities in development mode
if (process.env.NODE_ENV !== 'production') {
  import('./debug-logs').catch((err) =>
    console.log('Debug utilities not loaded:', err),
  );
}

// Import functionality from our separated modules
import {
  initializeWsHandlers,
  interruptStream,
} from '@/lib/store/message/message-handlers';
import {
  updateMessageContent,
  updateMessageStatus,
  appendToMessage,
  setActiveMessagePath,
  getMessageChildren,
  getMessageSiblings,
  navigateMessageBranch,
  editMessage as editMessageCore,
  regenerateMessage as regenerateMessageCore,
  messageHasNextSibling,
  messageHasPreviousSibling,
  addDocumentToMessage,
  startMessageGeneration as startMessageGenerationCore,
  clearMessages,
} from './message-core';
import {
  fetchChats,
  fetchChat,
  createChat,
  updateChatTitle,
  deleteChat,
  fetchMessages,
  clearChatMessages,
} from './chat-slice';

// Create event cleanup registry to properly remove event listeners
const eventCleanupFunctions: Array<() => void> = [];

// Helper to attach event with proper cleanup registration
const safeAddEventListener = (
  target: EventTarget,
  event: string,
  handler: EventListenerOrEventListenerObject,
): void => {
  // Add the event listener
  target.addEventListener(event, handler);

  // Register a cleanup function
  eventCleanupFunctions.push(() => {
    target.removeEventListener(event, handler);
    console.debug(`Removed event listener for ${event}`);
  });

  console.debug(
    `Added event listener for ${event} (total active: ${eventCleanupFunctions.length})`,
  );
};

// Function to clean up all registered event listeners
const cleanupAllEventListeners = (): void => {
  while (eventCleanupFunctions.length > 0) {
    const cleanup = eventCleanupFunctions.pop();
    if (cleanup) cleanup();
  }
  console.debug('All event listeners cleaned up');
};

// Create or reuse the message store - done outside of conditionals to avoid export errors
let messageStore: any;

// Check if we've already created a message store
const existingStore = storeRegistry.getStoreInstance();
if (existingStore) {
  console.debug('Reusing existing message store instance');
  messageStore = existingStore;
} else {
  console.debug('Creating new message store instance');

  // Create the zustand store
  messageStore = storeRegistry.registerStoreInstance(
    create<MessageState>((set, get) => {
      // Set up event listener for auth logout events with proper registration
      if (typeof window !== 'undefined') {
        // Register that we're adding an auth logout listener
        listenerRegistry.registerAuthLogoutListener();

        const logoutHandler = () => {
          console.debug('Auth logout detected, clearing state');
          // Safe to use get() here since the store is already initialized
          get().clearMessages();
          console.debug('State cleared due to logout');
        };

        // Add the event listener with cleanup registration
        safeAddEventListener(window, 'auth:logout', logoutHandler);
      }

      // Return the store state and actions
      return {
        // Initial state
        messages: {},
        messagesByChat: {},
        activeMessagePath: {},
        isStreaming: false,
        currentStreamingId: null,
        pendingChatId: null,
        pendingContent: null,
        pendingParentId: null,
        error: null,
        chats: [],
        isLoadingChats: false,
        wsHandlersInitialized: false,
        messageStatus: {},
        messageMetadata: {},
        usageStats: {},

        // Event buffering state
        contentEventBuffer: {},
        documentEventBuffer: {},
        bufferTimeouts: {},
        bufferStats: {
          totalEvents: 0,
          bufferedEvents: 0,
          immediateEvents: 0,
        },

        // Research progress state
        researchProgress: {},

        // Chat-related functions
        fetchChats: (userId, limit) => fetchChats(get, set, userId, limit),
        fetchChat: (chatId) => fetchChat(get, set, chatId),
        createChat: (title, userId) => createChat(get, set, title, userId),
        updateChatTitle: (chatId, title) =>
          updateChatTitle(get, set, chatId, title),
        deleteChat: (chatId) => deleteChat(get, set, chatId),
        fetchMessages: (chatId) => fetchMessages(get, set, chatId),

        // Message generation and WebSocket handlers
        startMessageGeneration: (chatId, content, parentId) =>
          startMessageGenerationCore(get, set, chatId, content, parentId),
        initializeWsHandlers: () => initializeWsHandlers(get, set),
        interruptStream: () => interruptStream(get, set),

        // Message manipulation functions
        updateMessageContent: (messageId, content) =>
          updateMessageContent(get, set, messageId, content),
        updateMessageStatus: (messageId, status) =>
          updateMessageStatus(get, set, messageId, status),
        appendToMessage: (messageId, contentDelta) =>
          appendToMessage(get, set, messageId, contentDelta),
        setActiveMessagePath: (chatId, messageIds) =>
          setActiveMessagePath(get, set, chatId, messageIds),
        navigateMessageBranch: (chatId, messageId, direction) =>
          navigateMessageBranch(get, set, chatId, messageId, direction),
        addDocumentToMessage: (messageId, documentEvent) =>
          addDocumentToMessage(get, set, messageId, documentEvent),

        // Message query functions
        getMessageChildren: (messageId) => getMessageChildren(get, messageId),
        getMessageSiblings: (messageId) => getMessageSiblings(get, messageId),
        messageHasNextSibling: (messageId) =>
          messageHasNextSibling(get, messageId),
        messageHasPreviousSibling: (messageId) =>
          messageHasPreviousSibling(get, messageId),

        // Editing and regeneration
        editMessage: (messageId, newContent) => {
          const startMessageGeneration = (
            chatId: string,
            content: string | MessagePart[] | any[],
            parentId?: string | null,
          ) => startMessageGenerationCore(get, set, chatId, content, parentId);
          return editMessageCore(
            get,
            set,
            startMessageGeneration,
            messageId,
            newContent,
          );
        },
        regenerateMessage: (messageId) => {
          const startMessageGeneration = (
            chatId: string,
            content: string | MessagePart[] | any[],
            parentId?: string | null,
          ) => startMessageGenerationCore(get, set, chatId, content, parentId);
          return regenerateMessageCore(
            get,
            set,
            startMessageGeneration,
            messageId,
          );
        },

        // Research progress actions
        updateResearchProgress: (messageId, phase, isResearching = true) => {
          set((state) => ({
            researchProgress: {
              ...state.researchProgress,
              [messageId]: {
                isResearching,
                phase,
                completedAt:
                  phase === 'complete' ? new Date().toISOString() : null,
                totalPhases:
                  (state.researchProgress[messageId]?.totalPhases || 0) +
                  (phase !== state.researchProgress[messageId]?.phase ? 1 : 0),
              },
            },
          }));
        },
        completeResearch: (messageId) => {
          set((state) => ({
            researchProgress: {
              ...state.researchProgress,
              [messageId]: {
                ...state.researchProgress[messageId],
                isResearching: false,
                phase: 'complete',
                completedAt: new Date().toISOString(),
              },
            },
          }));
        },
        isMessageResearching: (messageId) => {
          const state = get();
          return state.researchProgress[messageId]?.isResearching || false;
        },
        getResearchPhase: (messageId) => {
          const state = get();
          return state.researchProgress[messageId]?.phase || null;
        },

        // Cleanup functions
        clearMessages: () => {
          // Clean up event listeners when clearing messages to prevent memory leaks
          cleanupAllEventListeners();
          // Then clear the actual messages
          clearMessages(set);
        },
        clearChatMessages: (chatId) => clearChatMessages(get, set, chatId),
      };
    }),
  );
}

// Export the message store (either the existing one or the newly created one)
export const useMessageStore = messageStore;
