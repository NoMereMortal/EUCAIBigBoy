// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import React from 'react';
import { MessageRendererProps } from '@/components/chat/message-renderers';
import { AlertTriangle } from 'lucide-react';

export function ErrorMessageRenderer({
  content,
  eventData,
}: MessageRendererProps) {
  // Extract error message and type from eventData
  const errorMessage = eventData?.message || content || 'An error occurred';
  const errorDetails = eventData?.details;

  return (
    <div className="text-gray-600 dark:text-gray-300 text-sm">
      {/* Simple error indicator */}
      <div className="flex items-center gap-2 text-destructive mb-2">
        <AlertTriangle className="h-4 w-4" />
        <span>Error</span>
      </div>

      {/* Error message */}
      <div className="whitespace-pre-wrap">{errorMessage}</div>

      {/* Optional error details */}
      {errorDetails && (
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer">Error details</summary>
          <pre className="mt-1 font-mono whitespace-pre-wrap break-all">
            {JSON.stringify(errorDetails, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
