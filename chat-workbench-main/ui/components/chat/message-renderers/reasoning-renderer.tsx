// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import React from 'react';
import { MessageRendererProps } from '@/components/chat/message-renderers';
import { Markdown } from '@/components/ui/markdown';

export function ReasoningMessageRenderer({
  content,
  isStreaming,
}: MessageRendererProps) {
  return (
    <div className="md:max-w-[80%] mx-auto relative">
      <div className="py-2 text-gray-600 dark:text-gray-300 text-sm">
        {/* Simple content display */}
        <div className="prose-sm max-w-none dark:prose-invert">
          <Markdown content={content || ''} isStreaming={isStreaming} />
        </div>
      </div>
    </div>
  );
}
