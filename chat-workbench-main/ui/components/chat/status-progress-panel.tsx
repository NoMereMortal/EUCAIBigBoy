// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { cn } from '@/lib/utils';
import {
  getWebSocketClient,
  registerWebSocketHandlers,
} from '@/lib/services/websocket-service';
import {
  StatusEvent,
  ToolCallEvent,
  DocumentEvent,
  ContentEvent,
  ResponseEndEvent,
} from '@/lib/services/websocket-types';
import { useMessageStore } from '@/lib/store/message/message-slice';
import { useSettingsStore } from '@/lib/store';

// Search query pill component
const SearchPill = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => (
  <span
    className={cn(
      'inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-100 text-gray-700 border',
      className,
    )}
  >
    {children}
  </span>
);

// Loading spinner component
const LoadingSpinner = () => (
  <div className="inline-flex items-center">
    <div className="w-3 h-3 border-2 border-gray-300 border-t-primary rounded-full animate-spin"></div>
  </div>
);

// Document list item component
const DocumentItem = ({
  title,
  domain,
}: {
  title: string;
  domain?: string;
}) => {
  // Extract favicon URL from domain
  const faviconUrl = domain
    ? `https://www.google.com/s2/favicons?domain=${domain}&sz=16`
    : null;

  return (
    <div className="flex items-center space-x-2 text-sm text-gray-700">
      {faviconUrl && (
        <Image
          src={faviconUrl}
          alt={`${domain} favicon`}
          width={16}
          height={16}
          className="w-4 h-4 flex-shrink-0"
          onError={(e) => {
            // Fallback to generic document icon if favicon fails
            e.currentTarget.style.display = 'none';
          }}
        />
      )}
      <span className="truncate">{title}</span>
      {domain && <span className="text-xs text-gray-500">{domain}</span>}
    </div>
  );
};

// Collapsible section component
const CollapsibleSection = ({
  title,
  isOpen,
  onToggle,
  isActive,
  type,
  children,
}: {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  isActive: boolean;
  type: string;
  children: React.ReactNode;
}) => (
  <div
    className={cn(
      'border-l-2 pl-4 transition-all duration-200',
      isActive ? 'border-primary' : 'border-gray-200',
    )}
  >
    <button
      onClick={onToggle}
      className={cn(
        'flex items-center space-x-2 text-sm font-medium mb-2 transition-colors duration-200',
        isActive
          ? 'text-primary hover:text-primary/80'
          : 'text-gray-700 hover:text-gray-900',
      )}
    >
      {isActive && <LoadingSpinner />}
      <span className="flex-1 text-left">{title}</span>
      <span
        className={cn(
          'transform transition-transform duration-200 text-xs text-gray-400',
          isOpen ? 'rotate-90' : 'rotate-0',
        )}
      >
        ▶
      </span>
    </button>
    {isOpen && (
      <div
        className={cn(
          'space-y-2 pb-2 transition-all duration-200',
          isActive ? 'animate-in slide-in-from-top-1' : '',
        )}
      >
        {children}
      </div>
    )}
  </div>
);

interface StatusSection {
  id: string;
  type:
    | 'planning'
    | 'searching'
    | 'evaluating'
    | 'search_complete'
    | 'refining'
    | 'reading'
    | 'finished'
    | 'finalizing'
    | 'progress';
  title: string;
  timestamp: string;
  isActive: boolean;
  isOpen: boolean;
  phase?: string;
  data: {
    searchQueries?: {
      semantic: string[];
      keywords: string[];
      httpDomains: string[];
    };
    progressMessage?: string;
    documents?: Array<{
      id: string;
      title: string;
      domain?: string;
    }>;
    documentsFound?: number;
    searchPhase?: 'foundation' | 'refinement' | 'start' | 'planning' | string;
  };
}

interface StatusProgressState {
  isVisible: boolean;
  sections: StatusSection[];
  researchCompleted: boolean;
  // Track recently received status events to prevent duplicates
  recentStatusEvents: {
    [key: string]: {
      phase: string;
      timestamp: number;
      title: string;
    };
  };
  // Track the current research phase for proper state transitions
  currentPhase:
    | 'start'
    | 'planning'
    | 'searching'
    | 'evaluating'
    | 'analyzing'
    | 'complete'
    | null;
}

interface StatusProgressPanelProps {
  responseId: string;
  isHistorical?: boolean;
  onFinished?: () => void;
}

// Create a registry outside of component to track registered handlers globally
// This doesn't use React hooks so it's safe to define outside the component
const registeredHandlersRegistry = new Set<string>();

export const StatusProgressPanel: React.FC<StatusProgressPanelProps> = ({
  responseId,
  isHistorical = false,
  onFinished,
}) => {
  // Get the selected task handler
  const selectedTaskHandler = useSettingsStore(
    (state: { selectedTaskHandler: string }) => state.selectedTaskHandler,
  );

  // Initialize all hooks at the top level
  const [state, setState] = useState<StatusProgressState>({
    isVisible: true,
    sections: [],
    researchCompleted: false,
    recentStatusEvents: {},
    currentPhase: null,
  });

  const [responseEnded, setResponseEnded] = useState(false);
  const [waitingForContent, setWaitingForContent] = useState(false);
  // Track if handlers are registered for this component instance
  const handlersRegisteredRef = React.useRef(false);
  // Track if we've already shown the research completion message
  const researchCompletionShownRef = React.useRef(false);

  // Get message store functions for research progress
  const {
    updateResearchProgress,
    completeResearch,
    isMessageResearching,
    messages,
    messageMetadata,
  } = useMessageStore();

  // Define a type for status data to avoid TypeScript errors
  interface StatusData {
    phase?: string;
    title?: string;
    text?: string;
    type?: string;
    search_queries?: string[];
    keyword_queries?: string[];
    http_domains?: string[];
    documents_found?: number;
    search_type?: string;
    [key: string]: any; // Allow for other properties
  }

  // Parse status message for structured data with recursive JSON parsing
  const parseStatusMessage = useCallback((message: string): StatusData => {
    try {
      // Try to parse as JSON
      let data = JSON.parse(message);

      // Enhanced recursive parsing for nested JSON strings
      const parseNestedJson = (obj: any): any => {
        if (typeof obj !== 'object' || obj === null) return obj;

        // Handle arrays
        if (Array.isArray(obj)) {
          return obj.map((item) => parseNestedJson(item));
        }

        // Handle objects
        const result: any = {};
        Object.keys(obj).forEach((key) => {
          const value = obj[key];

          // Try to parse string values that look like JSON
          if (typeof value === 'string') {
            if (
              (value.startsWith('{') && value.endsWith('}')) ||
              (value.startsWith('[') && value.endsWith(']'))
            ) {
              try {
                result[key] = parseNestedJson(JSON.parse(value));
                console.log(`Parsed nested JSON in field ${key}`);
              } catch (e) {
                result[key] = value; // Keep as string if parsing fails
              }
            } else {
              result[key] = value;
            }
          } else if (typeof value === 'object' && value !== null) {
            // Recursively parse nested objects
            result[key] = parseNestedJson(value);
          } else {
            result[key] = value;
          }
        });

        return result;
      };

      // Apply recursive parsing
      data = parseNestedJson(data);

      console.log('Parsed status data:', data);
      return data;
    } catch (e) {
      console.log('Simple status message:', message);

      // Try to extract useful information from malformed status events
      if (typeof message === 'string') {
        // Try to extract phase information from the raw message
        const phaseMatch = message.match(/phase["\s:]+([a-z_]+)/i);
        const phase = phaseMatch ? phaseMatch[1] : 'progress';

        // Try to extract text content
        const textMatch = message.match(/text["\s:]+([^"]+)/i);
        const text = textMatch ? textMatch[1] : message;

        return {
          phase: phase,
          text: text,
          title: `Processing ${phase}`,
        };
      }

      return { type: 'simple', text: message };
    }
  }, []);

  // Helper function to create a new section
  const createSection = useCallback(
    (
      type: StatusSection['type'],
      title: string,
      data: StatusSection['data'] = {},
    ): StatusSection => ({
      id: `${type}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      type,
      title,
      timestamp: new Date().toISOString(),
      isActive: type !== 'finished',
      isOpen: true,
      data,
    }),
    [],
  );

  // Helper function to auto-collapse older sections
  const autoCollapseSections = useCallback(
    (sections: StatusSection[]): StatusSection[] => {
      if (sections.length <= 2) return sections;

      // Keep the last 2 sections open, collapse the rest
      return sections.map((section, index) => ({
        ...section,
        isOpen: index >= sections.length - 2,
      }));
    },
    [],
  );

  // Historical reconstruction from message parts
  useEffect(() => {
    // Reset the completion shown ref when the component mounts
    researchCompletionShownRef.current = false;

    if (isHistorical) {
      console.log('Reconstructing historical research data for:', responseId);

      const message = messages[responseId];
      if (!message?.parts) {
        console.warn(
          'No message parts found for historical reconstruction:',
          responseId,
        );
        return;
      }

      // Find status event parts and document parts
      const statusEventParts = message.parts.filter(
        (part: any) =>
          part.metadata?.status_event === 'true' ||
          (typeof part.content === 'string' &&
            part.content.includes('research_start:')),
      );

      const documentParts = message.parts.filter(
        (part: any) => part.part_kind === 'document',
      );

      console.log('Found historical data:', {
        statusEventParts: statusEventParts.length,
        documentParts: documentParts.length,
      });

      // Reconstruct sections from status event data
      let reconstructedSections: StatusSection[] = [];

      statusEventParts.forEach((part: any) => {
        if (!part.content) return;

        // Parse research events from content
        const eventStrings = part.content.split(
          /(?=research_start:|research_progress:|research_complete:)/,
        );

        eventStrings.forEach((eventStr: string) => {
          const match = eventStr.match(
            /(research_start|research_progress|research_complete):\s*(\{.*?\})/,
          );
          if (match) {
            try {
              const [, eventType, jsonStr] = match;
              const eventData = JSON.parse(jsonStr);

              console.log('Parsing historical event:', {
                eventType,
                eventData,
              });

              const title =
                eventData.title || eventData.text || 'Processing...';
              const phase = eventData.phase || 'progress';

              switch (phase) {
                case 'start':
                case 'planning':
                  reconstructedSections.push(
                    createSection('planning', title, {
                      progressMessage: eventData.text,
                      searchPhase: phase,
                    }),
                  );
                  break;

                case 'searching':
                  const searchQueries = {
                    semantic: eventData.search_queries || [],
                    keywords: eventData.keyword_queries || [],
                    httpDomains: eventData.http_domains || [],
                  };

                  reconstructedSections.push(
                    createSection('searching', title, {
                      searchQueries,
                      progressMessage: eventData.text,
                      searchPhase: eventData.search_type || 'foundation',
                    }),
                  );
                  break;

                case 'evaluating':
                  reconstructedSections.push(
                    createSection('evaluating', title, {
                      progressMessage: eventData.text,
                      documentsFound: eventData.documents_found,
                    }),
                  );
                  break;

                case 'analyzing':
                  reconstructedSections.push(
                    createSection('search_complete', title, {
                      progressMessage: eventData.text,
                    }),
                  );
                  break;

                case 'complete':
                  reconstructedSections.push(createSection('finished', title));
                  break;

                default:
                  reconstructedSections.push(
                    createSection('progress', title, {
                      progressMessage: eventData.text,
                    }),
                  );
                  break;
              }
            } catch (e) {
              console.warn('Failed to parse historical event:', eventStr, e);
            }
          }
        });
      });

      // Add document reading section if documents exist
      if (documentParts.length > 0) {
        const documents = documentParts.map((part: any) => {
          let domain: string | undefined;
          try {
            if (part.pointer?.startsWith('http')) {
              domain = new URL(part.pointer).hostname;
            }
          } catch (e) {
            // Ignore parsing errors
          }

          return {
            id: part.pointer || part.title || Math.random().toString(),
            title: part.title || 'Unknown Document',
            domain,
          };
        });

        // Insert reading section before the finished section
        const finishedIndex = reconstructedSections.findIndex(
          (s) => s.type === 'finished',
        );
        const readingSection = createSection(
          'reading',
          `Reading sources · ${documents.length}`,
          { documents },
        );

        if (finishedIndex >= 0) {
          reconstructedSections.splice(finishedIndex, 0, readingSection);
        } else {
          reconstructedSections.push(readingSection);
        }
      }

      // Apply auto-collapse and set state
      reconstructedSections = autoCollapseSections(reconstructedSections);

      // Mark all as inactive since research is complete
      reconstructedSections = reconstructedSections.map((section) => ({
        ...section,
        isActive: false,
      }));

      setState({
        isVisible: true,
        sections: reconstructedSections,
        researchCompleted: true,
        recentStatusEvents: {},
        currentPhase: 'complete',
      });

      console.log('Historical reconstruction complete:', {
        totalSections: reconstructedSections.length,
        sectionTypes: reconstructedSections.map((s) => s.type),
      });

      return;
    }

    // Live WebSocket event handlers for streaming messages
    const ws = getWebSocketClient();
    if (!ws) {
      console.warn(
        'WebSocket client not available for responseId:',
        responseId,
      );
      return;
    }

    // Skip registration if handlers are already registered for this responseId
    if (
      registeredHandlersRegistry.has(responseId) ||
      handlersRegisteredRef.current
    ) {
      console.log('Handlers already registered for responseId:', responseId);
      return;
    }

    // Mark as registered both in global registry and local ref
    registeredHandlersRegistry.add(responseId);
    handlersRegisteredRef.current = true;

    console.log('Registering event handlers for responseId:', responseId);

    const handlers = {
      onStatusEvent: (event: StatusEvent) => {
        console.log('Raw StatusEvent received:', {
          eventResponseId: event.response_id,
          targetResponseId: responseId,
          matches: event.response_id === responseId,
          eventStatus: event.status,
          eventMessage: event.message,
          timestamp: new Date().toISOString(),
        });

        if (event.response_id !== responseId) {
          console.debug('Ignoring StatusEvent for different responseId:', {
            eventResponseId: event.response_id,
            targetResponseId: responseId,
          });
          return;
        }

        console.log(
          'Processing StatusEvent for responseId:',
          responseId,
          event,
        );

        // Always parse the message directly with enhanced parsing
        let statusData: StatusData | null = null;
        if (event.message) {
          try {
            // First try direct parsing
            statusData = parseStatusMessage(event.message) as StatusData;
            console.log('Parsed status data:', statusData);

            // Check if we need to do additional parsing on nested fields
            if (statusData && typeof statusData === 'object') {
              // Look for any string fields that might be JSON
              Object.keys(statusData).forEach((key) => {
                if (
                  typeof statusData![key] === 'string' &&
                  statusData![key].startsWith('{') &&
                  statusData![key].endsWith('}')
                ) {
                  try {
                    // Try to parse this field as JSON
                    const parsedField = JSON.parse(statusData![key]);
                    statusData![key] = parsedField;
                    console.log(
                      `Parsed nested JSON in field ${key}:`,
                      parsedField,
                    );
                  } catch (e) {
                    // Keep as string if parsing fails
                  }
                }
              });
            }
          } catch (e) {
            console.warn('Error parsing status message:', e);
            // Create a basic status object as fallback
            statusData = {
              type: 'simple',
              text:
                typeof event.message === 'string'
                  ? event.message
                  : 'Processing...',
              title: 'Processing Research',
            };
          }
        }

        if (!statusData) {
          console.log('No status data to process');
          return;
        }

        // Extract phase information outside of state update to avoid unnecessary renders
        const phase = statusData.phase || 'progress';
        const title = statusData.title || statusData.text || 'Processing...';

        // Add additional logging to help debug status events
        console.log('Processing status event:', {
          phase,
          title,
          statusType: event.status,
          hasPhase: !!statusData.phase,
          hasTitle: !!statusData.title,
          messageType: typeof event.message,
        });

        // Process the status data without unnecessary state updates
        if (statusData) {
          // Handle structured status updates with enhanced titles
          if (statusData && (statusData.phase || statusData.title)) {
            const title =
              statusData.title || statusData.text || 'Processing...';
            const phase = statusData.phase || 'progress';

            switch (phase) {
              case 'start':
                // Only update phase, not researching state (already set on message creation)
                updateResearchProgress(responseId, 'start', true);

                setState((prev) => ({
                  ...prev,
                  sections: autoCollapseSections([
                    ...prev.sections.map((s) => ({ ...s, isActive: false })),
                    createSection('planning', title, {
                      progressMessage: statusData.text,
                      searchPhase: phase,
                    }),
                  ]),
                }));
                return;

              case 'planning':
                // Only update phase, maintain researching state
                updateResearchProgress(responseId, 'planning', true);

                setState((prev) => ({
                  ...prev,
                  sections: autoCollapseSections([
                    ...prev.sections.map((s) => ({ ...s, isActive: false })),
                    createSection('planning', title, {
                      progressMessage: statusData.text,
                      searchPhase: phase,
                    }),
                  ]),
                }));
                return;

              case 'searching':
                // Only update phase, maintain researching state
                updateResearchProgress(responseId, 'searching', true);

                const searchQueries = {
                  semantic: statusData.search_queries || [],
                  keywords: statusData.keyword_queries || [],
                  httpDomains: statusData.http_domains || [],
                };

                setState((prev) => ({
                  ...prev,
                  sections: autoCollapseSections([
                    ...prev.sections.map((s) => ({ ...s, isActive: false })),
                    createSection('searching', title, {
                      searchQueries,
                      progressMessage: statusData.text,
                      searchPhase: statusData.search_type || 'foundation',
                    }),
                  ]),
                }));
                return;

              case 'evaluating':
                // Only update phase, maintain researching state
                updateResearchProgress(responseId, 'evaluating', true);

                setState((prev) => ({
                  ...prev,
                  sections: autoCollapseSections([
                    ...prev.sections.map((s) => ({ ...s, isActive: false })),
                    createSection('evaluating', title, {
                      progressMessage: statusData.text,
                      documentsFound: statusData.documents_found,
                    }),
                  ]),
                }));
                return;

              case 'analyzing':
                // Only update phase, maintain researching state
                updateResearchProgress(responseId, 'analyzing', true);

                setState((prev) => ({
                  ...prev,
                  sections: autoCollapseSections([
                    ...prev.sections.map((s) => ({ ...s, isActive: false })),
                    createSection('search_complete', title, {
                      progressMessage: statusData.text,
                    }),
                  ]),
                }));
                return;

              case 'complete':
                // Complete research in message store - this changes researching to false
                completeResearch(responseId);
                setWaitingForContent(true);
                // Reset the completion shown ref when we get a new complete status
                researchCompletionShownRef.current = false;

                setState((prev) => ({
                  ...prev,
                  researchCompleted: true,
                  sections: autoCollapseSections([
                    ...prev.sections.map((s) => ({ ...s, isActive: false })),
                    createSection('finalizing', title, {
                      progressMessage: statusData.text,
                    }),
                  ]),
                }));
                return;

              case 'http_request':
                setState((prev) => ({
                  ...prev,
                  sections: autoCollapseSections([
                    ...prev.sections.map((s) => ({ ...s, isActive: false })),
                    createSection('progress', title, {
                      progressMessage: statusData.text,
                    }),
                  ]),
                }));
                return;

              default:
                // Handle any other phase as a progress section
                setState((prev) => ({
                  ...prev,
                  sections: autoCollapseSections([
                    ...prev.sections.map((s) => ({ ...s, isActive: false })),
                    createSection('progress', title, {
                      progressMessage: statusData.text,
                    }),
                  ]),
                }));
                return;
            }
          }

          // Legacy support for old search_start format
          if (statusData.type === 'search_start') {
            const searchQueries = {
              semantic: statusData.search_queries || [],
              keywords: statusData.keyword_queries || [],
              httpDomains: statusData.http_domains || [],
            };

            setState((prev) => ({
              ...prev,
              sections: autoCollapseSections([
                ...prev.sections.map((s) => ({ ...s, isActive: false })),
                createSection('searching', 'Searching Knowledge Base', {
                  searchQueries,
                }),
              ]),
            }));
            return;
          }
        }

        // Legacy support: Check for finished research phase
        if (
          event.status === 'finished' &&
          event.message?.includes('research')
        ) {
          setState((prev) => ({
            ...prev,
            researchCompleted: true,
            sections: autoCollapseSections([
              ...prev.sections.map((s) => ({ ...s, isActive: false })),
              createSection('finished', 'Research Complete'),
            ]),
          }));
          return;
        }

        // Fallback: Create a generic progress section for unrecognized status
        setState((prev) => ({
          ...prev,
          sections: autoCollapseSections([
            ...prev.sections.map((s) => ({ ...s, isActive: false })),
            createSection(
              'progress',
              `${event.status ? event.status.charAt(0).toUpperCase() + event.status.slice(1).toLowerCase() : 'Thinking...'}`,
              {
                progressMessage: event.message || event.status,
              },
            ),
          ]),
        }));
      },

      onContentEvent: (event: ContentEvent) => {
        console.debug('Raw ContentEvent received:', {
          eventResponseId: event.response_id,
          targetResponseId: responseId,
          matches: event.response_id === responseId,
          contentPreview: event.content?.substring(0, 50),
          timestamp: new Date().toISOString(),
        });

        if (event.response_id !== responseId) {
          console.debug('Ignoring ContentEvent for different responseId');
          return;
        }

        // Check if we're waiting for content after research completion
        // Only show completion message once using the ref
        if (
          (waitingForContent ||
            state.researchCompleted ||
            state.currentPhase === 'complete') &&
          !researchCompletionShownRef.current
        ) {
          console.log(
            'First content after research completion - transitioning to finished',
            {
              waitingForContent,
              researchCompleted: state.researchCompleted,
              currentPhase: state.currentPhase,
            },
          );

          // Set the ref to true to prevent showing completion message again
          researchCompletionShownRef.current = true;

          // Make sure we don't process this transition again
          setWaitingForContent(false);

          // Transform any finalizing section to finished section
          // or add a finished section if none exists
          setState((prev) => {
            // Check if we already have a finished section to prevent duplicates
            const hasFinishedSection = prev.sections.some(
              (s) => s.type === 'finished',
            );
            if (hasFinishedSection) {
              console.log('Finished section already exists, skipping creation');
              // Don't add another finished section if one already exists
              return prev;
            }

            console.log('Creating finished section');
            const hasFinalizingSection = prev.sections.some(
              (s) => s.type === 'finalizing',
            );

            if (hasFinalizingSection) {
              // Transform existing finalizing section
              return {
                ...prev,
                currentPhase: 'complete',
                sections: prev.sections.map((section) =>
                  section.type === 'finalizing'
                    ? {
                        ...section,
                        type: 'finished',
                        title: 'Research Completed',
                        isActive: false,
                      }
                    : section,
                ),
              };
            } else {
              // Add a new finished section if none exists
              return {
                ...prev,
                currentPhase: 'complete',
                sections: autoCollapseSections([
                  ...prev.sections.map((s) => ({ ...s, isActive: false })),
                  createSection('finished', 'Research Completed'),
                ]),
              };
            }
          });
          return;
        }

        // Check research state from message store to avoid stale closure
        const isStillResearching = isMessageResearching(responseId);
        const currentPhase = useMessageStore
          .getState()
          .getResearchPhase(responseId);

        // Only add content events that occur during research phase (before research completes)
        if (!isStillResearching || currentPhase === 'complete') {
          console.debug('Ignoring ContentEvent after research completed:', {
            isStillResearching,
            currentPhase,
          });
          return; // Don't add progress messages after research is complete
        }

        console.log(
          'Processing ContentEvent during research:',
          event.content?.substring(0, 100),
        );

        // Create or update the most recent progress section
        setState((prev) => {
          const lastSection = prev.sections[prev.sections.length - 1];
          const newContent = event.content || '';

          // If the last section is a progress section, update it
          if (
            lastSection &&
            lastSection.type === 'progress' &&
            lastSection.isActive
          ) {
            const updatedSections = [...prev.sections];
            updatedSections[updatedSections.length - 1] = {
              ...lastSection,
              data: {
                ...lastSection.data,
                progressMessage:
                  (lastSection.data.progressMessage || '') + newContent,
              },
            };
            return {
              ...prev,
              sections: updatedSections,
            };
          } else {
            // Create new progress section
            return {
              ...prev,
              sections: [
                ...prev.sections.map((s) => ({ ...s, isActive: false })), // Deactivate previous sections
                createSection('progress', 'Thinking', {
                  progressMessage: newContent,
                }),
              ],
            };
          }
        });
      },

      onDocumentEvent: (event: DocumentEvent) => {
        console.debug('Raw DocumentEvent received:', {
          eventResponseId: event.response_id,
          targetResponseId: responseId,
          matches: event.response_id === responseId,
          documentTitle: event.title,
          timestamp: new Date().toISOString(),
        });

        if (event.response_id !== responseId) {
          console.debug('Ignoring DocumentEvent for different responseId');
          return;
        }

        // Extract domain from document pointer if it's a URL
        let domain: string | undefined;
        try {
          if (event.pointer.startsWith('http')) {
            domain = new URL(event.pointer).hostname;
          }
        } catch (e) {
          // Ignore parsing errors
        }

        const document = {
          id: event.pointer,
          title: event.title || 'Unknown Document',
          domain,
        };

        // Find existing reading section or create new one
        setState((prev) => {
          const lastReadingSection = [...prev.sections]
            .reverse()
            .find((s) => s.type === 'reading');

          if (lastReadingSection && lastReadingSection.isActive) {
            // Update existing reading section
            const updatedSections = prev.sections.map((section) =>
              section.id === lastReadingSection.id
                ? {
                    ...section,
                    data: {
                      ...section.data,
                      documents: [
                        ...(section.data.documents || []).filter(
                          (d) => d.id !== document.id,
                        ),
                        document,
                      ],
                    },
                    title: `Reading sources · ${(section.data.documents || []).length + 1}`,
                  }
                : section,
            );
            return {
              ...prev,
              sections: updatedSections,
            };
          } else {
            // Create new reading section
            return {
              ...prev,
              sections: [
                ...prev.sections.map((s) => ({ ...s, isActive: false })),
                createSection('reading', 'Reading sources · 1', {
                  documents: [document],
                }),
              ],
            };
          }
        });
      },

      onResponseEndEvent: (event: ResponseEndEvent) => {
        console.log('Raw ResponseEndEvent received:', {
          eventResponseId: event.response_id,
          targetResponseId: responseId,
          matches: event.response_id === responseId,
          eventStatus: event.status,
          timestamp: new Date().toISOString(),
        });

        if (event.response_id !== responseId) {
          console.debug('Ignoring ResponseEndEvent for different responseId');
          return;
        }

        console.log(
          'Processing ResponseEndEvent - finishing panel for responseId:',
          responseId,
        );
        setResponseEnded(true);

        // Now that response has ended, trigger the onFinished callback
        setTimeout(() => {
          onFinished?.();
        }, 1000); // Brief delay to show completion state
      },
    };

    const unregister = registerWebSocketHandlers(ws, handlers);

    console.log(
      'Event handlers registered successfully for responseId:',
      responseId,
    );

    return () => {
      console.log('Unregistering event handlers for responseId:', responseId);
      registeredHandlersRegistry.delete(responseId);
      handlersRegisteredRef.current = false;
      researchCompletionShownRef.current = false; // Reset the ref when unmounting
      unregister();
    };
    // Optimize dependency array to prevent unnecessary effect re-runs
  }, [
    responseId, // This should be stable for the component's lifetime
    isHistorical, // This should be stable for the component's lifetime
    parseStatusMessage,
    onFinished,
    createSection,
    autoCollapseSections,
    updateResearchProgress,
    completeResearch,
    messages,
    isMessageResearching,
    state.researchCompleted,
    state.currentPhase,
    waitingForContent,
  ]);

  // Toggle section visibility
  const toggleSection = useCallback((sectionId: string) => {
    setState((prev) => ({
      ...prev,
      sections: prev.sections.map((section) =>
        section.id === sectionId
          ? { ...section, isOpen: !section.isOpen }
          : section,
      ),
    }));
  }, []);

  // Only render for the rag_oss task handler
  if (
    selectedTaskHandler !== 'rag_oss' ||
    !state.isVisible ||
    state.sections.length === 0
  )
    return null;

  // Helper to render section content based on type
  const renderSectionContent = (section: StatusSection) => {
    switch (section.type) {
      case 'planning':
        return (
          <div className="flex items-center space-x-2 text-xs">
            <span>{section.data.progressMessage}</span>
          </div>
        );

      case 'searching':
        const searchQueries = section.data.searchQueries;
        const hasSearchContent =
          searchQueries &&
          (searchQueries.semantic.length > 0 ||
            searchQueries.keywords.length > 0 ||
            searchQueries.httpDomains.length > 0);

        return hasSearchContent ? (
          <div className="space-y-3">
            {/* Semantic queries */}
            {[
              ...(searchQueries.semantic || []),
              ...(searchQueries.keywords || []),
            ].length > 0 && (
              <div>
                <div className="flex flex-wrap gap-1">
                  {[
                    ...(searchQueries.semantic || []),
                    ...(searchQueries.keywords || []),
                  ].map((query, index) => (
                    <SearchPill key={index}>{query}</SearchPill>
                  ))}
                </div>
              </div>
            )}

            {/* HTTP domains */}
            {searchQueries.httpDomains.length > 0 && (
              <div>
                <div className="text-xs font-medium mb-1">Web Sources:</div>
                <div className="flex flex-wrap gap-1">
                  {searchQueries.httpDomains.map((domain, index) => (
                    <SearchPill key={index}>{domain}</SearchPill>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-xs">Preparing search queries...</div>
        );

      case 'evaluating':
        return (
          <div className="space-y-2">
            <div className="flex items-center space-x-2 text-xs">
              <span className="">{section.data.progressMessage}</span>
            </div>
            {section.data.documentsFound && (
              <div className="text-xs text-gray-600">
                Found {section.data.documentsFound} documents
              </div>
            )}
          </div>
        );

      case 'search_complete':
        return (
          <div className="flex items-center space-x-2 text-xs">
            <span>{section.data.progressMessage}</span>
          </div>
        );

      case 'refining':
        return (
          <div className="flex items-center space-x-2 text-xs">
            <span>{section.data.progressMessage}</span>
          </div>
        );

      case 'progress':
        const progressMessage = section.data.progressMessage;
        return progressMessage ? (
          <div className="text-xs whitespace-pre-wrap">{progressMessage}</div>
        ) : (
          <div className="text-xs">Processing...</div>
        );

      case 'reading':
        const documents = section.data.documents || [];
        return documents.length > 0 ? (
          <div className="space-y-2">
            {documents.map((doc, index) => (
              <DocumentItem
                key={doc.id}
                title={doc.title}
                domain={doc.domain}
              />
            ))}
          </div>
        ) : (
          <div className="text-xs">Waiting for documents...</div>
        );

      case 'finalizing':
        return (
          <div className="flex items-center space-x-2 text-xs">
            <span>
              {section.data.progressMessage || 'Preparing final response...'}
            </span>
          </div>
        );

      case 'finished':
        return <div className="text-xs">Research completed</div>;

      default:
        return null;
    }
  };

  return (
    <div className={cn('flex items-start gap-4 py-2')}>
      <div className="md:w-[60%] mx-auto dark:border-stone-800 prose-stone dark:prose-invert rounded p-2 mb-4 space-y-3">
        {state.sections.map((section) =>
          section.type === 'finished' ? (
            <div key={section.id} className="border-l-2 border-green-500 pl-4">
              <div className="flex items-center space-x-2 text-sm font-medium text-green-700 mb-2">
                <div className="w-2 h-2 rounded-full bg-green-500" />
                <span>{section.title}</span>
              </div>
            </div>
          ) : (
            <CollapsibleSection
              key={section.id}
              title={section.title}
              isOpen={section.isOpen}
              onToggle={() => toggleSection(section.id)}
              isActive={section.isActive}
              type={section.type}
            >
              {renderSectionContent(section)}
            </CollapsibleSection>
          ),
        )}
      </div>
    </div>
  );
};
