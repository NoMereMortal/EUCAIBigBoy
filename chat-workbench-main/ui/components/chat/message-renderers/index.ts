// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { DefaultMessageRenderer } from '@/components/chat/message-renderers/default-renderer';
import { ErrorMessageRenderer } from '@/components/chat/message-renderers/error-renderer';
import { ToolCallMessageRenderer } from '@/components/chat/message-renderers/tool-call-renderer';
import { StatusMessageRenderer } from '@/components/chat/message-renderers/status-renderer';
import { ReasoningMessageRenderer } from '@/components/chat/message-renderers/reasoning-renderer';
import { DocumentRenderer } from '@/components/chat/message-renderers/document-renderer';
import { CitationRenderer } from '@/components/chat/message-renderers/citation-renderer';

export interface MessageRendererProps {
  content: string; // The main content to render
  isStreaming?: boolean; // Whether content is currently streaming in
  eventData?: Record<string, any>; // Event data for specialized renderers
  messageId?: string; // ID of the message (made optional)
  segmentId?: string; // ID of the message segment (made optional)
  contentBlockIndex?: number; // Content block this event belongs to (made optional)
  blockSequence?: number; // Sequence within the content block (made optional)
}

// Registry mapping event types to renderer components
export const messageRendererRegistry: Record<
  string,
  React.ComponentType<MessageRendererProps>
> = {
  content: DefaultMessageRenderer,
  error: ErrorMessageRenderer,
  tool_call: ToolCallMessageRenderer,
  status: StatusMessageRenderer,
  reasoning: ReasoningMessageRenderer,
  document: DocumentRenderer,
  citation: CitationRenderer,
  // Add other event types as needed
};

// Fallback renderer for unknown types
export const getRendererForEventType = (
  eventType: string,
): React.ComponentType<MessageRendererProps> => {
  return messageRendererRegistry[eventType] || DefaultMessageRenderer;
};
