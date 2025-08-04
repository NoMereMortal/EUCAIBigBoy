// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import React from 'react';
import { getRendererForEventType } from '@/components/chat/message-renderers/index';
import { StreamingEventType } from '@/lib/services/websocket-types';

export interface EventSegment {
  id: string; // Unique identifier for this segment
  messageId: string; // Parent message ID
  eventType: StreamingEventType;
  content: string; // Content for this segment
  eventData?: Record<string, any>; // Event-specific data
  timestamp: string; // When this segment was created
  sequence: number; // Order in the message
  contentBlockIndex?: number; // Content block this event belongs to
  blockSequence?: number; // Sequence within the content block
}

interface EventSegmentRendererProps {
  segment: EventSegment;
  isStreaming?: boolean;
}

/**
 * Renders a single event segment within a message
 */
export function EventSegmentRenderer({
  segment,
  isStreaming,
}: EventSegmentRendererProps) {
  // Get the appropriate renderer based on the segment's event type
  const Renderer = getRendererForEventType(segment.eventType);

  return (
    <div className="mb-2 last:mb-0 gap-2 md:max-w-[60%] mx-auto">
      <Renderer
        messageId={segment.messageId}
        content={segment.content}
        isStreaming={isStreaming}
        eventData={segment.eventData}
        segmentId={segment.id}
        contentBlockIndex={segment.contentBlockIndex}
        blockSequence={segment.blockSequence}
      />
    </div>
  );
}
