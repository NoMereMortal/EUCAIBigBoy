// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { ChatHeader } from '@/components/chat/chat-header';
import { ChatInput } from '@/components/chat/input/chat-input';
import { UserMessage, AssistantMessage } from '@/components/chat/message';
import { useMessageStore } from '@/lib/store/message/message-slice';
import { MessageState } from '@/lib/store/message/message-types';
import { Message } from '@/lib/types';

export function Chat({ chatId }: { chatId?: string }) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLDivElement>(null);
  const lastMessageIdRef = useRef<string | null>(null);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const animationFrameRef = useRef<number | undefined>(undefined);
  const lastUserScrollTimeRef = useRef<number>(0);

  // Enhanced scroll state management
  const [isLockedToBottom, setIsLockedToBottom] = useState(true);
  const [chatInputHeight, setChatInputHeight] = useState(120); // Default height

  // Scroll behavior configuration - easy to adjust
  const BOTTOM_BUFFER = 100; // pixels - conservative buffer for "near bottom"
  const UNLOCK_BUFFER = 150; // pixels - user must scroll this far up to unlock
  const SCROLL_DEBOUNCE_MS = 50; // milliseconds - delay between auto-scroll updates during streaming

  const {
    messages,
    activeMessagePath,
    isStreaming,
    currentStreamingId,
    pendingChatId,
    fetchMessages,
  } = useMessageStore();

  useEffect(() => {
    if (chatId) {
      fetchMessages(chatId);
    }
  }, [chatId, fetchMessages]);

  // WebSocket handlers are now initialized only once by MessageProvider

  // Get current chat's message path
  // If no chatId provided, use the most recent chat with messages
  let effectiveChatId = chatId;
  if (!effectiveChatId) {
    // Find the chat with the most recent activity
    const chatIds = Object.keys(activeMessagePath).filter(
      (id) => activeMessagePath[id].length > 0,
    );
    if (chatIds.length > 0) {
      // Sort by most recent message timestamp
      effectiveChatId = chatIds.reduce((latestChatId, currentChatId) => {
        const currentPath = activeMessagePath[currentChatId] || [];
        const latestPath = activeMessagePath[latestChatId] || [];

        if (currentPath.length === 0) return latestChatId;
        if (latestPath.length === 0) return currentChatId;

        const currentLastMessage =
          messages[currentPath[currentPath.length - 1]];
        const latestLastMessage = messages[latestPath[latestPath.length - 1]];

        if (!currentLastMessage) return latestChatId;
        if (!latestLastMessage) return currentChatId;

        return new Date(currentLastMessage.timestamp) >
          new Date(latestLastMessage.timestamp)
          ? currentChatId
          : latestChatId;
      });
    }
  }

  const currentPath = effectiveChatId
    ? activeMessagePath[effectiveChatId] || []
    : [];
  const hasMessages = currentPath.length > 0;

  // Enhanced debugging in development
  if (process.env.NODE_ENV === 'development') {
    console.log(
      'Chat component render - chatId:',
      chatId,
      'effectiveChatId:',
      effectiveChatId,
      'Messages:',
      Object.keys(messages).length,
      'currentPath length:',
      currentPath.length,
    );
  }

  // Smart scroll function with behavior control
  const scrollToBottomSmart = useCallback(
    (behavior: 'smooth' | 'instant' = 'smooth') => {
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({
          behavior: behavior === 'instant' ? 'auto' : 'smooth',
        });
      }
    },
    [],
  );

  // Enhanced auto-scroll logic with lock mechanism
  useEffect(() => {
    if (!currentStreamingId) return;

    const message = messages[currentStreamingId];
    if (!message) return;

    // New message - always scroll and lock to bottom
    if (currentStreamingId !== lastMessageIdRef.current) {
      lastMessageIdRef.current = currentStreamingId;
      setIsLockedToBottom(true);
      scrollToBottomSmart('instant');
      return;
    }

    // During streaming - only scroll if locked to bottom
    if (isStreaming && isLockedToBottom) {
      // Cancel any pending scroll operations
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }

      // Use longer debouncing for smoother experience
      scrollTimeoutRef.current = setTimeout(() => {
        // Use requestAnimationFrame for smoother scrolling
        animationFrameRef.current = requestAnimationFrame(() => {
          scrollToBottomSmart('smooth'); // Use smooth even during streaming
        });
      }, SCROLL_DEBOUNCE_MS); // Balanced debouncing for responsive scrolling
    }
  }, [
    currentStreamingId,
    messages,
    isStreaming,
    isLockedToBottom,
    scrollToBottomSmart,
  ]);

  // Scroll event handler to detect user scrolling and manage lock state
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      // Track user scroll time to distinguish from programmatic scrolls
      const now = Date.now();
      const timeSinceLastUserScroll = now - lastUserScrollTimeRef.current;

      // Only process if this might be a user scroll (not too recent)
      if (timeSinceLastUserScroll < 100) return;

      const { scrollTop, scrollHeight, clientHeight } = container;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

      // User scrolled far enough up - unlock auto-scroll
      if (distanceFromBottom > UNLOCK_BUFFER && isLockedToBottom) {
        setIsLockedToBottom(false);
      }

      // User scrolled back near bottom - re-lock
      if (distanceFromBottom <= BOTTOM_BUFFER && !isLockedToBottom) {
        setIsLockedToBottom(true);
        scrollToBottomSmart('smooth');
      }
    };

    // Track user scroll events
    const handleUserScroll = () => {
      lastUserScrollTimeRef.current = Date.now();
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    container.addEventListener('wheel', handleUserScroll, { passive: true });
    container.addEventListener('touchmove', handleUserScroll, {
      passive: true,
    });

    return () => {
      container.removeEventListener('scroll', handleScroll);
      container.removeEventListener('wheel', handleUserScroll);
      container.removeEventListener('touchmove', handleUserScroll);
    };
  }, [isLockedToBottom, BOTTOM_BUFFER, UNLOCK_BUFFER, scrollToBottomSmart]);

  // Measure ChatInput height dynamically
  useEffect(() => {
    const measureChatInputHeight = () => {
      if (chatInputRef.current) {
        const height = chatInputRef.current.offsetHeight;
        const newHeight = 25;
        if (newHeight !== chatInputHeight) {
          setChatInputHeight(newHeight);
        }
      }
    };

    // Small delay to ensure DOM is rendered
    const timeoutId = setTimeout(measureChatInputHeight, 100);

    // Measure when window resizes
    window.addEventListener('resize', measureChatInputHeight);

    // Use ResizeObserver for more accurate measurements if available
    let resizeObserver: ResizeObserver | null = null;
    if (chatInputRef.current && window.ResizeObserver) {
      resizeObserver = new ResizeObserver(measureChatInputHeight);
      resizeObserver.observe(chatInputRef.current);
    }

    return () => {
      clearTimeout(timeoutId);
      window.removeEventListener('resize', measureChatInputHeight);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
    };
  }, [chatInputHeight]); // Re-run when chatInputHeight changes

  // Initial scroll when messages are loaded
  useEffect(() => {
    if (chatId && activeMessagePath[chatId]?.length > 0) {
      scrollToBottomSmart('smooth');
    }
  }, [chatId, activeMessagePath, scrollToBottomSmart]);

  // Cleanup timeout and animation frame on unmount
  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  // Filter messages to only include those in the active path
  const activePathMessages = currentPath
    .filter((messageId: string) => messages[messageId]) // Ensure message exists
    .map((messageId: string) => messages[messageId]);

  return (
    <div className="flex h-full flex-col relative">
      <ChatHeader />
      <div
        ref={scrollContainerRef}
        className={cn(
          'flex-1 overflow-y-auto p-4',
          !hasMessages && 'flex flex-col justify-center',
        )}
      >
        {!hasMessages && <div className="flex-1" />}

        <div
          className={cn('flex flex-col gap-4')}
          style={{ marginBottom: `${chatInputHeight}px` }}
          key={currentPath.join('-')}
        >
          {activePathMessages.map((message: Message, index: number) => {
            if (!message) return null;

            const content = message.parts[0]?.content || '';
            const isCurrentlyStreaming =
              isStreaming && currentStreamingId === message.message_id;

            return (
              <React.Fragment key={message.message_id}>
                {message.kind === 'request' ? (
                  <UserMessage
                    messageId={message.message_id}
                    content={content}
                    getMessageSiblings={
                      useMessageStore.getState().getMessageSiblings
                    }
                  />
                ) : (
                  <AssistantMessage
                    messageId={message.message_id}
                    content={content}
                    isStreaming={isCurrentlyStreaming}
                    getMessageSiblings={
                      useMessageStore.getState().getMessageSiblings
                    }
                  />
                )}
              </React.Fragment>
            );
          })}

          <div ref={messagesEndRef} className="h-8" />
        </div>

        {!hasMessages && <div className="flex-1" />}
      </div>
      <div ref={chatInputRef}>
        <ChatInput chatId={effectiveChatId} />
      </div>
    </div>
  );
}
