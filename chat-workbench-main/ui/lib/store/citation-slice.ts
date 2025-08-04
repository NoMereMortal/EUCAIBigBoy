// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { create } from 'zustand';

export interface Citation {
  citation_id: string;
  document_id: string;
  reference_number?: number; // New field for citation numbering
  document_title?: string; // New field for document title
  document_pointer?: string; // New field for document URL
  text: string;
  page?: number;
  section?: string;
  response_id: string;
}

export interface DocumentInfo {
  document_id: string;
  title: string;
  pointer: string; // URL to open when clicked
  mime_type: string;
  page_count?: number;
  word_count?: number;
}

interface CitationState {
  // Data
  citations: Record<string, Citation>; // Keyed by citation_id
  documents: Record<string, DocumentInfo>; // Keyed by document_id
  citationsByResponse: Record<string, string[]>; // Maps response_id -> citation_ids[]

  // Actions
  addCitation: (citation: Citation) => void;
  addDocument: (document: DocumentInfo) => void;
  clearCitationsForResponse: (responseId: string) => void;
  getCitationsForResponse: (responseId: string) => Citation[];
  getDocumentById: (documentId: string) => DocumentInfo | undefined;
}

export const useCitationStore = create<CitationState>((set, get) => ({
  citations: {},
  documents: {},
  citationsByResponse: {},

  addCitation: (citation) => {
    set((state) => {
      // Add citation to the citations map
      const updatedCitations = { ...state.citations };
      updatedCitations[citation.citation_id] = citation;

      // Add to response mapping
      const updatedCitationsByResponse = { ...state.citationsByResponse };
      if (!updatedCitationsByResponse[citation.response_id]) {
        updatedCitationsByResponse[citation.response_id] = [];
      }
      updatedCitationsByResponse[citation.response_id].push(
        citation.citation_id,
      );

      return {
        citations: updatedCitations,
        citationsByResponse: updatedCitationsByResponse,
      };
    });
  },

  addDocument: (document) => {
    set((state) => ({
      documents: {
        ...state.documents,
        [document.document_id]: document,
      },
    }));
  },

  clearCitationsForResponse: (responseId) => {
    set((state) => {
      // Get citation IDs for this response
      const citationIds = state.citationsByResponse[responseId] || [];

      // Create new citations object without these citations
      const updatedCitations = { ...state.citations };
      citationIds.forEach((id) => {
        delete updatedCitations[id];
      });

      // Remove response from citationsByResponse
      const { [responseId]: _, ...remainingCitationsByResponse } =
        state.citationsByResponse;

      return {
        citations: updatedCitations,
        citationsByResponse: remainingCitationsByResponse,
      };
    });
  },

  getCitationsForResponse: (responseId) => {
    const state = get();
    const citationIds = state.citationsByResponse[responseId] || [];
    return citationIds.map((id) => state.citations[id]).filter(Boolean);
  },

  getDocumentById: (documentId) => {
    return get().documents[documentId];
  },
}));
