// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import React from 'react';
import { Markdown } from '@/components/ui/markdown';
import { MessageRendererProps } from '@/components/chat/message-renderers';
import { Info } from 'lucide-react'; // For status icon

export function StatusMessageRenderer({
  content,
  eventData,
  isStreaming,
}: MessageRendererProps) {
  // Extract status info from eventData
  const statusType = eventData?.status_type || 'info';

  return (
    <div className="text-gray-600 dark:text-gray-300 text-sm">
      {/* Simple status indicator */}
      <div className="flex items-center gap-2 mb-2">
        <Info className="h-4 w-4" />
        <span className="capitalize">{statusType}</span>
      </div>

      {/* Main content with markdown support */}
      <div className="prose-sm max-w-none dark:prose-invert">
        <Markdown content={content || ''} isStreaming={isStreaming} />
      </div>

      {/* Timestamp if available */}
      {eventData?.timestamp && (
        <div className="mt-2 text-xs text-muted-foreground">
          {new Date(eventData.timestamp).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
