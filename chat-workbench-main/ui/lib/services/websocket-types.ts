// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// WebSocket message types used for communication
export enum WSMessageType {
  // Client -> Server messages
  INITIALIZE = 'initialize',
  INTERRUPT = 'interrupt',
  PING = 'ping',

  // Server -> Client messages
  EVENT = 'event', // Generic streaming event container
  CONNECTION_ESTABLISHED = 'connection_established',
  ERROR = 'error',
  STATUS = 'status',
  PONG = 'pong',
}

// Streaming event types that come inside EVENT messages (snake_case from backend)
export type StreamingEventType =
  | 'content'
  | 'reasoning'
  | 'response_start'
  | 'response_end'
  | 'status'
  | 'error'
  | 'tool_call'
  | 'tool_return'
  | 'metadata'
  | 'document'
  | 'citation';

// Base streaming event structure
export interface BaseStreamingEvent {
  type: StreamingEventType;
  response_id: string;
  sequence: number;
  timestamp: string;
  emit?: boolean;
  persist?: boolean;
}

// Content event (text generation)
export interface ContentEvent extends BaseStreamingEvent {
  type: 'content';
  content: string;
}

// Reasoning event (model thinking)
export interface ReasoningEvent extends BaseStreamingEvent {
  type: 'reasoning';
  text: string;
  signature?: string;
  redacted_content?: string;
}

// Response start event
export interface ResponseStartEvent extends BaseStreamingEvent {
  type: 'response_start';
  request_id: string;
  chat_id: string;
  task: string;
  model_id: string;
  parent_id?: string;
}

// Response end event
export interface ResponseEndEvent extends BaseStreamingEvent {
  type: 'response_end';
  status: string;
  usage: Record<string, any>;
}

// Status event
export interface StatusEvent extends BaseStreamingEvent {
  type: 'status';
  status: string;
  message?: string;
}

// Error event
export interface ErrorEvent extends BaseStreamingEvent {
  type: 'error';
  error_type: string;
  message: string;
  details?: Record<string, any>;
}

// Tool call event
export interface ToolCallEvent extends BaseStreamingEvent {
  type: 'tool_call';
  tool_name: string;
  tool_id: string;
  tool_args: Record<string, any>;
}

// Tool return event
export interface ToolReturnEvent extends BaseStreamingEvent {
  type: 'tool_return';
  tool_name: string;
  tool_id: string;
  result: any;
}

// Metadata event
export interface MetadataEvent extends BaseStreamingEvent {
  type: 'metadata';
  metadata: Record<string, any>;
}

// Document event
export interface DocumentEvent extends BaseStreamingEvent {
  type: 'document';
  document_id: string;
  pointer: string;
  mime_type: string;
  title?: string;
  page_count?: number;
  word_count?: number;
}

// Citation event
export interface CitationEvent extends BaseStreamingEvent {
  type: 'citation';
  document_id: string;
  citation_id?: string; // Citation ID for tracking
  reference_number?: number; // New field for citation numbering
  document_title?: string; // New field for document title
  document_pointer?: string; // New field for document URL
  text: string;
  page?: number;
  section?: string;
}

// Union type for all streaming events
export type StreamingEvent =
  | ContentEvent
  | ReasoningEvent
  | ResponseStartEvent
  | ResponseEndEvent
  | StatusEvent
  | ErrorEvent
  | ToolCallEvent
  | ToolReturnEvent
  | MetadataEvent
  | DocumentEvent
  | CitationEvent;

// WebSocket event message from server (contains streaming events)
export interface WSEventMessage {
  data: StreamingEvent;
}

// Connection established message
export interface WSConnectionEstablishedMessage {
  timestamp: string;
}

// Message part types
export type MessagePartType =
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

// Base message part
export interface MessagePart {
  part_kind: MessagePartType;
}

// Text message part
export interface TextMessagePart extends MessagePart {
  part_kind: 'text';
  content: string;
}

// Image message part with pointer
export interface ImageMessagePart extends MessagePart {
  part_kind: 'image';
  pointer: string;
  mime_type: string;
  metadata?: Record<string, any>;
  timestamp?: string;
}

// Document message part with pointer
export interface DocumentMessagePart extends MessagePart {
  part_kind: 'document';
  pointer: string;
  mime_type: string;
  title?: string;
  metadata?: Record<string, any>;
  timestamp?: string;
}

// System prompt message part
export interface SystemPromptMessagePart extends MessagePart {
  part_kind: 'system-prompt';
  content: string;
  dynamic_ref?: string;
}

// Tool call message part
export interface ToolCallMessagePart extends MessagePart {
  part_kind: 'tool-call';
  content: string;
  tool_name: string;
  tool_args: Record<string, any>;
  tool_id: string;
}

// Tool return message part
export interface ToolReturnMessagePart extends MessagePart {
  part_kind: 'tool-return';
  content: string;
  tool_name: string;
  tool_id: string;
  result: any;
}

// Retry prompt message part
export interface RetryPromptMessagePart extends MessagePart {
  part_kind: 'retry-prompt';
  content: string;
}

// Pointer message part
export interface PointerMessagePart extends MessagePart {
  part_kind: 'pointer';
  content: string;
  pointer_type: 'image' | 'document';
  pointer: string;
  metadata?: Record<string, any>;
}

// Reasoning message part
export interface ReasoningMessagePart extends MessagePart {
  part_kind: 'reasoning';
  content: string;
  signature?: string;
}

// Citation message part
export interface CitationMessagePart extends MessagePart {
  part_kind: 'citation';
  content: string;
  document_id: string;
  text: string;
  page?: number;
  section?: string;
}

// Initialize message to server
export interface WSInitializeMessage {
  task: string;
  chat_id: string;
  parent_id: string | null;
  model_id: string;
  parts: Array<TextMessagePart | ImageMessagePart | DocumentMessagePart>;
  persona?: string | null;
  context?: Record<string, any>;
}

// Pong message from server
export interface WSPongMessage {
  timestamp: number;
}
