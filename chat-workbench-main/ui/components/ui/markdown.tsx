// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import React, { useState, useEffect } from 'react';
import { CheckCircle2, Clipboard } from 'lucide-react';
import styles from './markdown.module.css';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import {
  vscDarkPlus,
  oneLight,
} from 'react-syntax-highlighter/dist/cjs/styles/prism';
import { useTheme } from 'next-themes';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import remarkDirective from 'remark-directive';
import rehypeKatex from 'rehype-katex';

interface MarkdownProps {
  content: string;
  isStreaming?: boolean;
}

const arePropsEqual = (prevProps: MarkdownProps, nextProps: MarkdownProps) => {
  // Only skip render if nothing changed
  if (
    prevProps.content === nextProps.content &&
    prevProps.isStreaming === nextProps.isStreaming
  )
    return true;

  // If we're actively streaming, render more frequently
  if (nextProps.isStreaming) {
    // During streaming, check if content has grown
    if (nextProps.content.startsWith(prevProps.content)) {
      const newChars = nextProps.content.length - prevProps.content.length;

      // Only apply minimal optimization during streaming:
      // Re-render at least every ~20 characters
      if (newChars > 0 && newChars % 20 === 0) return false;

      // Re-render on important semantic breaks regardless of character count
      const lastChar = nextProps.content[nextProps.content.length - 1];
      const lastFewChars = nextProps.content.slice(-5);

      const isSemanticBreak =
        ['.', '!', '?'].includes(lastChar) || // End of sentence
        lastChar === '\n' || // New line
        /\n\s*\n$/.test(lastFewChars) || // Paragraph break
        /`{3}/.test(lastFewChars); // Code block boundary

      if (isSemanticBreak) return false;
    }
  }

  // For non-streaming content or any other case, default to rendering
  // This ensures changes are always reflected
  return false;
};

// CodeBlock component with copy functionality and line number toggle
const CodeBlock = ({
  language,
  children,
  className,
  ...props
}: {
  language: string;
  children: React.ReactNode;
  className?: string;
  [key: string]: any;
}) => {
  const [copied, setCopied] = useState(false);
  const { theme } = useTheme();
  const [currentTheme, setCurrentTheme] = useState(theme);

  // Update the theme when it changes
  useEffect(() => {
    setCurrentTheme(theme);
  }, [theme]);

  const syntaxStyle = currentTheme === 'dark' ? vscDarkPlus : oneLight;

  // Convert children to string safely
  const codeString = React.useMemo(() => {
    if (typeof children === 'string') return children;
    if (Array.isArray(children)) return children.join('');
    return String(children || '');
  }, [children]);

  // Function to copy code to clipboard
  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(codeString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code', err);
    }
  };

  return (
    <div className={styles.container}>
      {/* Header bar with language name and controls */}
      <div className={styles.header}>
        <div className={styles.languageLabel}>{language || 'text'}</div>

        <div className={styles.controlsContainer}>
          <button
            onClick={copyToClipboard}
            className={styles.button}
            aria-label="Copy code"
          >
            {copied ? (
              <CheckCircle2 className="icon-xxs text-green-500" />
            ) : (
              <Clipboard className="icon-xxs" />
            )}
            <span>{copied ? 'Copied!' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {/* Syntax highlighter with explicit styling */}
      <div className={styles.highlighterContainer}>
        <SyntaxHighlighter
          style={syntaxStyle}
          language={language || 'text'} // Fallback to text if language is not specified
          PreTag="div"
          showLineNumbers={false}
          lineNumberStyle={{
            color: 'var(--tw-prose-bullets, rgb(106, 153, 85))',
            userSelect: 'none',
            paddingRight: '1em',
          }}
          wrapLines={true}
          customStyle={{
            backgroundColor: 'transparent',
            margin: 0,
            padding: '0.6666667em 1em',
          }}
          codeTagProps={{
            className: styles.code,
          }}
          className={`${className || ''} ${styles.syntaxHighlighter}`}
          {...props}
        >
          {codeString}
        </SyntaxHighlighter>
      </div>
    </div>
  );
};

// Use React.memo with enhanced comparison to prevent unnecessary rerenders
export const Markdown = React.memo(
  ({ content, isStreaming }: MarkdownProps) => {
    return (
      <ReactMarkdown
        unwrapDisallowed={true}
        remarkPlugins={[remarkGfm, remarkMath, remarkDirective]}
        rehypePlugins={[rehypeKatex]}
        components={{
          code({ inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');

            // Convert children to string safely
            const codeString =
              typeof children === 'string'
                ? children
                : Array.isArray(children)
                  ? children.join('')
                  : String(children || '');

            // Detect if inline code has newlines (but don't change its rendering approach)
            const hasNewlines = inline && codeString.includes('\n');

            // Even if ReactMarkdown thinks it's not inline, we check if it really looks like
            // an inline reference (short, single line text that might be misclassified)
            const trimmedCode = codeString.trim();
            const isActuallyInlineReference =
              !inline &&
              trimmedCode.length < 30 && // Short content
              !trimmedCode.includes('\n') && // No newlines
              !trimmedCode.startsWith('```') && // Not starting with triple backticks
              !match; // No language specified (important!)

            // Use the inline code style for both actual inline code AND things that look like inline references
            if (!inline && !isActuallyInlineReference) {
              // This is a genuine code block, not an inline reference
              return (
                <CodeBlock
                  language={match ? match[1] : 'text'} // Default to 'text' if no language specified
                  className={className}
                  {...props}
                >
                  {children}
                </CodeBlock>
              );
            } else {
              // This is inline code - use the appropriate styling
              // Apply special class for inline code with newlines
              return (
                <code
                  className={`${className || ''} ${styles.inlineCode} ${hasNewlines ? styles.inlineMultiline : ''}`}
                  {...props}
                >
                  {children}
                </code>
              );
            }
          },
          p({ children }) {
            return <div className="mb-4 last:mb-0">{children}</div>;
          },
          ul({ children }) {
            return <ul className="list-disc pl-6 mb-4">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="list-decimal pl-6 mb-4">{children}</ol>;
          },
          li({ children }) {
            return <li className="mb-1">{children}</li>;
          },
          h1({ children }) {
            return <h1 className="text-2xl font-bold mb-4 mt-6">{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="text-xl font-bold mb-3 mt-5">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="text-lg font-bold mb-2 mt-4">{children}</h3>;
          },
          blockquote({ children }) {
            return (
              <blockquote className="border-l-4 border-gray-300 dark:border-gray-700 pl-4 italic my-4">
                {children}
              </blockquote>
            );
          },
          table({ children }) {
            return (
              <div className="overflow-x-auto mb-4">
                <table className="min-w-full divide-y divide-gray-300 dark:divide-gray-700">
                  {children}
                </table>
              </div>
            );
          },
          thead({ children }) {
            return (
              <thead className="bg-gray-100 dark:bg-gray-800">{children}</thead>
            );
          },
          tbody({ children }) {
            return (
              <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                {children}
              </tbody>
            );
          },
          tr({ children }) {
            return <tr>{children}</tr>;
          },
          th({ children }) {
            return (
              <th className="px-3 py-2 text-left text-sm font-semibold">
                {children}
              </th>
            );
          },
          td({ children }) {
            return <td className="px-3 py-2 text-sm">{children}</td>;
          },
          a({ href, children, ...props }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                {...props}
              >
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    );
  },
  arePropsEqual,
);

// Add display name to the component
Markdown.displayName = 'Markdown';
