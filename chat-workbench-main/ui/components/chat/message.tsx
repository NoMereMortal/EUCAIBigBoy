// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, useEffect, useRef } from 'react';
import { FileChip } from '@/components/chat/input/file-chip';
import { FileViewerModal } from '@/components/chat/file-viewer-modal';
import {
  Clipboard,
  CheckCircle2,
  Pencil,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useMessageStore } from '@/lib/store/message/message-slice';
import { useSettingsStore } from '@/lib/store/settings-slice';
import { getRendererForEventType } from '@/components/chat/message-renderers';
import { EventSegmentsManager } from '@/components/chat/message-renderers/event-segments-manager';
import { StatusProgressPanel } from '@/components/chat/status-progress-panel';
import { Message } from '@/lib/types';
import { MessageState } from '@/lib/store/message/message-types';

// Define interfaces for message parts
interface BaseMessagePart {
  part_kind: string;
  content?: string;
  metadata?: {
    filename?: string;
    preview_url?: string;
  };
  title?: string;
}

interface ImageMessagePart extends BaseMessagePart {
  part_kind: 'image';
  pointer: string;
  mime_type: string;
}

interface DocumentMessagePart extends BaseMessagePart {
  part_kind: 'document';
  pointer: string;
  mime_type: string;
}

type MessagePart = BaseMessagePart | ImageMessagePart | DocumentMessagePart;

// Props used by both UserMessage and AssistantMessage
export interface MessageProps {
  messageId: string;
  content: string;
  getMessageSiblings: (messageId: string) => string[];
}

// Additional props for AssistantMessage
export interface AssistantMessageProps extends MessageProps {
  isStreaming?: boolean;
}

// UserMessage component with user-specific styling and actions
export function UserMessage({
  messageId,
  content,
  getMessageSiblings,
}: MessageProps) {
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(content);
  const [viewingFile, setViewingFile] = useState<{
    pointer: string;
    mime_type: string;
    filename: string;
    file_type: string;
  } | null>(null); // State for the file being viewed

  if (!content) {
    console.debug(`UserMessage ${messageId} has empty content`);
    content = ''; // Ensure content is at least an empty string
  }

  const {
    editMessage,
    messageHasNextSibling,
    messageHasPreviousSibling,
    navigateMessageBranch,
  } = useMessageStore();

  const { messages } = useMessageStore();
  const message = messages[messageId];

  // Get chat ID from the message
  const chatId = message?.chat_id || '';

  // Check for siblings
  const hasNextSibling = messageHasNextSibling(messageId);
  const hasPreviousSibling = messageHasPreviousSibling(messageId);

  // Copy to clipboard
  const copyToClipboard = async () => {
    if (!content) return;

    try {
      await navigator.clipboard.writeText(content || '');
      setCopied(true);

      // Reset copied state after 2 seconds
      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  // Start editing function
  const startEditing = () => {
    setIsEditing(true);
    setEditContent(content);
  };

  // Handle edit submission
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editContent.trim()) return;

    await editMessage(messageId, editContent);
    setIsEditing(false);
  };

  // Keypress watch for edit
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleEditSubmit(e as unknown as React.FormEvent);
    }
  };

  // Navigation functions
  const navigateNext = () => {
    if (chatId && hasNextSibling) {
      navigateMessageBranch(chatId, messageId, 'next');
    }
  };

  const navigatePrevious = () => {
    if (chatId && hasPreviousSibling) {
      navigateMessageBranch(chatId, messageId, 'previous');
    }
  };

  // Show edit form if editing
  if (isEditing) {
    return (
      <div className={cn('flex items-start gap-4 py-2 flex-row-reverse')}>
        <div className="flex-1 md:max-w-[60%] space-y-2">
          <form onSubmit={handleEditSubmit} className="w-full">
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full p-2 border rounded-md mb-2 bg-background"
              rows={3}
              autoFocus
              onKeyDown={handleKeyPress}
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="px-3 py-1 text-sm rounded-md border"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-3 py-1 text-sm bg-primary text-primary-foreground rounded-md"
              >
                Save
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  // Extract file parts and text parts from the message
  const fileParts: Array<ImageMessagePart | DocumentMessagePart> = [];
  const documentParts: any[] = []; // Store document parts separately, including those without pointers
  const textParts: string[] = [];

  // Safely check and add file parts and text parts
  if (message?.parts?.length) {
    message.parts.forEach((part: any) => {
      // Handle image parts that have pointers
      if (part.part_kind === 'image' && part.pointer && part.mime_type) {
        fileParts.push({
          ...part,
          part_kind: 'image',
          pointer: part.pointer,
          mime_type: part.mime_type,
        });
      }

      // Handle document parts - add ALL to documentParts and those with pointers to fileParts
      if (part.part_kind === 'document') {
        // Add to separate array to display all documents
        documentParts.push(part);

        // Only add to fileParts if it has a pointer and can be viewed
        if (part.pointer && part.mime_type) {
          fileParts.push({
            ...part,
            part_kind: 'document',
            pointer: part.pointer,
            mime_type: part.mime_type,
          });
        }
      }

      // Handle text parts
      if (part.part_kind === 'text' && part.content) {
        textParts.push(part.content);
      }
    });
  }

  // Helper function to get filename from part
  const getFilename = (part: {
    metadata?: { filename?: string };
    title?: string;
    pointer?: string;
  }) => {
    if (part.metadata?.filename) return part.metadata.filename;
    if (part.title) return part.title;
    return part.pointer?.split('/')?.pop() || 'File';
  };

  return (
    <div className={cn('flex items-start gap-4 py-2 flex-row-reverse')}>
      <div className="flex-1 space-y-2">
        {/* Display chips for all document parts regardless of pointer status */}
        {documentParts.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2 md:max-w-[60%] mx-auto justify-end">
            {documentParts.map((part, index) => (
              <FileChip
                key={`doc-${index}-${part.title || index}`}
                file={{
                  filename: getFilename(part),
                  file_type: 'document',
                  mime_type: part.mime_type,
                  pointer: part.pointer,
                }}
                onClick={
                  part.pointer && part.mime_type
                    ? () =>
                        setViewingFile({
                          pointer: part.pointer,
                          mime_type: part.mime_type,
                          filename: getFilename(part),
                          file_type: 'document',
                        })
                    : undefined
                }
                viewOnly={true}
              />
            ))}
          </div>
        )}

        {/* Display image parts with pointers */}
        {fileParts.filter((part) => part.part_kind === 'image').length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2 md:max-w-[60%] mx-auto justify-end">
            {fileParts
              .filter((part) => part.part_kind === 'image')
              .map((part, index) => (
                <FileChip
                  key={`img-${index}-${part.pointer || index}`}
                  file={{
                    filename: getFilename(part),
                    file_type: part.part_kind,
                    mime_type: part.mime_type,
                    pointer: part.pointer,
                    preview_url: part.metadata?.preview_url,
                  }}
                  onClick={() =>
                    setViewingFile({
                      pointer: part.pointer,
                      mime_type: part.mime_type,
                      filename: getFilename(part),
                      file_type: part.part_kind,
                    })
                  }
                  viewOnly={true}
                />
              ))}
          </div>
        )}

        <div className="md:max-w-[60%] rounded-lg bg-card mx-auto relative">
          <div className="prose prose-stone prose-sm max-w-none dark:prose-invert px-3 py-2">
            {/* Display all text parts if available, otherwise fall back to content prop */}
            {textParts.length > 0
              ? textParts.map((text, i) => (
                  <div key={`text-part-${i}`} className={i > 0 ? 'mt-2' : ''}>
                    {text}
                  </div>
                ))
              : content}
          </div>

          {message?.status === 'error' && (
            <div className="mt-2 text-sm text-red-500">
              Failed to process message. Please try again.
            </div>
          )}
        </div>

        {/* File viewer modal */}
        <FileViewerModal
          isOpen={!!viewingFile}
          onClose={() => setViewingFile(null)}
          file={viewingFile}
        />

        {/* Controls for user message */}
        <div className="flex items-center gap-2 mt-2 md:max-w-[60%] mx-auto justify-end">
          {/* Edit button */}
          <button
            onClick={startEditing}
            className="p-1 rounded-md mx-1 hover:bg-muted transition-colors cursor-pointer"
            title="Edit"
          >
            <Pencil className="icon-xs" />
          </button>

          {/* Copy button */}
          <button
            onClick={copyToClipboard}
            className="p-1 rounded-full mr-2 hover:bg-muted transition-colors cursor-pointer"
            title="Copy"
          >
            {copied ? (
              <CheckCircle2 className="icon-xs" />
            ) : (
              <Clipboard className="icon-xs" />
            )}
          </button>

          {(hasNextSibling || hasPreviousSibling) && (
            <>
              <button
                onClick={navigatePrevious}
                disabled={!hasPreviousSibling}
                className="p-1 rounded-full disabled:opacity-50 hover:bg-muted transition-colors cursor-pointer"
                title="Previous branch"
              >
                <ChevronLeft className="icon-xs" />
              </button>

              <span className="text-xs font-medium">
                {(() => {
                  const siblings = getMessageSiblings(messageId);
                  const currentIndex = siblings.indexOf(messageId);
                  return `${currentIndex + 1}/${siblings.length}`;
                })()}
              </span>

              <button
                onClick={navigateNext}
                disabled={!hasNextSibling}
                className="p-1 rounded-full disabled:opacity-50 hover:bg-muted transition-colors cursor-pointer"
                title="Next branch"
              >
                <ChevronRight className="icon-xs" />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// AssistantMessage component with assistant-specific styling and actions
export function AssistantMessage({
  messageId,
  content,
  isStreaming,
}: AssistantMessageProps) {
  const [copied, setCopied] = useState(false);
  const [lastEventTime, setLastEventTime] = useState(Date.now());
  const [showLoadingAnimation, setShowLoadingAnimation] = useState(false);
  const loadingCheckInterval = useRef<NodeJS.Timeout | null>(null);
  const hideLoadingTimeout = useRef<NodeJS.Timeout | null>(null);
  const streamStartTime = useRef<number | null>(null);
  const initialResponseThreshold = 750; // Time in ms to consider an initial response "fast"

  const { regenerateMessage, isMessageResearching, getResearchPhase } =
    useMessageStore();
  const { messages } = useMessageStore();
  const message = messages[messageId];

  // Get the current task handler from settings
  const selectedTaskHandler = useSettingsStore(
    (state) => state.selectedTaskHandler,
  );

  // Check research state for live streaming messages
  const isResearching = isMessageResearching(messageId);
  const researchPhase = getResearchPhase(messageId);

  // Only enable research mode for rag_oss task handler
  const isResearchMode =
    selectedTaskHandler === 'rag_oss' &&
    isStreaming &&
    (isResearching || researchPhase !== 'complete');

  // Detect research messages from database by checking for status event parts
  const hasResearchData = message?.parts?.some(
    (part: any) =>
      part.metadata?.status_event === 'true' ||
      (typeof part.content === 'string' &&
        part.content.includes('research_start:')),
  );

  if (!content) {
    console.log(`AssistantMessage ${messageId} has empty content:`, {
      messageId,
      messageStatus: message?.status,
      messageEventType: message?.eventType,
      hasEventData: !!message?.eventData,
      messageObject: message,
    });
    content = ''; // Ensure content is at least an empty string
  }

  // Get the appropriate renderer based on event type or message status
  // Default to 'content' for backward compatibility
  let rendererType = message?.eventType || 'content';

  // Force error renderer if message status is 'error'
  if (message?.status === 'error') {
    rendererType = 'error';
  }

  // Use effect to update eventData for error messages, preventing render-phase state updates
  useEffect(() => {
    // Only run this effect if the message has error status but no eventData
    if (message?.status === 'error' && !message.eventData) {
      console.log('Creating default error data for message with error status');

      // Use a safer and more type-correct approach: first get the current message object
      const currentState = useMessageStore.getState();
      if (currentState.messages[messageId]) {
        // Create update action in next tick to avoid React render-phase state updates
        setTimeout(() => {
          // Get latest state to avoid race conditions
          const latestState = useMessageStore.getState();
          const currentMessage = latestState.messages[messageId];

          // Only update if message still exists and still needs error data
          if (
            currentMessage &&
            currentMessage.status === 'error' &&
            !currentMessage.eventData
          ) {
            // Create proper typed Message object with error data
            const updatedMessage: Message = {
              ...currentMessage,
              eventType: 'error', // StreamingEventType is correctly typed in Message interface
              eventData: {
                message: 'An error occurred during message generation',
                error_type: 'Error',
                details: null,
              },
            };

            // Update just this message within the store
            useMessageStore.setState((state: MessageState) => ({
              messages: {
                ...state.messages,
                [messageId]: updatedMessage,
              },
            }));

            console.log('Added error data to message:', messageId);
          }
        }, 0);
      }
    }
  }, [message, messageId]); // Re-run if message or messageId changes

  // Use effect to track time since last event and show loading animation
  useEffect(() => {
    if (isStreaming) {
      // Set initial time when streaming starts or effect is triggered
      const now = Date.now();
      setLastEventTime(now);

      // Record when streaming started for later comparison
      streamStartTime.current = now;

      // Show loading animation immediately when streaming begins
      setShowLoadingAnimation(true);

      // Create an interval to check if we need to refresh the loading state
      // This is kept in case we need to manage long-running operations
      loadingCheckInterval.current = setInterval(() => {
        // We're keeping this interval in case we need to add additional logic
        // for long-running streaming operations
      }, 200); // Check every 200ms
    } else {
      // Clean up when streaming stops
      setShowLoadingAnimation(false);
      streamStartTime.current = null;
      if (loadingCheckInterval.current) {
        clearInterval(loadingCheckInterval.current);
        loadingCheckInterval.current = null;
      }
    }

    // Clean up when component unmounts
    return () => {
      // Clean up loading check interval
      if (loadingCheckInterval.current) {
        clearInterval(loadingCheckInterval.current);
        loadingCheckInterval.current = null;
      }

      // Clean up hide loading animation timeout
      if (hideLoadingTimeout.current) {
        clearTimeout(hideLoadingTimeout.current);
        hideLoadingTimeout.current = null;
      }
    };
  }, [isStreaming]); // Remove lastEventTime from dependencies

  // Update lastEventTime whenever content changes, indicating a new event
  useEffect(() => {
    if (isStreaming && message) {
      const now = Date.now();
      setLastEventTime(now);

      // Clear any existing timeout to avoid race conditions
      if (hideLoadingTimeout.current) {
        clearTimeout(hideLoadingTimeout.current);
      }

      // Check if this is a quick initial response (less than initialResponseThreshold after streaming started)
      const isQuickInitialResponse =
        streamStartTime.current &&
        now - streamStartTime.current < initialResponseThreshold;

      if (isQuickInitialResponse) {
        // For quick initial responses, hide the loading animation immediately
        // This prevents the loading animation from appearing at all for fast responses
        setShowLoadingAnimation(false);
      } else {
        // For slower responses or subsequent events, use a delay before hiding
        // This prevents flickering when content arrives in small chunks
        hideLoadingTimeout.current = setTimeout(() => {
          setShowLoadingAnimation(false);
          hideLoadingTimeout.current = null;
        }, 500); // 500ms delay before hiding animation
      }
    }
  }, [content, isStreaming, message]);

  // Special handling for error messages
  if (message?.status === 'error' || rendererType === 'error') {
    console.log('Detected error message:', {
      messageId,
      status: message?.status,
      rendererType,
      eventData: message?.eventData,
      messageObject: message,
    });

    // Use error renderer directly for error messages
    const ErrorRenderer = getRendererForEventType('error');
    return (
      <div className={cn('flex items-start gap-4 py-4 max-w-[60%]')}>
        <div className="flex-1 space-y-2">
          <ErrorRenderer
            messageId={messageId}
            content={content}
            isStreaming={isStreaming}
            eventData={message?.eventData}
          />
        </div>
      </div>
    );
  }

  // Copy to clipboard
  const copyToClipboard = async () => {
    if (!content) return;

    try {
      await navigator.clipboard.writeText(content || '');
      setCopied(true);

      // Reset copied state after 2 seconds
      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  // Handle regeneration
  const handleRegenerate = async () => {
    try {
      await regenerateMessage(messageId);
    } catch (error) {
      console.error('Regeneration failed:', error);
    }
  };

  // Determine if we should show the status panel
  // Show panel if: currently researching OR has historical research data OR has completed research
  // AND the task is not "chat"
  const shouldShowStatusPanel =
    ((isResearchMode && isStreaming) ||
      hasResearchData ||
      (researchPhase && researchPhase !== null)) &&
    selectedTaskHandler !== 'chat';

  return (
    <div className={cn('flex items-start gap-4 py-4')}>
      <div className="flex-1 space-y-2">
        {/* Show StatusProgressPanel for all research messages (live and historical) */}
        {shouldShowStatusPanel ? (
          <div className="space-y-2">
            {isResearchMode && isStreaming && (
              <div className="md:max-w-[60%] mx-auto text-sm text-muted-foreground">
                Research in progress...
              </div>
            )}
            <StatusProgressPanel
              responseId={messageId}
              isHistorical={
                !isStreaming &&
                (hasResearchData || researchPhase === 'complete')
              }
              onFinished={() => {
                console.log('Research completed for:', messageId);
              }}
            />
          </div>
        ) : null}

        {/* Render content when not suppressed OR for completed research messages */}
        {(!isResearchMode || hasResearchData) && (
          <EventSegmentsManager
            messageId={messageId}
            content={content}
            isStreaming={isStreaming}
            eventType={message?.eventType || 'content'}
            eventData={message?.eventData}
          />
        )}

        {/* Loading animation that appears when no events for 500ms - suppress during research */}
        {isStreaming && showLoadingAnimation && !isResearchMode && (
          <div className="mt-2 flex justify-start pt-4 md:max-w-[60%] mx-auto transition-opacity duration-600 opacity-100">
            <div className="flex space-x-2">
              <div
                className="w-2 h-2 rounded-full bg-stone-800 dark:bg-stone-400 animate-pulse"
                style={{ animationDelay: '0ms' }}
              ></div>
              <div
                className="w-2 h-2 rounded-full bg-stone-800 dark:bg-stone-400 animate-pulse"
                style={{ animationDelay: '200ms' }}
              ></div>
              <div
                className="w-2 h-2 rounded-full bg-stone-800 dark:bg-stone-400 animate-pulse"
                style={{ animationDelay: '400ms' }}
              ></div>
            </div>
          </div>
        )}

        {/* Controls for assistant message - only show when not researching */}
        {!isStreaming && !isResearchMode && (
          <div className="flex items-center gap-2 md:max-w-[60%] mx-auto">
            {/* Copy button */}
            <button
              onClick={copyToClipboard}
              className="p-1 pl-0 rounded-full mr-2 hover:bg-muted transition-colors cursor-pointer"
              title="Copy"
            >
              {copied ? (
                <CheckCircle2 className="icon-xs" />
              ) : (
                <Clipboard className="icon-xs" />
              )}
            </button>

            {/* Regenerate button */}
            <button
              onClick={handleRegenerate}
              className="p-1 pl-0 rounded-md hover:bg-muted transition-colors cursor-pointer"
              title="Retry"
            >
              <RefreshCw className="icon-xs" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
