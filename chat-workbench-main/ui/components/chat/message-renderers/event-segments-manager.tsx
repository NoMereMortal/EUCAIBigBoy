// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import React, { useEffect, useMemo } from 'react';
import {
  EventSegment,
  EventSegmentRenderer,
} from '@/components/chat/message-renderers/event-segment';
import { StreamingEventType } from '@/lib/services/websocket-types';
import { v4 as uuidv4 } from 'uuid';
import { Message } from '@/lib/types';
import { useMessageStore } from '@/lib/store/message/message-slice';

interface EventSegmentsManagerProps {
  messageId: string;
  content: string;
  isStreaming?: boolean;
  eventType?: StreamingEventType;
  eventData?: Record<string, any>;
}

/**
 * Type representing each event in the event history
 */
interface EventHistoryItem {
  type: StreamingEventType;
  content: string;
  data?: Record<string, any>;
  sequence: number;
  timestamp: string;
  contentBlockIndex?: number; // Track which content block this event belongs to
  blockSequence?: number; // Track sequence within the content block
}

/**
 * Type representing a combined event history for a message,
 * tracking every event type that has come in and their order
 */
interface EventHistory {
  events: EventHistoryItem[];
}

/**
 * Manages and renders event segments within a message,
 * separating different types of events into distinct visual blocks
 */
export function EventSegmentsManager({
  messageId,
  content,
  isStreaming,
  eventType = 'content',
  eventData,
}: EventSegmentsManagerProps) {
  // Access the message store to get the message
  const { messages } = useMessageStore();
  const message = messages[messageId];

  // Process the event segments for this message
  const segments = useMemo(() => {
    // If no message or it's not an assistant message, just return a basic segment
    if (!message || message.kind !== 'response') {
      // Create a simple segment from the given props
      return [
        {
          id: uuidv4(),
          messageId,
          eventType,
          content: content || '',
          eventData,
          timestamp: new Date().toISOString(),
          sequence: 0,
        },
      ];
    }

    // First check if the message has an event history in the eventData
    const eventHistory = message.eventData?.eventHistory as EventHistory;

    // Debug message processing path
    console.debug('Processing message segments for:', messageId);
    console.debug('Message has event history:', !!eventHistory?.events?.length);
    console.debug('Message has parts:', !!message.parts?.length);

    let resultSegments: EventSegment[] = [];

    if (eventHistory?.events?.length > 0) {
      // Use the explicit event history to create multiple segments
      resultSegments = processEventHistory(eventHistory, message, messageId);
      console.debug(
        'Created segments from event history:',
        resultSegments.length,
        'Document segments:',
        resultSegments.filter((s) => s.eventType === 'document').length,
      );
    } else if (message.parts && message.parts.length > 1) {
      // If the message has multiple parts from REST API, process them
      resultSegments = processMessageParts(message);
      console.debug(
        'Created segments from message parts:',
        resultSegments.length,
        'Document segments:',
        resultSegments.filter((s) => s.eventType === 'document').length,
      );
    } else {
      // Extract segments from the message's eventType and event data
      resultSegments = extractSegmentsFromMessage(message, content);
      console.debug(
        'Created segments from message content:',
        resultSegments.length,
        'Document segments:',
        resultSegments.filter((s) => s.eventType === 'document').length,
      );
    }

    return resultSegments;
  }, [message, messageId, content, eventType, eventData]);

  if (!segments || segments.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      {segments.map((segment) => (
        <EventSegmentRenderer
          key={segment.id}
          segment={segment}
          isStreaming={isStreaming && segment.sequence === segments.length - 1}
        />
      ))}
    </div>
  );
}

/**
 * Process an explicit event history into a list of segments
 */
function processEventHistory(
  eventHistory: EventHistory,
  message: Message,
  messageId: string,
): EventSegment[] {
  // Group adjacent events of the same type to avoid unnecessary segmentation
  const contentGroupedEvents: EventSegment[] = [];
  const documentGroupedEvents: EventSegment[] = [];

  // Track current group information
  let currentType: StreamingEventType | null = null;
  let currentBlockIndex: number | null = null;
  let currentContent = '';
  let currentData: Record<string, any> = {};
  let currentStartSequence = 0;
  let currentTimestamp = '';

  // Sort events by sequence number to ensure proper order
  const sortedEvents = [...eventHistory.events].sort(
    (a, b) => a.sequence - b.sequence,
  );

  // Find response start sequence
  let responseStartAt = -1;
  for (let i = 0; i < sortedEvents.length; i++) {
    const event = sortedEvents[i];
    if (event.type === 'response_start') {
      responseStartAt = event.sequence;
      console.debug('Response started at sequence:', responseStartAt);
      break;
    }
  }

  // Find research completion point by looking for "finished" status with "research" in message
  let researchCompletedAt = -1;
  for (let i = 0; i < sortedEvents.length; i++) {
    const event = sortedEvents[i];
    if (
      event.type === 'status' &&
      event.data?.status === 'finished' &&
      event.data?.message &&
      typeof event.data.message === 'string' &&
      event.data.message.toLowerCase().includes('research')
    ) {
      researchCompletedAt = event.sequence;
      console.debug('Research completed at sequence:', researchCompletedAt);
      break;
    }
  }

  console.debug(
    'Processing',
    sortedEvents.length,
    'events, response start:',
    responseStartAt,
    'research completed:',
    researchCompletedAt,
  );

  // Group adjacent events of the same type
  sortedEvents.forEach((event, index) => {
    const eventType = event.type;
    const eventContent = event.content || '';
    const eventData = event.data || {};
    const eventTimestamp = event.timestamp;

    // Skip tool_call and tool_return events - they're now handled by the status panel
    if (
      eventType === ('tool_call' as any) ||
      eventType === ('tool_return' as any)
    ) {
      return;
    }

    // Filter ALL ContentEvents between response_start and research completion (simplified approach)
    if (eventType === 'content') {
      // Default assumption: filter ALL content between response start and research completion
      if (
        responseStartAt >= 0 &&
        researchCompletedAt >= 0 &&
        event.sequence > responseStartAt &&
        event.sequence < researchCompletedAt
      ) {
        console.debug(
          'Filtering out research-phase ContentEvent at sequence:',
          event.sequence,
          'content preview:',
          eventContent.substring(0, 50),
        );
        return; // Skip this content event - it should only appear in status panel
      }
      // Include content events that occurred after research completion
      if (researchCompletedAt >= 0 && event.sequence >= researchCompletedAt) {
        console.debug(
          'Including post-research ContentEvent at sequence:',
          event.sequence,
          'content preview:',
          eventContent.substring(0, 50),
        );
      }
      // Include content events before response start (shouldn't happen in practice)
      if (responseStartAt >= 0 && event.sequence <= responseStartAt) {
        console.debug(
          'Including pre-response ContentEvent at sequence:',
          event.sequence,
        );
      }
      // If no research cycle boundaries detected, include all content (backwards compatibility)
      if (responseStartAt < 0 || researchCompletedAt < 0) {
        console.debug(
          'No research boundaries detected, including ContentEvent at sequence:',
          event.sequence,
        );
      }
    }

    // Extract content block index if available
    const contentBlockIndex = event.contentBlockIndex ?? null;

    // For tool_call events, we have a special grouping logic to handle deltas
    const isSameToolCall =
      eventType === 'tool_call' &&
      currentType === 'tool_call' &&
      eventData?.tool_name === currentData?.tool_name &&
      eventData?.tool_id === currentData?.tool_id;

    // If this is a new group, different type, or different content block from current group
    // Special handling for tool_call: don't break up tool_call events of the same tool
    if (
      currentType === null ||
      (currentType !== eventType && !isSameToolCall) ||
      (contentBlockIndex !== null &&
        currentBlockIndex !== contentBlockIndex &&
        !isSameToolCall)
    ) {
      // Save the previous group if it exists
      if (currentType !== null) {
        const newSegment = {
          id: uuidv4(),
          messageId,
          eventType: currentType,
          content: currentContent,
          eventData: currentData,
          timestamp: currentTimestamp,
          sequence: currentStartSequence,
          contentBlockIndex: currentBlockIndex ?? undefined,
          blockSequence: event.blockSequence,
        };

        // Add to appropriate array based on type
        if (currentType === 'document') {
          documentGroupedEvents.push(newSegment);
        } else {
          contentGroupedEvents.push(newSegment);
        }
      }

      // Start a new group
      currentType = eventType;
      currentBlockIndex = contentBlockIndex;
      currentContent = eventContent;
      currentData = { ...eventData };
      currentStartSequence = index;
      currentTimestamp = eventTimestamp;
    } else {
      // Same type, append to current group
      currentContent += eventContent;

      // Merge eventData if applicable
      if (Object.keys(eventData).length > 0) {
        if (eventType === 'tool_call' && eventData.tool_args?.delta) {
          // Special handling for tool call deltas - accumulate them
          const existingArgs = currentData.tool_args || {};
          currentData = {
            ...currentData,
            tool_args: {
              ...existingArgs,
              delta:
                (existingArgs.delta || '') + (eventData.tool_args.delta || ''),
            },
          };
        } else {
          // Regular data merging for other event types
          currentData = { ...currentData, ...eventData };
        }
      }
    }
  });

  // Don't forget the last group
  if (currentType !== null) {
    const finalSegment = {
      id: uuidv4(),
      messageId,
      eventType: currentType,
      content: currentContent,
      eventData: currentData,
      timestamp: currentTimestamp,
      sequence: currentStartSequence,
      contentBlockIndex: currentBlockIndex ?? undefined,
    };

    // Add to appropriate array based on type
    if (currentType === 'document') {
      documentGroupedEvents.push(finalSegment);
    } else {
      contentGroupedEvents.push(finalSegment);
    }
  }

  // Return all content segments followed by document segments
  return [...contentGroupedEvents, ...documentGroupedEvents];
}

/**
 * Process message parts from a REST API response
 */
function processMessageParts(message: Message): EventSegment[] {
  const contentSegments: EventSegment[] = [];
  const documentSegments: EventSegment[] = [];

  // Process each part in the message
  message.parts.forEach((part, index) => {
    // Skip parts without content or part_kind
    if (!part || !part.part_kind) return;

    // Filter out tool-call parts - these are handled by status-progress-panel
    if ((part as any).part_kind === 'tool-call') {
      console.debug('Filtering out tool-call part:', part);
      return;
    }

    // Filter out status event parts - these are handled by status-progress-panel
    if (part.metadata && part.metadata.status_event === 'true') {
      console.debug('Filtering out status event part:', part);
      return;
    }

    // Filter out parts containing research status strings - these are handled by status-progress-panel
    if (
      typeof part.content === 'string' &&
      (part.content.includes('research_start:') ||
        part.content.includes('research_progress:') ||
        part.content.includes('research_complete:'))
    ) {
      console.debug(
        'Filtering out research status content part:',
        part.content.substring(0, 100),
      );
      return;
    }

    // Filter out document parts - these are handled by status-progress-panel
    if ((part as any).part_kind === 'document') {
      console.debug('Filtering out document part:', part);
      return;
    }

    // Filter out citation parts - these are handled by status-progress-panel
    if ((part as any).part_kind === 'citation') {
      console.debug('Filtering out citation part:', part);
      return;
    }

    // Create a segment for each part based on its type
    const segmentId = `${message.message_id}-part-${index}`;
    const timestamp = part.timestamp || message.timestamp;

    // Map part_kind to eventType (they may not be exactly the same)
    let eventType: StreamingEventType = 'content';
    if (
      part.part_kind === 'document' ||
      part.part_kind === 'citation' ||
      part.part_kind === 'reasoning' ||
      part.part_kind === 'tool-call'
    ) {
      // Direct mapping for some types - convert kebab-case to snake_case
      eventType = part.part_kind.replace('-', '_') as StreamingEventType;
    }

    // Create event data based on part type
    let partEventData: Record<string, any> = { ...(part.metadata || {}) };

    // Handle document parts
    if (part.part_kind === 'document') {
      // Use type assertion to access document-specific properties
      const docPart = part as any;
      partEventData = {
        ...partEventData,
        document_id: docPart.document_id || '',
        title: docPart.title || 'Document',
        pointer: docPart.pointer || '',
        mime_type: docPart.mime_type || 'application/pdf',
      };
    }
    // Handle citation parts
    else if (part.part_kind === 'citation') {
      // Use type assertion to access citation-specific properties
      const citePart = part as any;
      partEventData = {
        ...partEventData,
        document_id: citePart.document_id || '',
        text: citePart.text || '',
        page: citePart.page,
        section: citePart.section,
        reference_number: citePart.reference_number,
        document_title: citePart.document_title,
        document_pointer: citePart.document_pointer,
      };
    }

    // Create the segment
    const segment = {
      id: segmentId,
      messageId: message.message_id,
      eventType: eventType,
      content: part.content || '',
      eventData: partEventData,
      timestamp,
      sequence: index,
    };

    // Separate document segments from other segments
    if (part.part_kind === 'document') {
      documentSegments.push(segment);
    } else {
      contentSegments.push(segment);
    }
  });

  // Return all segments with documents at the end
  return [...contentSegments, ...documentSegments];
}

/**
 * Extract segments from a message's current event type and content
 */
function extractSegmentsFromMessage(
  message: Message,
  content: string,
): EventSegment[] {
  const contentSegments: EventSegment[] = [];
  const documentSegments: EventSegment[] = [];

  // Skip tool_call events - they're now handled by the status panel
  if (message.eventType === ('tool_call' as any)) {
    // Don't create segments for tool calls, just return empty arrays
    return [];
  }
  // Handle document events - put them in the document segment array
  else if (message.eventType === 'document') {
    documentSegments.push({
      id: uuidv4(),
      messageId: message.message_id,
      eventType: 'document',
      content,
      eventData: message.eventData || {},
      timestamp: message.timestamp,
      sequence: 0,
    });
  }
  // Handle reasoning events
  else if (message.eventType === 'reasoning') {
    contentSegments.push({
      id: uuidv4(),
      messageId: message.message_id,
      eventType: 'reasoning',
      content,
      eventData: message.eventData || {},
      timestamp: message.timestamp,
      sequence: 0,
    });
  }
  // Handle citation events
  else if (message.eventType === 'citation') {
    contentSegments.push({
      id: uuidv4(),
      messageId: message.message_id,
      eventType: 'citation',
      content,
      eventData: message.eventData || {},
      timestamp: message.timestamp,
      sequence: 0,
    });
  }
  // Default to content event
  else {
    contentSegments.push({
      id: uuidv4(),
      messageId: message.message_id,
      eventType: message.eventType || 'content',
      content,
      eventData: message.eventData || {},
      timestamp: message.timestamp,
      sequence: 0,
    });
  }

  // Return all segments with documents at the end
  return [...contentSegments, ...documentSegments];
}
