// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import React, { useEffect, useRef } from 'react';
import { Markdown } from '@/components/ui/markdown';
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

// CSS for citation tooltips
const citationStyles = `
.citation-marker {
  color: #0066cc;
  cursor: pointer;
  position: relative;
  border-radius: 3px;
  padding: 0 2px;
  font-weight: bold;
  white-space: nowrap;
}

.citation-marker:hover {
  background-color: rgba(0, 102, 204, 0.1);
}

.citation-tooltip {
  display: none;
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background-color: #333;
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 0.75rem;
  white-space: normal;
  width: 280px;
  z-index: 10;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
  margin-bottom: 5px;
  font-weight: normal;
}

.citation-tooltip:after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  margin-left: -5px;
  border-width: 5px;
  border-style: solid;
  border-color: #333 transparent transparent transparent;
}

.citation-marker:hover .citation-tooltip {
  display: block;
}

.citation-title {
  font-weight: bold;
  margin-bottom: 4px;
  font-size: 0.8rem;
}

.citation-text {
  margin-bottom: 4px;
  font-style: italic;
  font-size: 0.75rem;
}

.citation-meta {
  font-size: 0.7rem;
  color: #ccc;
}
`;

// Simple citation list component
function CitationList({ responseId }: { responseId: string }) {
  const getCitationsForResponse = useCitationStore(
    (state) => state.getCitationsForResponse,
  );
  const getDocumentById = useCitationStore((state) => state.getDocumentById);

  const citations = getCitationsForResponse(responseId);

  if (citations.length === 0) return null;

  return (
    <div className="text-xs text-gray-500 dark:text-gray-400">
      <div className="font-semibold mb-2">References:</div>
      {citations.map((citation, index) => {
        const document = getDocumentById(citation.document_id);
        const title =
          citation.document_title ||
          (document ? document.title : 'Unknown Document');

        return (
          <div key={citation.citation_id} className="mb-1 flex items-start">
            <span className="font-mono text-blue-600 dark:text-blue-400 mr-2 flex-shrink-0">
              [{citation.reference_number || index + 1}]
            </span>
            <div className="flex-1">
              <div className="font-medium">{title}</div>
              {citation.text && (
                <div className="text-gray-400 italic text-xs mt-1">
                  &ldquo;{citation.text.substring(0, 100)}
                  {citation.text.length > 100 ? '...' : ''}&rdquo;
                </div>
              )}
              {(citation.page || citation.section) && (
                <div className="text-gray-400 text-xs mt-1">
                  {citation.page && `Page ${citation.page}`}
                  {citation.page && citation.section && ' | '}
                  {citation.section && `Section: ${citation.section}`}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function DefaultMessageRenderer({
  content,
  isStreaming,
  messageId,
}: MessageRendererProps) {
  const markdownRef = useRef<HTMLDivElement>(null);
  const citations = useCitationStore((state: CitationState) => state.citations);
  const getCitationsForResponse = useCitationStore(
    (state: CitationState) => state.getCitationsForResponse,
  );
  const getDocumentById = useCitationStore(
    (state: CitationState) => state.getDocumentById,
  );

  // Process content to add citation references if needed
  const processedContent = React.useMemo(() => {
    if (!content || !messageId) return content;

    // Get citations for this response
    const responseCitations = getCitationsForResponse(messageId);
    if (responseCitations.length === 0) return content;

    // Replace citation markers with HTML
    let processedText = content;
    responseCitations.forEach((citation) => {
      // Use reference_number if available, otherwise fallback to citation_id
      const markerText =
        citation.reference_number !== undefined
          ? citation.reference_number
          : citation.citation_id;
      const citationMarker = `[${markerText}]`;

      // Get document either from citation's document info or from store
      const documentTitle = citation.document_title || '';
      const document = getDocumentById(citation.document_id);
      const title =
        documentTitle || (document ? document.title : 'Unknown Document');

      if (processedText.includes(citationMarker)) {
        const tooltipContent = `
                    <span class="citation-tooltip">
                        <span class="citation-title">${title}</span>
                        <span class="citation-text">${citation.text.substring(0, 120)}${citation.text.length > 120 ? '...' : ''}</span>
                        <span class="citation-meta">
                            ${citation.page ? `Page ${citation.page}` : ''}
                            ${citation.section ? ` | Section: ${citation.section}` : ''}
                        </span>
                    </span>
                `;

        const replacement = `<span class="citation-marker" data-citation-id="${citation.citation_id}" data-document-id="${citation.document_id}">${citationMarker}${tooltipContent}</span>`;
        processedText = processedText.replace(citationMarker, replacement);
      }
    });

    return processedText;
  }, [content, messageId, getCitationsForResponse, getDocumentById]);

  // Add click handlers for citations
  useEffect(() => {
    if (!markdownRef.current) return;

    const handleCitationClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains('citation-marker')) {
        e.preventDefault();
        e.stopPropagation();

        const documentId = target.getAttribute('data-document-id');
        if (documentId) {
          const document = getDocumentById(documentId);
          if (document?.pointer) {
            window.open(document.pointer, '_blank');
          }
        }
      }
    };

    const container = markdownRef.current;
    container.addEventListener('click', handleCitationClick);

    return () => {
      container.removeEventListener('click', handleCitationClick);
    };
  }, [getDocumentById]);

  return (
    <div className="py-2 text-gray-600 dark:text-gray-300 text-sm">
      {/* Add citation styles */}
      <style dangerouslySetInnerHTML={{ __html: citationStyles }} />

      {/* First render the processed content with citations as dangerouslySetInnerHTML */}
      {processedContent && processedContent !== content ? (
        <div
          className="prose-sm max-w-none dark:prose-invert"
          ref={markdownRef}
          dangerouslySetInnerHTML={{ __html: processedContent }}
        />
      ) : (
        /* Fall back to regular markdown rendering if no citations were processed */
        <div
          className="prose-sm max-w-none dark:prose-invert"
          ref={markdownRef}
        >
          <Markdown content={content || ''} isStreaming={isStreaming} />
        </div>
      )}
    </div>
  );
}
