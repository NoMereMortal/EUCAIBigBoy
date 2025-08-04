// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { StreamingEventType } from '@/lib/services/websocket-types';

export interface MessagePartRequest {
  content: string;
  part_kind:
    | 'text'
    | 'image'
    | 'document'
    | 'system-prompt'
    | 'tool-call'
    | 'tool-return'
    | 'retry-prompt'
    | 'pointer'
    | 'reasoning'
    | 'citation';
  metadata?: Record<string, any>;
  // Additional fields for specific part types
  file_id?: string; // Required for image and document parts
  user_id?: string; // Required for image parts, optional for document parts
  mime_type?: string; // Required for image and document parts
  pointer?: string; // Optional for document parts
  title?: string; // Optional for document parts
  width?: number; // Optional for image parts
  height?: number; // Optional for image parts
  format?: string; // Optional for image parts
  page_count?: number; // Optional for document parts
  word_count?: number; // Optional for document parts
}

export interface MessagePart {
  content: string;
  part_kind:
    | 'text'
    | 'image'
    | 'document'
    | 'system-prompt'
    | 'tool-call'
    | 'tool-return'
    | 'retry-prompt'
    | 'pointer'
    | 'reasoning'
    | 'citation';
  metadata?: Record<string, any>;
  timestamp: string;
  // Additional fields for specific part types
  file_id?: string; // Required for image and document parts
  user_id?: string; // Required for image parts, optional for document parts
  mime_type?: string; // Required for image and document parts
  pointer?: string; // Optional for document parts
  title?: string; // Optional for document parts
  width?: number; // Optional for image parts
  height?: number; // Optional for image parts
  format?: string; // Optional for image parts
  page_count?: number; // Optional for document parts
  word_count?: number; // Optional for document parts
}

// Define a more granular message status type to clearly represent the message lifecycle
export type MessageStatus =
  | 'created' // Message object created but processing not started
  | 'processing' // LLM is processing but no tokens received yet
  | 'streaming' // Tokens are actively streaming
  | 'complete' // All tokens received and processing finished
  | 'error'; // An error occurred during processing

export interface Message {
  message_id: string;
  chat_id: string;
  parent_id: string | null;
  kind: 'request' | 'response';
  parts: MessagePart[];
  timestamp: string;
  status: MessageStatus;
  eventType?: StreamingEventType; // Store the type of event that generated this message
  eventData?: Record<string, any>; // Store additional event-specific data
}

export interface GenerateRequest {
  task: string;
  chat_id: string;
  parent_id?: string | null;
  parts: MessagePart[];
  model_id: string;
  context?: any[] | null;
  persona?: string | null;
}
