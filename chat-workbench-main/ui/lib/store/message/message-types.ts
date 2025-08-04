// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// lib/store/message-types.ts
import {
  MessageStatus,
  Message,
  MessagePart,
  GenerateRequest,
  ChatSession,
} from '@/lib/types';
import { ContentEvent, DocumentEvent } from '@/lib/services/websocket-types';

export interface MessageState {
  // Core state
  messages: Record<string, Message>; // All messages indexed by ID
  messagesByChat: Record<string, string[]>; // Message IDs indexed by chat ID
  activeMessagePath: Record<string, string[]>; // Message paths by chat ID (thread history)
  isStreaming: boolean; // Currently streaming a message
  currentStreamingId: string | null; // ID of currently streaming message
  pendingChatId: string | null; // Chat ID with pending request
  pendingContent: string | MessagePart[] | any[] | null; // Content of pending message
  pendingParentId: string | null; // Parent ID for pending message
  error: string | null; // Any error state
  wsHandlersInitialized: boolean; // Whether WebSocket handlers have been initialized
  messageStatus: Record<string, string>; // Status updates for messages
  messageMetadata: Record<string, Record<string, any>>; // Additional metadata by message ID
  usageStats: Record<string, Record<string, any>>; // Usage statistics by message ID

  // Event buffering for race condition handling
  contentEventBuffer: Record<string, ContentEvent[]>; // messageId → buffered content events
  documentEventBuffer: Record<string, DocumentEvent[]>; // messageId → buffered document events
  bufferTimeouts: Record<string, NodeJS.Timeout>; // cleanup timers for buffered events
  bufferStats: {
    // performance monitoring
    totalEvents: number;
    bufferedEvents: number;
    immediateEvents: number;
  };

  // Research progress state
  researchProgress: Record<
    string,
    {
      // Research state by message ID
      isResearching: boolean; // Whether message is in research phase
      phase:
        | 'start'
        | 'planning'
        | 'searching'
        | 'evaluating'
        | 'analyzing'
        | 'complete'
        | null;
      completedAt: string | null; // When research completed
      totalPhases: number; // Total research phases completed
    }
  >;

  // Chat state (moved from chat-slice)
  chats: ChatSession[]; // Available chat sessions
  isLoadingChats: boolean; // Whether chats are being loaded

  // Actions
  startMessageGeneration: (
    chatId: string,
    content: string | MessagePart[] | any[],
    parentId?: string | null,
  ) => Promise<void>;
  fetchMessages: (chatId: string) => Promise<void>;
  updateMessageContent: (messageId: string, content: string) => void;
  updateMessageStatus: (messageId: string, status: MessageStatus) => void;
  appendToMessage: (messageId: string, contentDelta: string) => void;
  setActiveMessagePath: (chatId: string, messageIds: string[]) => void;
  navigateMessageBranch: (
    chatId: string,
    messageId: string,
    direction: 'next' | 'previous',
  ) => void;
  getMessageChildren: (messageId: string) => string[];
  getMessageSiblings: (messageId: string) => string[];

  // Chat actions (moved from chat-slice)
  fetchChats: (userId?: string, limit?: number) => Promise<void>;
  fetchChat: (chatId: string) => Promise<ChatSession | null>;
  createChat: (title: string, userId?: string) => Promise<ChatSession>;
  updateChatTitle: (chatId: string, title: string) => Promise<void>;
  deleteChat: (chatId: string) => Promise<void>;

  // WebSocket actions
  initializeWsHandlers: () => void;
  interruptStream: () => void;

  // Editing actions
  editMessage: (messageId: string, newContent: string) => Promise<void>;
  regenerateMessage: (messageId: string) => Promise<void>;

  // Research progress actions
  updateResearchProgress: (
    messageId: string,
    phase:
      | 'start'
      | 'planning'
      | 'searching'
      | 'evaluating'
      | 'analyzing'
      | 'complete',
    isResearching?: boolean,
  ) => void;
  completeResearch: (messageId: string) => void;
  isMessageResearching: (messageId: string) => boolean;
  getResearchPhase: (
    messageId: string,
  ) =>
    | 'start'
    | 'planning'
    | 'searching'
    | 'evaluating'
    | 'analyzing'
    | 'complete'
    | null;

  // Utility actions
  messageHasNextSibling: (messageId: string) => boolean;
  messageHasPreviousSibling: (messageId: string) => boolean;
  addDocumentToMessage: (
    messageId: string,
    documentEvent: DocumentEvent,
  ) => void;

  // Cleanup/reset
  clearMessages: () => void;
  clearChatMessages: (chatId: string) => void;
}
