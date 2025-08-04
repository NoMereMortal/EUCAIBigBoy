// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import React, { useState, useEffect } from 'react';
import { MessageRendererProps } from '@/components/chat/message-renderers';
import { useCitationStore } from '@/lib/store/citation-slice';

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

export function CitationRenderer({ content, eventData }: MessageRendererProps) {
  const { citation_id, document_id } = eventData || {};
  const getDocumentById = useCitationStore(
    (state: CitationState) => state.getDocumentById,
  );

  // Retrieve citation and document data
  const citations = useCitationStore((state: CitationState) => state.citations);
  const citation = citation_id ? citations[citation_id] : undefined;
  const document = document_id ? getDocumentById(document_id) : undefined;

  // Force a component update when citations change
  const [updateTrigger, setUpdateTrigger] = useState(0);

  // Debug rendering for citations
  useEffect(() => {
    console.debug(
      'Rendering citation:',
      citation_id,
      'Found in store:',
      !!citation,
      'Document ID:',
      document_id,
      'EventData:',
      eventData,
    );
  }, [citation_id, citation, document_id, eventData]);

  // Re-render when citations change
  useEffect(() => {
    // This will trigger whenever citations in the store change
    setUpdateTrigger((prev: number) => prev + 1);
  }, [citations]);

  if (!citation) {
    return (
      <div className="py-1 text-sm text-gray-500 italic border-l-2 border-gray-300 pl-2 my-1">
        Citation information unavailable
      </div>
    );
  }

  // Use document from store or citation's document info
  const documentTitle =
    citation.document_title || (document ? document.title : 'Unknown Document');
  const documentPointer = citation.document_pointer || document?.pointer || '';

  const handleCitationClick = () => {
    if (documentPointer) {
      window.open(documentPointer, '_blank');
    }
  };

  // Format reference number if present
  const referenceLabel =
    citation.reference_number !== undefined ? (
      <span className="text-blue-600 dark:text-blue-400 mr-1">
        [{citation.reference_number}]
      </span>
    ) : null;

  return (
    <div
      className="py-1 text-sm text-gray-500 italic border-l-2 border-blue-300 pl-2 my-1 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
      onClick={handleCitationClick}
    >
      <div className="font-medium text-blue-600 dark:text-blue-400 text-xs flex items-center">
        {referenceLabel}
        <span>{documentTitle}</span>
        {citation.page && <span className="ml-1">(Page {citation.page})</span>}
      </div>
      <div className="text-gray-600 dark:text-gray-400 mt-1">
        &ldquo;{citation.text}&rdquo;
        {citation.section && (
          <span className="block text-xs mt-1">
            Section: {citation.section}
          </span>
        )}
      </div>
    </div>
  );
}
