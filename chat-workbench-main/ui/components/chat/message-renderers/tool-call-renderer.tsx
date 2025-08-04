// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import React, { useState, useEffect, useRef } from 'react';
import { Markdown } from '@/components/ui/markdown';
import { MessageRendererProps } from '@/components/chat/message-renderers/index';

// Calculator content renderer - simplified with expression extraction
function CalculatorRenderer({
  toolArgs,
  content,
  isStreaming,
}: {
  toolArgs: any;
  content: string;
  contentBlockIndex?: number;
  blockSequence?: number;
  isStreaming?: boolean;
}) {
  // Extract delta text from toolArgs
  const deltaText = toolArgs?.delta || '';

  // Use ref for accumulation to avoid re-renders
  const accumulatedTextRef = useRef('');
  const [extractedExpression, setExtractedExpression] = useState('');

  // Process new delta fragments without causing infinite loop
  useEffect(() => {
    if (deltaText) {
      // Accumulate text without causing re-renders
      accumulatedTextRef.current += deltaText;

      try {
        // Only extract if we see valid expression pattern
        if (accumulatedTextRef.current.includes('"expression"')) {
          // Look for "expression": "..." pattern in the accumulated text
          // This regex handles both complete and incomplete expression values
          const expressionMatch =
            /\"expression\"\s*:\s*\"([^\"]*(?:\\\"[^\"]*)*)(?:\"|$)/g.exec(
              accumulatedTextRef.current,
            );
          if (expressionMatch && expressionMatch[1]) {
            // Unescape any escaped quotes in the extracted expression
            const unescapedExpression = expressionMatch[1].replace(/\\"/g, '"');
            setExtractedExpression(unescapedExpression);
          }
        }
      } catch (e) {
        // Silently handle errors during regex extraction
        console.debug('Error extracting expression from incomplete JSON:', e);
      }
    }
  }, [deltaText]);

  // Also check for direct expression in toolArgs for non-streaming cases
  useEffect(() => {
    if (toolArgs?.expression) {
      setExtractedExpression(toolArgs.expression);
    }
  }, [toolArgs?.expression]);

  return (
    <div className="text-gray-600 dark:text-gray-300 text-sm">
      {/* Expression display - simplified */}
      {extractedExpression && (
        <div className="prose-sm max-w-none dark:prose-invert">
          <Markdown content={content || ''} isStreaming={isStreaming} />
        </div>
      )}

      {/* Result with markdown support */}
      {content && (
        <div className="prose-sm max-w-none dark:prose-invert">
          <Markdown content={content || ''} isStreaming={isStreaming} />
        </div>
      )}
    </div>
  );
}

// Thinking content renderer - simplified with thought extraction
function ThinkingRenderer({
  toolArgs,
  content,
  isStreaming,
}: {
  toolArgs: any;
  content: string;
  contentBlockIndex?: number;
  blockSequence?: number;
  isStreaming?: boolean;
}) {
  // Extract delta text from toolArgs
  const deltaText = toolArgs?.delta || '';

  // Use ref for accumulation to avoid re-renders
  const accumulatedTextRef = useRef('');
  const [extractedThought, setExtractedThought] = useState('');

  // Process new delta fragments without causing infinite loop
  useEffect(() => {
    if (deltaText) {
      // Accumulate text without causing re-renders
      accumulatedTextRef.current += deltaText;

      // Try to extract thought value using regex
      // This handles partial JSON fragments as they stream in
      try {
        // Only extract if we see valid thought pattern
        if (accumulatedTextRef.current.includes('"thought"')) {
          // Look for "thought": "..." pattern in the accumulated text
          // This regex handles both complete and incomplete thought values
          const thoughtMatch =
            /\"thought\"\s*:\s*\"([^\"]*(?:\\\"[^\"]*)*)(?:\"|$)/g.exec(
              accumulatedTextRef.current,
            );
          if (thoughtMatch && thoughtMatch[1]) {
            // Unescape any escaped quotes in the extracted thought
            const unescapedThought = thoughtMatch[1].replace(/\\"/g, '"');
            setExtractedThought(unescapedThought);
          }
        }
      } catch (e) {
        // Silently handle errors during regex extraction
        console.debug('Error extracting thought from incomplete JSON:', e);
      }
    }
  }, [deltaText]);

  return (
    <div className="text-gray-600 dark:text-gray-300 text-sm">
      {extractedThought && <p className="pb-3">{extractedThought}</p>}

      {/* Keep main content for after thinking */}
      {content && (
        <div className="text-gray-600 dark:text-gray-300 text-sm">
          <Markdown content={content} isStreaming={isStreaming} />
        </div>
      )}
    </div>
  );
}

// Default tool renderer - simplified with JSON arguments extraction
function DefaultToolRenderer({
  toolName,
  toolArgs,
  content,
  isStreaming,
}: {
  toolName: string;
  toolArgs: any;
  content: string;
  contentBlockIndex?: number;
  blockSequence?: number;
  isStreaming?: boolean;
}) {
  const deltaText = toolArgs?.delta || '';

  // Use ref for accumulation to avoid re-renders
  const accumulatedTextRef = useRef('');
  const [parsedArgs, setParsedArgs] = useState<any>(null);

  // Process new delta fragments without causing infinite loop
  useEffect(() => {
    if (deltaText) {
      // Accumulate text without causing re-renders
      accumulatedTextRef.current += deltaText;

      try {
        // Try to parse the accumulated text as JSON
        // This will gracefully handle incomplete JSON
        const jsonStart = accumulatedTextRef.current.indexOf('{');
        if (jsonStart >= 0) {
          const jsonText = accumulatedTextRef.current.substring(jsonStart);
          // Only attempt to parse if we have something that looks like valid JSON
          if (jsonText.includes('}')) {
            const parsed = JSON.parse(jsonText);
            setParsedArgs(parsed);
          }
        }
      } catch (e) {
        // Silently handle parsing errors for partial JSON
        // This is expected during streaming
      }
    }
  }, [deltaText]);

  // Also use direct toolArgs if available and not streaming
  useEffect(() => {
    if (toolArgs && !toolArgs.delta && Object.keys(toolArgs).length > 0) {
      setParsedArgs(toolArgs);
    }
  }, [toolArgs]);

  // Determine if we have args to display
  const hasArgs = parsedArgs && Object.keys(parsedArgs).length > 0;

  return (
    <div className="text-gray-600 dark:text-gray-300 text-sm">
      {/* Arguments display - simplified */}
      {hasArgs && (
        <div className="font-mono text-xs pb-3">
          <pre className="whitespace-pre-wrap break-all">
            {JSON.stringify(parsedArgs, null, 2)}
          </pre>
        </div>
      )}

      {/* Main content with markdown support */}
      {content && (
        <div className="prose-sm max-w-none dark:prose-invert">
          <Markdown content={content || ''} isStreaming={isStreaming} />
        </div>
      )}
    </div>
  );
}

export function ToolCallMessageRenderer({
  content,
  eventData,
  isStreaming,
}: MessageRendererProps) {
  // Extract tool call info directly from eventData
  const toolName = eventData?.tool_name || 'Calling Tool';

  // Convert tool name to sentence case
  const formattedToolName = toolName
    .split('_')
    .map(
      (word: string) =>
        word.charAt(0).toUpperCase() + word.slice(1).toLowerCase(),
    )
    .join(' ');

  // Use tool args directly from eventData - simplifying delta handling
  const toolArgs = eventData?.tool_args || {};

  // Determine which renderer to use based on tool type
  const renderToolContent = () => {
    if (toolName === 'think') {
      return (
        <ThinkingRenderer
          toolArgs={toolArgs}
          content={content || ''}
          isStreaming={isStreaming}
        />
      );
    } else if (toolName === 'calculator') {
      return (
        <CalculatorRenderer
          toolArgs={toolArgs}
          content={content || ''}
          isStreaming={isStreaming}
        />
      );
    } else {
      // Default renderer for other tools
      return (
        <DefaultToolRenderer
          toolName={toolName}
          toolArgs={toolArgs}
          content={content || ''}
          isStreaming={isStreaming}
        />
      );
    }
  };

  // Render the tool call in a subtle box with header
  return (
    <div className="rounded-md bg-gray-50/80 dark:bg-gray-800/20 border border-gray-100 dark:border-gray-700/50 my-3">
      {/* Header with tool name */}
      <div className="border-b border-gray-100 dark:border-gray-700/30 px-3 py-1.5">
        <div className="flex items-center gap-2 text-gray-700 dark:text-gray-300">
          <span className="text-sm">{formattedToolName}</span>
        </div>
      </div>

      {/* Content area */}
      <div className="px-3 py-2">{renderToolContent()}</div>
    </div>
  );
}
