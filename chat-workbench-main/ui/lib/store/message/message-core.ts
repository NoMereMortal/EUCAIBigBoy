// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// lib/store/message-core.ts
import { MessageState } from '@/lib/store/message/message-types';
import { MessageStatus, MessagePart } from '@/lib/types';
import { DocumentEvent, WSMessageType } from '@/lib/services/websocket-types';
import { getWebSocketClient } from '@/lib/services/websocket-service';
import { storeRegistry } from '@/lib/store/message/registry';

// Update message content
export const updateMessageContent = (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  messageId: string,
  content: string,
) => {
  set((state) => {
    const message = state.messages[messageId];
    if (!message) return state;

    const updatedMessage = {
      ...message,
      parts: [
        {
          ...message.parts[0],
          content,
        },
        ...message.parts.slice(1),
      ],
    };

    return {
      messages: {
        ...state.messages,
        [messageId]: updatedMessage,
      },
    };
  });
};

// Update message status
export const updateMessageStatus = (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  messageId: string,
  status: MessageStatus,
) => {
  set((state) => {
    const message = state.messages[messageId];
    if (!message) return state;

    return {
      messages: {
        ...state.messages,
        [messageId]: {
          ...message,
          status,
        },
      },
    };
  });
};

// Append content to a streaming message (with defensive buffering)
export const appendToMessage = (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  messageId: string,
  contentDelta: string,
) => {
  console.debug('appendToMessage called:', {
    messageId,
    contentDelta,
  });

  // First check if message exists before calling set()
  const currentState = get();
  const message = currentState.messages[messageId];

  // Check if message is in research phase - skip content updates during research
  // This allows content events to reach StatusProgressPanel but not update message content
  const isResearching = currentState.isMessageResearching(messageId);
  const researchPhase = currentState.getResearchPhase(messageId);

  // Enhanced debug logging for research state tracking
  console.debug(`Research state check for ${messageId}:`, {
    isResearching,
    researchPhase,
    researchProgressExists: !!currentState.researchProgress[messageId],
    researchProgressData: currentState.researchProgress[messageId],
    contentPreview:
      contentDelta.substring(0, 100) + (contentDelta.length > 100 ? '...' : ''),
  });

  // Get the current task handler
  const selectedTaskHandler =
    typeof window !== 'undefined'
      ? localStorage.getItem('selectedTaskHandler') || 'chat'
      : 'chat';

  // Only skip content append for rag_oss task handler
  if (
    (isResearching || researchPhase !== 'complete') &&
    selectedTaskHandler === 'rag_oss'
  ) {
    console.debug(
      `Skipping content append during research phase for ${messageId}:`,
      {
        isResearching,
        researchPhase,
        taskHandler: selectedTaskHandler,
        reason: isResearching
          ? 'isResearching=true'
          : `researchPhase='${researchPhase}' (not complete)`,
        contentPreview: contentDelta.substring(0, 50),
      },
    );
    return;
  }

  if (!message) {
    console.warn(
      'Message not found in appendToMessage - using defensive buffering:',
      {
        targetId: messageId,
        availableIds: Object.keys(currentState.messages),
        storeSize: Object.keys(currentState.messages).length,
        currentStreamingId: currentState.currentStreamingId,
      },
    );

    // Create a synthetic content event for defensive buffering
    const syntheticEvent = {
      type: 'content',
      response_id: messageId,
      content: contentDelta,
      timestamp: new Date().toISOString(),
      sequence: 0,
      emit: true,
      persist: true,
    };

    // Use the same buffering logic as onContentEvent
    set((state) => {
      const currentBuffer = state.contentEventBuffer[messageId] || [];
      const updatedBuffer = [...currentBuffer, syntheticEvent];

      // Update defensive buffering stats
      const newBufferStats = {
        ...state.bufferStats,
        bufferedEvents: state.bufferStats.bufferedEvents + 1,
      };

      // Prevent buffer overflow
      const MAX_BUFFER_SIZE = 15; // Slightly higher for defensive buffering
      if (updatedBuffer.length > MAX_BUFFER_SIZE) {
        console.warn('Defensive buffer overflow for message:', messageId);
        // Drop oldest event to prevent memory issues
        updatedBuffer.shift();
      }

      const newState: any = {
        contentEventBuffer: {
          ...state.contentEventBuffer,
          [messageId]: updatedBuffer,
        },
        bufferTimeouts: { ...state.bufferTimeouts },
        bufferStats: newBufferStats,
      };

      // Set cleanup timeout if not already set
      if (!state.bufferTimeouts[messageId]) {
        const DEFENSIVE_BUFFER_TIMEOUT = 200; // Slightly longer timeout
        const timeoutId = setTimeout(() => {
          set((cleanupState) => {
            const { [messageId]: _, ...remainingBuffers } =
              cleanupState.contentEventBuffer;
            const { [messageId]: __, ...remainingTimeouts } =
              cleanupState.bufferTimeouts;

            return {
              contentEventBuffer: remainingBuffers,
              bufferTimeouts: remainingTimeouts,
            };
          });
        }, DEFENSIVE_BUFFER_TIMEOUT);

        newState.bufferTimeouts = {
          ...state.bufferTimeouts,
          [messageId]: timeoutId,
        };
      }

      console.debug('Content defensively buffered:', {
        messageId,
        bufferSize: updatedBuffer.length,
        totalBufferedEvents: newBufferStats.bufferedEvents,
      });

      return newState;
    });
    return; // Exit early - content is now buffered
  }

  // Message exists - proceed with normal processing
  set((state) => {
    console.debug('Found message, appending content:', {
      messageId,
      currentContent: message.parts[0]?.content || '',
      contentDelta,
      messageKind: message.kind,
      chatId: message.chat_id,
    });

    // create new message object to trigger re-render
    // Track all events that occur sequentially in the message
    // This allows us to properly segment different event types
    const existingEventHistory = message.eventData?.eventHistory || {
      events: [],
    };

    // Extract content block index and sequence if available
    const contentBlockIndex = message.eventData?.contentBlockIndex;
    const blockSequence = message.eventData?.blockSequence;

    // Add this content event to the history
    const updatedEventHistory = {
      events: [
        ...existingEventHistory.events,
        {
          type: 'content',
          content: contentDelta,
          contentBlockIndex: contentBlockIndex,
          blockSequence: blockSequence,
          sequence: existingEventHistory.events.length,
          timestamp: new Date().toISOString(),
          emit: true,
          persist: true,
        },
      ],
    };

    // Update message with new content and updated event history
    const updatedMessage = {
      ...message,
      parts: [
        {
          ...message.parts[0],
          content: (message.parts[0].content || '') + contentDelta,
        },
        ...message.parts.slice(1),
      ],
      // Keep track of all events for proper segmentation
      eventData: {
        ...(message.eventData || {}),
        eventHistory: updatedEventHistory,
      },
    };

    console.debug('Created updated message:', {
      messageId,
      newContent: updatedMessage.parts[0].content,
      contentLength: updatedMessage.parts[0].content.length,
    });

    // Get the chat ID for this message
    const chatId = message.chat_id;

    // Ensure message is in the active path for new chats
    const currentPath = state.activeMessagePath[chatId] || [];
    let updatedPath = [...currentPath];

    // If this is a new chat or message not in path, ensure both request and response are in the path
    if (currentPath.length === 0 || !currentPath.includes(messageId)) {
      if (message.kind === 'response' && message.parent_id) {
        // Make sure both the parent (user message) and this message are in the path
        updatedPath = [message.parent_id, messageId];
        console.debug('Ensuring message in active path:', updatedPath);
      }
    }

    const newState = {
      messages: {
        ...state.messages,
        [messageId]: updatedMessage,
      },
      currentStreamingId: messageId,
      // Ensure active message path is updated for new chats
      activeMessagePath: {
        ...state.activeMessagePath,
        [chatId]: updatedPath,
      },
    };

    console.debug('appendToMessage completed successfully:', {
      messageId,
      finalContentLength: newState.messages[messageId].parts[0].content.length,
      activePath: newState.activeMessagePath[chatId],
    });

    return newState;
  });
};

// Set the active path of messages for a chat
export const setActiveMessagePath = (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  chatId: string,
  messageIds: string[],
) => {
  // Deduplicate message IDs to prevent React key conflicts
  const uniqueMessageIds = messageIds.filter((id, index) => {
    return messageIds.indexOf(id) === index;
  });

  set((state) => ({
    activeMessagePath: {
      ...state.activeMessagePath,
      [chatId]: uniqueMessageIds,
    },
  }));
};

// Get all children of a message
export const getMessageChildren = (
  get: () => MessageState,
  messageId: string,
) => {
  const { messages } = get();

  return Object.values(messages)
    .filter((m) => m.parent_id === messageId)
    .map((m) => m.message_id);
};

// Get all siblings of a message (same parent)
export const getMessageSiblings = (
  get: () => MessageState,
  messageId: string,
) => {
  const { messages } = get();
  const message = messages[messageId];
  if (!message || !message.parent_id) return [];

  const siblings = Object.values(messages)
    .filter((m) => m.parent_id === message.parent_id)
    .sort((a, b) => {
      // Sort by timestamp (oldest first)
      return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
    })
    .map((m) => m.message_id);

  return siblings;
};

// Navigate between sibling messages (branches)
export const navigateMessageBranch = (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  chatId: string,
  messageId: string,
  direction: 'next' | 'previous',
) => {
  const { messages, activeMessagePath } = get();
  const currentPath = activeMessagePath[chatId] || [];
  if (currentPath.length === 0) return;

  const message = messages[messageId];
  if (!message) return;

  // Get siblings sorted by timestamp
  const siblings = getMessageSiblings(get, messageId);
  if (siblings.length === 0) return;

  // Find current index
  const currentIndex = siblings.indexOf(messageId);
  if (currentIndex === -1) return;

  let nextIndex;
  if (direction === 'next') {
    nextIndex = (currentIndex + 1) % siblings.length;
  } else {
    nextIndex = (currentIndex - 1 + siblings.length) % siblings.length;
  }

  // Find the sibling's messageId
  const siblingId = siblings[nextIndex];

  // Get current message index in path
  const pathIndex = currentPath.indexOf(messageId);
  if (pathIndex === -1) return;

  // Start new path with everything up to the navigation point
  const newPath = [...currentPath.slice(0, pathIndex), siblingId];

  // Track IDs that have already been included in the path to avoid duplicates
  const includedIds = new Set(newPath);

  // Helper function to get full descendant tree for a message
  const getDescendantTree = (parentId: string): string[] => {
    const children = Object.values(messages)
      .filter((m) => m.parent_id === parentId)
      .sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
      );

    const result: string[] = [];
    for (const child of children) {
      // Only add if not already in the path
      if (!includedIds.has(child.message_id)) {
        result.push(child.message_id);
        includedIds.add(child.message_id);
        // Get descendants, but only ones not already included
        result.push(...getDescendantTree(child.message_id));
      }
    }
    return result;
  };

  // Get deduplicated descendant tree of the selected sibling
  const descendants = getDescendantTree(siblingId);

  // Add all descendants to the path
  newPath.push(...descendants);

  // Update the active path
  setActiveMessagePath(get, set, chatId, newPath);
};

// Edit message and regenerate a response
export const editMessage = async (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  startMessageGeneration: (
    chatId: string,
    content: string | MessagePart[],
    parentId?: string | null,
  ) => Promise<void>,
  messageId: string,
  newContent: string,
) => {
  const { messages } = get();
  const message = messages[messageId];
  if (!message) return;

  // Update the message content
  updateMessageContent(get, set, messageId, newContent);

  // We'll create a new branch rather than removing old messages
  try {
    // Generate new response for the edited message
    await startMessageGeneration(
      message.chat_id,
      newContent,
      message.parent_id,
    );

    // The new response becomes part of the active path automatically
  } catch (error) {
    console.error('Failed to generate new response:', error);
    set({ error: 'Failed to generate new response' });
  }
};

// Regenerate a response message
export const regenerateMessage = async (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  startMessageGeneration: (
    chatId: string,
    content: string | MessagePart[],
    parentId?: string | null,
  ) => Promise<void>,
  messageId: string,
) => {
  const { messages } = get();
  const message = messages[messageId];
  if (!message) return;

  // Only responses can be regenerated
  if (message.kind !== 'response') return;

  // Find the parent message (request)
  const parentId = message.parent_id;
  if (!parentId) return;

  const parentMessage = messages[parentId];
  if (!parentMessage) return;

  // Get the original request content
  const requestContent = parentMessage.parts[0].content;

  // Get the chat ID
  const chatId = message.chat_id;

  try {
    // Don't remove existing children - just create a new branch
    await startMessageGeneration(
      chatId,
      requestContent,
      parentMessage.parent_id,
    );

    // After generation completes, update the active path to show the new branch
    // This happens automatically in startMessageGeneration's completion handler

    // Optionally update UI to indicate there are alternative branches
    console.debug('Created alternative branch via regeneration');
  } catch (error) {
    console.error('Failed to regenerate response:', error);
    set({ error: 'Failed to regenerate response' });
  }
};

// Check if a message has a next sibling
export const messageHasNextSibling = (
  get: () => MessageState,
  messageId: string,
) => {
  const { messages } = get();
  const message = messages[messageId];
  if (!message || !message.parent_id) return false;

  const siblings = getMessageSiblings(get, messageId);
  if (siblings.length <= 1) return false;

  // Sort siblings by timestamp
  siblings.sort((a, b) => {
    return new Date(messages[a].timestamp) > new Date(messages[b].timestamp)
      ? 1
      : -1;
  });

  const currentIndex = siblings.indexOf(messageId);
  return currentIndex < siblings.length - 1;
};

// Check if a message has a previous sibling
export const messageHasPreviousSibling = (
  get: () => MessageState,
  messageId: string,
) => {
  const { messages } = get();
  const message = messages[messageId];
  if (!message || !message.parent_id) return false;

  const siblings = getMessageSiblings(get, messageId);
  if (siblings.length <= 1) return false;

  // Sort siblings by timestamp
  siblings.sort((a, b) => {
    return new Date(messages[a].timestamp) > new Date(messages[b].timestamp)
      ? 1
      : -1;
  });

  const currentIndex = siblings.indexOf(messageId);
  return currentIndex > 0;
};

// Add document to message parts
export const addDocumentToMessage = (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  messageId: string,
  documentEvent: DocumentEvent,
) => {
  set((state) => {
    const message = state.messages[messageId];
    if (!message) {
      console.warn('Message not found for document:', messageId);
      return state;
    }

    const { title, pointer, mime_type, page_count, word_count } = documentEvent;

    // Create document part that conforms to MessagePart interface
    const documentPart: MessagePart = {
      part_kind: 'document',
      content: title || 'Document', // Use title as content, fallback to 'Document'
      metadata: {
        pointer,
        mime_type,
        title,
        page_count,
        word_count,
      },
      timestamp: new Date().toISOString(),
    };

    // Add document part to message
    const updatedMessage = {
      ...message,
      parts: [...message.parts, documentPart],
    };

    console.debug('Added document part to message:', {
      messageId,
      title,
      pointer,
      mime_type,
    });

    return {
      messages: {
        ...state.messages,
        [messageId]: updatedMessage,
      },
    };
  });
};

// Start message generation process
export const startMessageGeneration = async (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
  chatId: string,
  content: string | MessagePart[] | any[],
  parentId: string | null = null,
) => {
  // Update UI state to show pending/loading state
  set({
    isStreaming: true,
    pendingChatId: chatId,
    pendingContent: content,
    pendingParentId: parentId,
    error: null, // Clear any previous errors
  });

  try {
    // Get WebSocket client (should already be connected by auth provider)
    const ws = getWebSocketClient();

    // Check if WebSocket is connected, attempt to reconnect if not
    if (!ws.isConnected()) {
      console.log('WebSocket not connected, attempting to reconnect...');

      try {
        // First try to refresh auth token through the auth manager
        const { authManager } = await import('@/lib/auth/auth-manager');

        // Emit auth-changed event to trigger token refresh
        authManager.on('auth-changed', () => {
          console.log('Auth changed event received during reconnection');
        });

        // Wait a moment for any auth operations to complete
        await new Promise((resolve) => setTimeout(resolve, 500));

        // Now try to reconnect the WebSocket
        await ws.connect();

        // If still not connected after reconnection attempt, then throw error
        if (!ws.isConnected()) {
          throw new Error('WebSocket reconnection failed');
        }

        console.log('WebSocket reconnection successful');
      } catch (reconnectError) {
        console.error('WebSocket reconnection failed:', reconnectError);
        throw new Error(
          'WebSocket not connected. Please try logging out and back in.',
        );
      }
    }

    // Get model, persona, and task handler info - no fallbacks, model selection is required
    let selectedModelId: string | null = null;
    let selectedPersonaId = null;
    let selectedTaskHandler = 'chat'; // Default fallback

    try {
      // Access settings store via direct imported helper or fallback to dynamic import
      let settingsStore;

      console.debug('Starting settings store access...');

      try {
        // Try to get settings data from the global registry
        const globalStore = storeRegistry.getStoreInstance();
        console.debug('Global store from registry:', !!globalStore);

        if (globalStore && globalStore._settingsStore) {
          // Access settings store through the message store's reference
          settingsStore = globalStore._settingsStore;
          selectedPersonaId = settingsStore.getState().selectedPersonaId;

          // Get task handler with more detailed logging
          const settingsState = settingsStore.getState();
          selectedTaskHandler = settingsState.selectedTaskHandler || 'chat';

          console.debug('Retrieved task handler from settings:', {
            selectedTaskHandler,
            fromLocalStorage: localStorage.getItem('selectedTaskHandler'),
            settingsStateValue: settingsState.selectedTaskHandler,
          });
        } else {
          console.debug(
            'Registry store not available, trying dynamic import...',
          );
          // Fallback to dynamic import as a last resort
          const storeModule = await import('../index');
          console.debug('Store module imported:', !!storeModule?.useStore);

          if (storeModule && storeModule.useStore) {
            // Get the settings from the main store
            const mainStore = storeModule.useStore.getState();
            selectedPersonaId = mainStore.selectedPersonaId;
            // Create a fake settings store object with the method we need
            settingsStore = {
              getState: () => ({
                selectedModelId: mainStore.selectedModelId,
                selectedPersonaId: mainStore.selectedPersonaId,
                getEffectiveModelId: (defaultModelId: string | null) => {
                  // Implement the effective model ID logic directly
                  return mainStore.selectedModelId || defaultModelId;
                },
              }),
            };
            console.debug('Got settings from dynamic import (fallback):', {
              selectedModelId: mainStore.selectedModelId,
              selectedPersonaId: selectedPersonaId,
              hasGetEffectiveModelId: true,
            });
          }
        }
      } catch (settingsError) {
        console.warn('Error getting settings from registry:', settingsError);
        // Last resort fallback
        const storeModule = await import('../index');
        if (storeModule && storeModule.useStore) {
          const mainStore = storeModule.useStore.getState();
          selectedPersonaId = mainStore.selectedPersonaId;
          settingsStore = {
            getState: () => ({
              selectedModelId: mainStore.selectedModelId,
              selectedPersonaId: mainStore.selectedPersonaId,
              getEffectiveModelId: (defaultModelId: string | null) => {
                // Implement the effective model ID logic directly
                return mainStore.selectedModelId || defaultModelId;
              },
            }),
          };
          console.debug(
            'Got settings from dynamic import (fallback after error):',
            {
              selectedModelId: mainStore.selectedModelId,
              selectedPersonaId: selectedPersonaId,
              hasGetEffectiveModelId: true,
            },
          );
        }
      }

      // Get effective model ID using fallback logic
      if (settingsStore) {
        let defaultModelId: string | null = null;

        try {
          // Try to get models from React Query cache first
          const { queryClient } = await import('../../react-query');
          const cachedModels = queryClient.getQueryData(['models', 'list', {}]);

          if (
            cachedModels &&
            Array.isArray(cachedModels) &&
            cachedModels.length > 0
          ) {
            // Use cached models from React Query
            const availableModels = cachedModels
              .filter((model: any) => model.is_available)
              .sort((a: any, b: any) => (a.order || 0) - (b.order || 0));
            defaultModelId = availableModels[0]?.id || null;
            console.debug('Using cached models for default:', {
              cachedModelsCount: cachedModels.length,
              availableCount: availableModels.length,
              defaultModelId,
            });
          } else {
            // Fallback to fresh API call if no cached data
            console.debug('No cached models found, making fresh API call');
            const { modelApi } = await import('../../api/resources/model');
            const models = await modelApi.getModels();
            const availableModels = models
              .filter((model) => model.is_available)
              .sort((a, b) => (a.order || 0) - (b.order || 0));
            defaultModelId = availableModels[0]?.id || null;
            console.debug('Fresh API call results:', {
              modelsCount: models.length,
              availableCount: availableModels.length,
              defaultModelId,
            });
          }
        } catch (modelFetchError) {
          console.error('Error getting models for default:', modelFetchError);
          defaultModelId = null;
        }

        // Use the effective model ID (selected or default)
        selectedModelId = settingsStore
          .getState()
          .getEffectiveModelId(defaultModelId);
        console.debug('Using effective model ID:', {
          explicitlySelected: settingsStore.getState().selectedModelId,
          defaultModel: defaultModelId,
          effectiveModel: selectedModelId,
        });
      } else {
        console.warn(
          'Settings store not found, cannot determine effective model',
        );
      }

      // Final check - if still no model available, show error
      if (!selectedModelId) {
        throw new Error(
          'No models available. Please check your configuration or contact support.',
        );
      }
    } catch (error) {
      console.error('Error getting model information:', error);
      // Propagate the error up to show appropriate UI feedback
      set({
        error:
          error instanceof Error
            ? error.message
            : 'Failed to get model information',
        isStreaming: false,
        pendingChatId: null,
        pendingContent: null,
        pendingParentId: null,
      });
      throw error;
    }

    // Send the initialize message to start the generation
    let partsToSend;

    // Check if content is already an array of message parts
    if (Array.isArray(content)) {
      partsToSend = content;
    } else {
      // Otherwise treat it as a string and create a text part
      partsToSend = [{ part_kind: 'text', content }];
    }

    // Force refresh from localStorage if available
    if (typeof window !== 'undefined') {
      const storedTaskHandler = localStorage.getItem('selectedTaskHandler');
      if (storedTaskHandler) {
        console.debug(
          'Using task handler from localStorage:',
          storedTaskHandler,
        );
        selectedTaskHandler = storedTaskHandler;
      }
    }

    console.debug('Sending message to WebSocket', {
      chatId,
      parentId,
      modelId: selectedModelId,
      persona: selectedPersonaId,
      parts: partsToSend,
      task: selectedTaskHandler,
    });

    ws.send(WSMessageType.INITIALIZE, {
      task: selectedTaskHandler,
      chat_id: chatId,
      parent_id: parentId,
      model_id: selectedModelId,
      parts: partsToSend,
      persona: selectedPersonaId,
    });

    console.debug('Message sent to WebSocket successfully');
  } catch (error) {
    // Handle error
    console.error('Error sending message:', error);
    set({
      error:
        'Failed to send message: ' +
        (error instanceof Error ? error.message : 'Unknown error'),
      isStreaming: false,
      pendingChatId: null,
      pendingContent: null,
      pendingParentId: null,
    });
    throw error;
  }
};

// Clear all messages
export const clearMessages = (
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
) => {
  set((state) => ({
    messages: {},
    messagesByChat: {},
    activeMessagePath: {},
    isStreaming: false,
    currentStreamingId: null,
    pendingChatId: null,
    pendingContent: null,
    pendingParentId: null,
    error: null,
    chats: state.chats, // Keep existing chats instead of clearing them
    isLoadingChats: false,
    wsHandlersInitialized: false, // Reset WebSocket initialization flag
    messageStatus: {},
    messageMetadata: {},
    usageStats: {},
  }));
};
