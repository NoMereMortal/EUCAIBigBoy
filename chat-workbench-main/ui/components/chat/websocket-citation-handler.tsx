// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import React, { useEffect, useState } from 'react';
import {
  getWebSocketClient,
  registerWebSocketHandlers,
} from '@/lib/services/websocket-service';
import { CitationEvent, DocumentEvent } from '@/lib/services/websocket-types';
import { useCitationStore } from '@/lib/store/citation-slice';
import { useMessageStore } from '@/lib/store/message/message-slice';
import { MessageState } from '@/lib/store/message/message-types';

// Import the CitationState type for proper typing
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

/**
 * Component that listens to WebSocket events and updates the citation store
 * This should be mounted near the top of your app to ensure citation handling.
 */
export function WebSocketCitationHandler() {
  const addCitation = useCitationStore(
    (state: CitationState) => state.addCitation,
  );
  const addDocument = useCitationStore(
    (state: CitationState) => state.addDocument,
  );
  // Use appendToMessage to force re-renders in UI
  const appendToMessage = useMessageStore(
    (state: MessageState) => state.appendToMessage,
  );
  const messages = useMessageStore((state: MessageState) => state.messages);
  // Track state for forced rerenders
  const [forceUpdateCounter, setForceUpdateCounter] = useState(0);

  // Force re-render effect when citations or documents are added
  useEffect(() => {
    // This will trigger every time forceUpdateCounter changes
    if (forceUpdateCounter > 0) {
      console.debug('Forcing UI refresh due to citation/document update');
    }
  }, [forceUpdateCounter]);

  useEffect(() => {
    // Register handlers for citation and document events
    const ws = getWebSocketClient();

    const handlers = {
      onCitationEvent: (event: CitationEvent) => {
        console.debug('Citation event received:', event);
        const {
          document_id,
          response_id,
          text,
          page,
          section,
          reference_number,
          document_title,
          document_pointer,
        } = event;

        // Generate a citation ID if one wasn't provided
        const citation_id = `citation-${response_id}-${Date.now()}`;

        if (document_id && response_id) {
          addCitation({
            citation_id,
            document_id,
            response_id,
            text: text || '',
            page,
            section,
            reference_number,
            document_title,
            document_pointer,
          });

          // Force UI update after citation added
          setForceUpdateCounter((prev) => prev + 1);

          // Skip forced re-renders during streaming to prevent corruption
          if (response_id && messages[response_id]) {
            const messageStore = useMessageStore.getState();
            const isCurrentlyStreaming =
              messageStore.isStreaming &&
              messageStore.currentStreamingId === response_id;

            if (!isCurrentlyStreaming) {
              try {
                console.debug(
                  'Citation handler triggering message refresh (not streaming)',
                );
                appendToMessage(response_id, '');
              } catch (error) {
                console.error(
                  'Citation handler error triggering message update:',
                  error,
                );
              }
            } else {
              console.debug(
                'Citation handler skipping re-render during streaming to prevent corruption',
              );
            }
          }
        }

        // If document info is included, add/update document as well
        if (document_id && (document_title || document_pointer)) {
          addDocument({
            document_id,
            title: document_title || 'Unknown Document',
            pointer: document_pointer || '',
            mime_type: 'application/pdf', // Default mime type
          });

          // Force UI update after document added
          setForceUpdateCounter((prev) => prev + 1);
        }
      },

      onDocumentEvent: (event: DocumentEvent) => {
        console.debug('Document event received:', event);
        const {
          pointer,
          mime_type,
          title,
          page_count,
          word_count,
          response_id,
        } = event;

        // Generate a document ID from the pointer or timestamp
        const document_id = `doc-${pointer.split('/').pop() || Date.now()}`;

        if (pointer) {
          addDocument({
            document_id,
            title: title || 'Unknown Document',
            pointer,
            mime_type,
            page_count,
            word_count,
          });

          // Force UI update after document added
          setForceUpdateCounter((prev) => prev + 1);

          // Skip forced re-renders during streaming to prevent corruption
          if (response_id && messages[response_id]) {
            const messageStore = useMessageStore.getState();
            const isCurrentlyStreaming =
              messageStore.isStreaming &&
              messageStore.currentStreamingId === response_id;

            if (!isCurrentlyStreaming) {
              try {
                console.debug(
                  'Citation handler triggering message refresh for document (not streaming)',
                );
                appendToMessage(response_id, '');
              } catch (error) {
                console.error(
                  'Citation handler error triggering message update:',
                  error,
                );
              }
            } else {
              console.debug(
                'Citation handler skipping re-render during streaming to prevent corruption',
              );
            }
          }
        }
      },
    };

    // Register the handlers
    const unregister = registerWebSocketHandlers(ws, handlers);

    // Cleanup function
    return () => {
      if (unregister) {
        unregister();
      }
    };
  }, [
    addCitation,
    addDocument,
    appendToMessage,
    messages,
    setForceUpdateCounter,
  ]);

  // This component doesn't render anything
  return null;
}
