// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// lib/store/message-handlers.ts
import { MessageState } from '@/lib/store/message/message-types';
import { wsHandlerRegistry } from '@/lib/store/message/registry';
import {
  WSMessageType,
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
} from '@/lib/services/websocket-types';
import {
  getWebSocketClient,
  registerWebSocketHandlers,
} from '@/lib/services/websocket-service';
import { Message, MessagePart } from '@/lib/types';
import { logger } from '@/lib/utils/logger';
import { useCitationStore } from '@/lib/store/citation-slice';

// Initialize WebSocket event handlers
export const initializeWsHandlers = (
  get: () => MessageState,
  set: (
    state:
      | Partial<MessageState>
      | ((state: MessageState) => Partial<MessageState>),
  ) => void,
) => {
  // Check if handlers are already initialized to prevent duplicate registrations
  // First check the global registry (most reliable)
  if (wsHandlerRegistry.isInitialized()) {
    console.debug(
      'WebSocket handlers already initialized (from registry), skipping',
    );
    return;
  }

  // Also check the store state for backwards compatibility
  if (get().wsHandlersInitialized) {
    console.debug(
      'WebSocket handlers already initialized (from store state), skipping',
    );
    return;
  }

  try {
    const ws = getWebSocketClient();

    // Register streaming event handlers using the new system
    registerWebSocketHandlers(ws, {
      // Handle response start events (replaces METADATA)
      onResponseStartEvent: (event: ResponseStartEvent) => {
        console.debug('Response start event received:', event);
        const { request_id, response_id, chat_id } = event;
        const { pendingChatId, pendingContent, pendingParentId } = get();

        console.debug('Current pending state:', {
          pendingChatId,
          pendingContent: typeof pendingContent,
          pendingParentId,
        });

        if (!pendingChatId || !pendingContent) {
          console.warn('Missing pending state, skipping response start');
          return;
        }

        // Validate that the chat_id matches pending chat
        if (chat_id !== pendingChatId) {
          console.warn('Chat ID mismatch:', {
            eventChatId: chat_id,
            pendingChatId,
          });
        }

        // Create user message with the server-assigned ID
        let userParts: MessagePart[];

        // Handle different types of pendingContent
        if (Array.isArray(pendingContent)) {
          // If pendingContent is already an array of parts, use it directly
          userParts = pendingContent as MessagePart[];
        } else {
          // Otherwise treat it as a string
          userParts = [
            {
              content: String(pendingContent),
              part_kind: 'text',
              timestamp: new Date().toISOString(),
            },
          ];
        }

        const userMessage: Message = {
          message_id: request_id,
          chat_id: chat_id, // Use chat_id from event for consistency
          parent_id: pendingParentId,
          kind: 'request',
          parts: userParts,
          timestamp: new Date().toISOString(),
          status: 'complete',
        };

        // Create empty response message that will receive streaming content
        const responseMessage: Message = {
          message_id: response_id,
          chat_id: chat_id, // Use chat_id from event for consistency
          parent_id: request_id,
          kind: 'response',
          parts: [
            {
              content: '',
              part_kind: 'text',
              timestamp: new Date().toISOString(),
            },
          ],
          timestamp: new Date().toISOString(),
          status: 'streaming',
        };

        console.debug('Creating messages:', {
          requestId: request_id,
          responseId: response_id,
          chatId: chat_id,
          userMessage: userMessage.parts[0].content,
          responseMessage: ' ',
        });

        // Update state with both messages AND initialize research state immediately
        set((state) => {
          // Add messages to chat's message list
          const chatMessages = [
            ...(state.messagesByChat[chat_id] || []),
            request_id,
            response_id,
          ];

          // Update active path to include new messages
          let messagePath = [...(state.activeMessagePath[chat_id] || [])];

          // If this is a regeneration or branch (has parent), insert after parent
          if (pendingParentId) {
            const parentIndex = messagePath.indexOf(pendingParentId);
            if (parentIndex !== -1) {
              // Replace everything after parent with new request/response pair
              messagePath = [
                ...messagePath.slice(0, parentIndex + 1),
                request_id,
                response_id,
              ];
            } else {
              // Parent not in current path, append to end
              messagePath.push(request_id, response_id);
            }
          } else {
            // No parent, start a new thread
            messagePath = [request_id, response_id];
          }

          const newState = {
            // Add both messages to store
            messages: {
              ...state.messages,
              [request_id]: userMessage,
              [response_id]: responseMessage,
            },
            messagesByChat: {
              ...state.messagesByChat,
              [chat_id]: chatMessages,
            },
            activeMessagePath: {
              ...state.activeMessagePath,
              [chat_id]: messagePath,
            },
            // Initialize research state IMMEDIATELY for the response message
            // This ensures content filtering works from the very first content event
            researchProgress: {
              ...state.researchProgress,
              [response_id]: {
                isResearching: true,
                phase: 'start' as const,
                completedAt: null,
                totalPhases: 1,
              },
            },
            // Clear pending state now that we have real messages
            pendingChatId: null,
            pendingContent: null,
            pendingParentId: null,
            // Track the streaming message
            currentStreamingId: response_id,
          };

          console.debug('State updated with messages:', {
            messageIds: [request_id, response_id],
            messageCount: Object.keys(newState.messages).length,
            currentStreamingId: response_id,
            activePath: messagePath,
          });

          // Verify messages were created correctly
          console.debug('Verifying created messages:', {
            userMessageExists: !!newState.messages[request_id],
            responseMessageExists: !!newState.messages[response_id],
            userMessageContent:
              newState.messages[request_id]?.parts[0]?.content,
            responseMessageContent:
              newState.messages[response_id]?.parts[0]?.content,
          });

          return newState;
        });

        // Process any buffered content events for the newly created response message
        const bufferedContentEvents = get().contentEventBuffer[response_id];
        if (bufferedContentEvents && bufferedContentEvents.length > 0) {
          console.debug(
            'Processing buffered content events for:',
            response_id,
            bufferedContentEvents.length,
          );

          // Process each buffered event in order
          bufferedContentEvents.forEach((bufferedEvent, index) => {
            console.debug(
              `Processing buffered content event ${index + 1}/${bufferedContentEvents.length}:`,
              bufferedEvent.content,
            );
            get().appendToMessage(response_id, bufferedEvent.content);
          });
        }

        // Process any buffered document events for the newly created response message
        const bufferedDocumentEvents = get().documentEventBuffer[response_id];
        if (bufferedDocumentEvents && bufferedDocumentEvents.length > 0) {
          console.debug(
            'Processing buffered document events for:',
            response_id,
            bufferedDocumentEvents.length,
          );

          // Process each buffered document event
          bufferedDocumentEvents.forEach((bufferedEvent, index) => {
            console.debug(
              `Processing buffered document event ${index + 1}/${bufferedDocumentEvents.length}:`,
              bufferedEvent.title,
            );
            get().addDocumentToMessage(response_id, bufferedEvent);
          });
        }

        // Clean up buffers for this message after processing
        if (
          (bufferedContentEvents && bufferedContentEvents.length > 0) ||
          (bufferedDocumentEvents && bufferedDocumentEvents.length > 0)
        ) {
          const timeoutId = get().bufferTimeouts[response_id];
          if (timeoutId) {
            clearTimeout(timeoutId);
          }

          set((cleanupState) => {
            const { [response_id]: _content, ...remainingContentBuffers } =
              cleanupState.contentEventBuffer;
            const { [response_id]: _document, ...remainingDocumentBuffers } =
              cleanupState.documentEventBuffer;
            const { [response_id]: _timeout, ...remainingTimeouts } =
              cleanupState.bufferTimeouts;

            return {
              contentEventBuffer: remainingContentBuffers,
              documentEventBuffer: remainingDocumentBuffers,
              bufferTimeouts: remainingTimeouts,
            };
          });

          console.debug(
            'Completed processing buffered events for:',
            response_id,
          );
        }

        // Research state was already initialized atomically above during message creation
        // Log verification that it was set correctly
        const currentResearchState = get().researchProgress[response_id];
        console.debug(
          'Research state initialized for response message:',
          response_id,
          currentResearchState,
        );
      },

      // Handle content events (replaces PART_UPDATE)
      onContentEvent: (event: ContentEvent) => {
        console.debug('Content event received:', event);
        const { response_id, content } = event;

        // Use response_id from the event, or fall back to currentStreamingId if not provided
        const targetMessageId = response_id || get().currentStreamingId;

        if (!content || !targetMessageId) {
          console.warn('Cannot update content: Missing required data', {
            hasResponseId: !!response_id,
            hasCurrentStreamingId: !!get().currentStreamingId,
            hasContent: !!content,
          });
          return;
        }

        // Update stats
        set((state) => ({
          bufferStats: {
            ...state.bufferStats,
            totalEvents: state.bufferStats.totalEvents + 1,
          },
        }));

        // Check if message exists in store
        const currentState = get();
        const message = currentState.messages[targetMessageId];

        if (message) {
          // Message exists - process immediately (normal case)
          console.debug(
            `Processing content immediately for ${targetMessageId}:`,
            content,
          );

          // Update immediate processing stats
          set((state) => ({
            bufferStats: {
              ...state.bufferStats,
              immediateEvents: state.bufferStats.immediateEvents + 1,
            },
          }));

          get().appendToMessage(targetMessageId, content);
        } else {
          // Message doesn't exist yet - buffer the event (race condition)
          console.debug(
            `Buffering content event for ${targetMessageId} (message not ready yet):`,
            content,
          );

          // Update buffered events stats
          set((state) => ({
            bufferStats: {
              ...state.bufferStats,
              bufferedEvents: state.bufferStats.bufferedEvents + 1,
            },
          }));

          // Buffer the event
          set((state) => {
            const currentBuffer =
              state.contentEventBuffer[targetMessageId] || [];
            const updatedBuffer = [...currentBuffer, event];

            // Prevent buffer overflow
            const MAX_BUFFER_SIZE = 10;
            if (updatedBuffer.length > MAX_BUFFER_SIZE) {
              console.warn('Buffer overflow for message:', targetMessageId);
              // Process the oldest event anyway to prevent loss
              const oldestEvent = updatedBuffer.shift()!;
              console.debug(
                'Force processing oldest buffered event:',
                oldestEvent,
              );
              // Note: This will still fail but at least we're not accumulating indefinitely
            }

            const newState: any = {
              contentEventBuffer: {
                ...state.contentEventBuffer,
                [targetMessageId]: updatedBuffer,
              },
              bufferTimeouts: { ...state.bufferTimeouts },
            };

            // Set cleanup timeout if not already set
            if (!state.bufferTimeouts[targetMessageId]) {
              const BUFFER_TIMEOUT = 250; // Increased timeout to prevent premature cleanup
              const timeoutId = setTimeout(() => {
                console.warn('Buffer timeout for message:', targetMessageId);
                // Try one more time to process buffered events before cleanup
                const finalState = get();
                const finalMessage = finalState.messages[targetMessageId];
                const bufferedEvents =
                  finalState.contentEventBuffer[targetMessageId] || [];

                if (finalMessage && bufferedEvents.length > 0) {
                  logger.debug(
                    'MessageHandlers',
                    'Processing buffered events before cleanup',
                    {
                      targetMessageId,
                      bufferedCount: bufferedEvents.length,
                    },
                  );

                  // Process all buffered events in order
                  bufferedEvents.forEach((bufferedEvent, index) => {
                    try {
                      get().appendToMessage(
                        targetMessageId,
                        bufferedEvent.content,
                      );
                      logger.debug(
                        'MessageHandlers',
                        'Processed buffered event',
                        { index, targetMessageId },
                      );
                    } catch (error) {
                      logger.error(
                        'MessageHandlers',
                        'Error processing buffered event',
                        { error, index },
                      );
                    }
                  });
                }

                // Clean up buffer for this message
                set((cleanupState) => {
                  const { [targetMessageId]: _, ...remainingBuffers } =
                    cleanupState.contentEventBuffer;
                  const { [targetMessageId]: __, ...remainingTimeouts } =
                    cleanupState.bufferTimeouts;

                  return {
                    contentEventBuffer: remainingBuffers,
                    bufferTimeouts: remainingTimeouts,
                  };
                });
              }, BUFFER_TIMEOUT);

              newState.bufferTimeouts = {
                ...state.bufferTimeouts,
                [targetMessageId]: timeoutId,
              };
            }

            return newState;
          });
        }
      },

      // Handle response end events (replaces COMPLETE)
      onResponseEndEvent: (event: ResponseEndEvent) => {
        console.debug('Response end event received:', event);
        const { response_id, usage, status } = event;

        if (response_id) {
          // Check if there's an error status
          if (status === 'error') {
            console.debug('Response ended with error status');

            // Only set status to error if it's not already set
            // This prevents overriding the detailed error info set by onErrorEvent
            const message = get().messages[response_id];
            if (message && message.status !== 'error') {
              get().updateMessageStatus(response_id, 'error');
            }
          } else {
            // For non-error statuses, mark as complete
            get().updateMessageStatus(response_id, 'complete');
          }

          // Store usage statistics if available
          if (usage) {
            set((state) => ({
              usageStats: {
                ...state.usageStats,
                [response_id]: usage,
              },
            }));
          }

          // Reset streaming state
          set({
            isStreaming: false,
            currentStreamingId: null,
          });
        }
      },

      // Handle error events
      onErrorEvent: (event: ErrorEvent) => {
        console.log(
          'Raw error event structure:',
          JSON.stringify(event, null, 2),
        );

        // Extract error data from the correct location based on how message-slice.ts receives it
        // For error events from the 'error' message type
        let errorMessage: string = 'Unknown error';
        let errorType: string = 'Error';
        let errorDetails: any = null;
        let responseId: string | null = null;

        // Type guard to check if it's a proper ErrorEvent type
        const isErrorEvent = (e: any): e is ErrorEvent =>
          'error_type' in e && 'message' in e && 'response_id' in e;

        // Type guard for generic object with error properties
        const hasErrorProps = (e: any): boolean =>
          e && typeof e === 'object' && ('error' in e || 'error_type' in e);

        // Check if we're getting a direct ErrorEvent streaming event
        if (isErrorEvent(event)) {
          errorType = event.error_type;
          errorMessage = event.message || 'Unknown error';
          errorDetails = event.details;
          responseId = event.response_id;
          console.log('Processed as ErrorEvent:', {
            errorMessage,
            errorType,
          });
        }
        // Or if we're getting a WebSocket error message (which has error data nested in data property)
        else if (hasErrorProps(event)) {
          const eventObj = event as Record<string, any>;
          errorMessage = eventObj.error || 'Unknown error';
          errorType = eventObj.error_type || 'Error';
          errorDetails = eventObj.details || null;
          responseId = eventObj.response_id || null;
          console.log('Processed as object with error properties:', {
            errorMessage,
            errorType,
          });
        }

        console.log('Processed error data:', {
          errorMessage,
          errorType,
          responseId,
          errorDetailsPresent: !!errorDetails,
        });

        const targetMessageId = responseId || get().currentStreamingId;
        console.log('Target message for error:', targetMessageId);

        if (targetMessageId) {
          console.log('Setting error message on target:', targetMessageId);
          // Update message with error information
          set((state) => ({
            messages: {
              ...state.messages,
              [targetMessageId]: {
                ...state.messages[targetMessageId],
                status: 'error',
                eventType: 'error',
                eventData: {
                  message: errorMessage,
                  error_type: errorType,
                  details: errorDetails,
                },
              },
            },
          }));
        }

        // Update error state
        set({
          error: errorMessage || 'Generation interrupted or error occurred',
          isStreaming: false,
          currentStreamingId: null,
          pendingChatId: null,
          pendingContent: null,
          pendingParentId: null,
        });
      },

      // Handle status events
      onStatusEvent: (event: StatusEvent) => {
        console.debug('Status event received:', event);
        const { response_id, status, message } = event;

        if (response_id) {
          // Parse the message JSON if it exists
          let parsedMessage = null;
          if (message) {
            try {
              parsedMessage = JSON.parse(message);
              console.debug('Parsed status message:', parsedMessage);
            } catch (error) {
              console.warn('Failed to parse status message:', error);
            }
          }

          // Update message status and message data in store
          set((state) => ({
            messageStatus: {
              ...state.messageStatus,
              [response_id]: status,
            },
            // Store the parsed message data in messageMetadata
            messageMetadata: {
              ...state.messageMetadata,
              [response_id]: {
                ...(state.messageMetadata[response_id] || {}),
                statusMessage: parsedMessage,
              },
            },
          }));

          // Log the status update with title if available
          if (parsedMessage && parsedMessage.title) {
            console.debug(
              `Status update for ${response_id}: ${status} - ${parsedMessage.title}`,
            );
          }
        }
      },

      // Handle metadata events
      onMetadataEvent: (event: MetadataEvent) => {
        console.debug('Metadata event received:', event);
        const { response_id, metadata } = event;

        if (response_id && metadata) {
          set((state) => ({
            messageMetadata: {
              ...state.messageMetadata,
              [response_id]: {
                ...(state.messageMetadata[response_id] || {}),
                ...metadata,
              },
            },
          }));
        }
      },

      // Handle tool call events
      onToolCallEvent: (event: ToolCallEvent) => {
        console.debug('Tool call event received:', event);
        const { response_id, tool_name, tool_id, tool_args } = event;

        if (!response_id) {
          console.warn('Tool call event missing response_id:', event);
          return;
        }

        // Check if message is in research phase - skip tool call events during research
        const currentState = get();
        const isResearching = currentState.isMessageResearching(response_id);
        const researchPhase = currentState.getResearchPhase(response_id);

        if (isResearching || researchPhase !== 'complete') {
          console.debug(
            `Skipping tool call event during research phase for ${response_id}:`,
            {
              isResearching,
              researchPhase,
              toolName: tool_name,
            },
          );
          return;
        }

        // Check if message exists in store
        const message = currentState.messages[response_id];

        if (message) {
          // Message exists - update with tool call information in streaming fashion
          console.debug('Adding tool call to existing message:', response_id);

          set((state) => {
            // Get current event data
            const currentEventData =
              state.messages[response_id].eventData || {};

            // Prepare the tool args - for streaming we show each delta as it comes in
            const updatedToolArgs = {
              ...tool_args,
            };

            // If this is a new tool_call for this message, set the type and initial data
            // Otherwise keep existing data and just update with new event
            const existingToolName = currentEventData.tool_name;
            const isNewToolCall = !existingToolName;

            // Get the content block index and sequence if available
            // Access via eventData since these properties might not be on the event type directly
            const contentBlockIndex =
              currentEventData.contentBlockIndex ||
              (event as any).contentBlockIndex ||
              (event as any).content_block_index;
            const blockSequence =
              currentEventData.blockSequence ||
              (event as any).blockSequence ||
              (event as any).block_sequence;

            // Track this event in the history for proper segmentation
            const existingEventHistory = state.messages[response_id].eventData
              ?.eventHistory || { events: [] };
            const updatedEventHistory = {
              events: [
                ...existingEventHistory.events,
                {
                  type: 'tool_call',
                  content: '', // Tool calls don't have direct content
                  data: {
                    tool_name,
                    tool_id,
                    tool_args: updatedToolArgs,
                  },
                  contentBlockIndex,
                  blockSequence,
                  sequence: existingEventHistory.events.length,
                  timestamp: new Date().toISOString(),
                },
              ],
            };

            return {
              messages: {
                ...state.messages,
                [response_id]: {
                  ...state.messages[response_id],
                  eventType: 'tool_call', // Set type for correct renderer
                  eventData: {
                    ...(state.messages[response_id].eventData || {}),
                    tool_name: tool_name || existingToolName || '',
                    tool_id: tool_id || currentEventData.tool_id || '',
                    tool_args: updatedToolArgs,
                    contentBlockIndex,
                    blockSequence,
                    eventHistory: updatedEventHistory,
                  },
                },
              },
            };
          });
        } else {
          // Message doesn't exist yet - buffer event data for when message is created
          console.warn(
            'Tool call received but message not found:',
            response_id,
          );
        }
      },

      // Handle citation events
      onCitationEvent: (event: CitationEvent) => {
        logger.debug('MessageHandlers', 'Citation event received', { event });
        const {
          response_id,
          document_id,
          text,
          page,
          section,
          reference_number,
          document_title,
          document_pointer,
        } = event;

        if (!response_id || !document_id) {
          logger.warn(
            'MessageHandlers',
            'Citation event missing required fields',
            {
              hasResponseId: !!response_id,
              hasDocumentId: !!document_id,
              event,
            },
          );
          return;
        }

        // Get the citation store to add the citation
        const citationStore = useCitationStore.getState();
        if (!citationStore) {
          logger.error('MessageHandlers', 'Citation store not available');
          return;
        }

        // Generate citation ID if not provided
        const citation_id =
          event.citation_id || `citation-${response_id}-${Date.now()}`;

        // Add citation to the citation store
        try {
          citationStore.addCitation({
            citation_id,
            document_id,
            response_id,
            text: text || '',
            page,
            section,
            reference_number,
            document_title,
            document_pointer,
          });

          logger.debug('MessageHandlers', 'Citation added to store', {
            citation_id,
            document_id,
            response_id,
          });

          // If document info is included, add/update document as well
          if (document_title || document_pointer) {
            citationStore.addDocument({
              document_id,
              title: document_title || 'Unknown Document',
              pointer: document_pointer || '',
              mime_type: 'application/pdf', // Default mime type
            });

            logger.debug('MessageHandlers', 'Document added to store', {
              document_id,
              document_title,
            });
          }

          // Force message re-render to show citation markers
          const message = get().messages[response_id];
          if (message) {
            // Trigger a small update to force re-render
            get().appendToMessage(response_id, '');
          }
        } catch (error) {
          logger.error('MessageHandlers', 'Error processing citation event', {
            error,
            event,
          });
        }
      },

      // Handle document events
      onDocumentEvent: (event: DocumentEvent) => {
        console.debug('Document event received:', event);
        const { response_id } = event;

        if (!response_id) {
          console.warn('Document event missing response_id:', event);
          return;
        }

        // Check if message is in research phase - skip document events during research
        const currentState = get();
        const isResearching = currentState.isMessageResearching(response_id);
        const researchPhase = currentState.getResearchPhase(response_id);

        if (isResearching || researchPhase !== 'complete') {
          console.debug(
            `Skipping document event during research phase for ${response_id}:`,
            {
              isResearching,
              researchPhase,
              documentTitle: event.title,
            },
          );
          return;
        }

        // Check if message exists in store
        const message = currentState.messages[response_id];

        if (message) {
          // Message exists - add document immediately
          console.debug('Adding document to existing message:', response_id);
          get().addDocumentToMessage(response_id, event);
        } else {
          // Message doesn't exist yet - buffer the event
          console.debug('Buffering document event for:', response_id);

          set((state) => {
            const currentBuffer = state.documentEventBuffer[response_id] || [];
            const updatedBuffer = [...currentBuffer, event];

            // Prevent buffer overflow
            const MAX_BUFFER_SIZE = 10;
            if (updatedBuffer.length > MAX_BUFFER_SIZE) {
              console.warn(
                'Document buffer overflow for message:',
                response_id,
              );
              updatedBuffer.shift(); // Remove oldest event
            }

            const newState: any = {
              documentEventBuffer: {
                ...state.documentEventBuffer,
                [response_id]: updatedBuffer,
              },
              bufferTimeouts: { ...state.bufferTimeouts },
              bufferStats: {
                ...state.bufferStats,
                bufferedEvents: state.bufferStats.bufferedEvents + 1,
              },
            };

            // Set cleanup timeout if not already set
            if (!state.bufferTimeouts[response_id]) {
              const BUFFER_TIMEOUT = 100;
              const timeoutId = setTimeout(() => {
                console.warn(
                  'Document buffer timeout for message:',
                  response_id,
                );
                set((cleanupState) => {
                  const {
                    [response_id]: _content,
                    ...remainingContentBuffers
                  } = cleanupState.contentEventBuffer;
                  const {
                    [response_id]: _document,
                    ...remainingDocumentBuffers
                  } = cleanupState.documentEventBuffer;
                  const { [response_id]: _timeout, ...remainingTimeouts } =
                    cleanupState.bufferTimeouts;

                  return {
                    contentEventBuffer: remainingContentBuffers,
                    documentEventBuffer: remainingDocumentBuffers,
                    bufferTimeouts: remainingTimeouts,
                  };
                });
              }, BUFFER_TIMEOUT);

              newState.bufferTimeouts = {
                ...state.bufferTimeouts,
                [response_id]: timeoutId,
              };
            }

            return newState;
          });
        }
      },

      // Add a catch-all handler for any event type not specifically handled
      // This ensures no events are missed and makes the system more resilient
      onConnectionEstablished: (data) => {
        console.debug('WebSocket connection established');

        // Register a catch-all handler for all events to ensure nothing is missed
        const ws = getWebSocketClient();
        ws.onStreamingEvent('*', (event) => {
          // Skip event types that already have specific handlers
          const handledTypes = [
            'content',
            'reasoning',
            'response_start',
            'response_end',
            'status',
            'error',
            'tool_call',
            'tool_return',
            'metadata',
            'document',
            'citation',
          ];

          if (handledTypes.includes(event.type)) {
            return; // Skip handled event types
          }

          console.debug(
            `Catch-all handler processing unhandled event type: ${event.type}`,
            event,
          );

          // Generic processing for unknown event types
          const { response_id, type } = event;
          if (response_id) {
            const message = get().messages[response_id];
            if (message) {
              set((state) => ({
                messages: {
                  ...state.messages,
                  [response_id]: {
                    ...state.messages[response_id],
                    eventType: type,
                    eventData: event,
                  },
                },
              }));
            } else {
              console.debug(
                `Message ${response_id} not found for event type ${type}`,
              );
            }
          }
        });
      },

      // Handle WebSocket errors
      onError: (error) => {
        console.error('WebSocket connection error:', error);
        set({
          error: 'WebSocket connection error. Please try again.',
          isStreaming: false,
          currentStreamingId: null,
        });
      },

      // Handle WebSocket close
      onClose: () => {
        console.debug('WebSocket connection closed');
      },
    });

    console.debug('WebSocket handlers initialized successfully');

    // Mark handlers as initialized in both the registry and store state
    wsHandlerRegistry.markInitialized();
    set({ wsHandlersInitialized: true });
  } catch (error) {
    console.error('Failed to initialize WebSocket handlers:', error);
  }
};

// Function to interrupt the current generation stream
export const interruptStream = (
  get: () => MessageState,
  set: (state: Partial<MessageState>) => void,
) => {
  const ws = getWebSocketClient();
  if (ws.isConnected()) {
    ws.interrupt();

    const { currentStreamingId } = get();
    if (currentStreamingId) {
      // Update message status to complete (even though interrupted)
      get().updateMessageStatus(currentStreamingId, 'complete');
    }

    set({
      isStreaming: false,
      currentStreamingId: null,
      pendingChatId: null,
      pendingContent: null,
      pendingParentId: null,
    });
  }
};
