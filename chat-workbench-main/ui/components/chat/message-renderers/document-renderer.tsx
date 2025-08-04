// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import React, { useRef, useEffect, useMemo, useState } from 'react';
import { MessageRendererProps } from '@/components/chat/message-renderers';
import { useCitationStore } from '@/lib/store/citation-slice';
import { useMessageStore } from '@/lib/store/message/message-slice';
import { MessageState } from '@/lib/store/message/message-types';

// Define CitationState interface for proper typing
interface CitationState {
  citations: Record<string, any>;
  documents: Record<string, any>;
  citationsByResponse: Record<string, string[]>;
  addCitation: (citation: any) => void;
  addDocument: (document: any) => void;
  clearCitationsForResponse: (responseId: string) => void;
  getCitationsForResponse: (responseId: string) => any[];
  getDocumentById: (documentId: string) => any | undefined;
}

// CSS for document references section
const documentSectionStyles = `
.document-references-section {
  margin-top: 1.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid #e5e7eb;
}

.document-references-heading {
  font-size: 0.875rem;
  font-weight: 600;
  color: #4b5563;
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
}

.dark .document-references-heading {
  color: #9ca3af;
}

.document-references-count {
  font-size: 0.75rem;
  font-weight: normal;
  color: #6b7280;
  margin-left: 0.5rem;
}
`;

export function DocumentRenderer({ content, eventData }: MessageRendererProps) {
  const { document_id } = eventData || {};
  const getDocumentById = useCitationStore(
    (state: CitationState) => state.getDocumentById,
  );
  const documents = useCitationStore((state: CitationState) => state.documents);
  const document = document_id ? getDocumentById(document_id) : undefined;

  // Force a component update when documents change
  const [updateTrigger, setUpdateTrigger] = useState(0);

  // Debug rendering
  useEffect(() => {
    console.debug(
      'Rendering document:',
      document_id,
      'Found in store:',
      !!document,
      'EventData:',
      eventData,
    );
  }, [document_id, document, eventData]);

  // Determine if this is the first document in the response to show the section header
  const messageId = eventData?.messageId;

  // Get messages from the message store
  const messages = useMessageStore((state: MessageState) => state.messages);

  // Re-render when updateTrigger changes
  useEffect(() => {
    // This effect doesn't need to depend on messages directly
    // as we'll update the trigger in response to relevant changes
    setUpdateTrigger((prev: number) => prev + 1);
  }, []); // Empty dependency array as we don't need to re-run this effect

  // Find all document segments in current message to determine if this is the first one
  const { isFirstDocument, documentCount } = useMemo(() => {
    if (!messageId || !messages[messageId])
      return { isFirstDocument: false, documentCount: 0 };

    // Get all document segments for this message by checking message parts or eventData
    const message = messages[messageId];
    let docCount = 0;
    let isFirst = false;

    // If the message has parts with document parts
    if (message.parts && Array.isArray(message.parts)) {
      const documentParts = message.parts.filter(
        (part: any) => part.part_kind === 'document',
      );
      docCount = documentParts.length;
      // Check if this is the first document by comparing document_id
      if (documentParts.length > 0) {
        const firstDocPart = documentParts[0] as any;
        isFirst = firstDocPart.document_id === document_id;
      }
    }

    // For streaming messages that use eventData.eventHistory
    if (message.eventData?.eventHistory?.events) {
      const docEvents = message.eventData.eventHistory.events.filter(
        (event: any) => event.type === 'document',
      );
      docCount = Math.max(docCount, docEvents.length);
      if (docEvents.length > 0 && docEvents[0].data) {
        isFirst = docEvents[0].data.document_id === document_id;
      }
    }

    // Default to true if we can't determine (show section header anyway)
    return {
      isFirstDocument: isFirst || docCount === 0,
      documentCount: docCount,
    };
  }, [document_id, messageId, messages]);

  if (!document) {
    return (
      <div className="py-2 px-3 bg-gray-50 dark:bg-gray-800 rounded-md text-sm mt-2">
        <div className="font-medium">Document Reference</div>
        <div className="text-gray-600 dark:text-gray-400 mt-1">
          {content || 'Document information unavailable'}
        </div>
      </div>
    );
  }

  const handleDocumentClick = () => {
    if (document?.pointer) {
      window.open(document.pointer, '_blank');
    }
  };

  return (
    <>
      {/* Add document section styles */}
      <style dangerouslySetInnerHTML={{ __html: documentSectionStyles }} />

      {/* Show section header for the first document */}
      {isFirstDocument && (
        <div className="document-references-section">
          <div className="document-references-heading">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4 mr-1"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
              />
            </svg>
            <span>References</span>
            <span className="document-references-count">({documentCount})</span>
          </div>
        </div>
      )}

      <div
        className="py-2 px-3 bg-gray-50 dark:bg-gray-800 rounded-md text-sm mt-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        onClick={handleDocumentClick}
      >
        <div className="font-medium flex items-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4 mr-1"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <span>{document?.title}</span>
        </div>
        <div className="text-gray-600 dark:text-gray-400 mt-1 text-xs">
          {document?.page_count && (
            <span className="mr-2">{document.page_count} pages</span>
          )}
          {document?.word_count && <span>{document.word_count} words</span>}
          <div className="mt-1 text-blue-600 dark:text-blue-400 underline text-xs">
            Click to open document
          </div>
        </div>
      </div>
    </>
  );
}
