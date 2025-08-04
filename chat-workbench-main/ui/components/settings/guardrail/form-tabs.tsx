// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

interface FormTabsProps {
  formMode: 'basic' | 'content' | 'wordFilters' | 'deniedTopics' | 'pii';
  setFormMode: (
    mode: 'basic' | 'content' | 'wordFilters' | 'deniedTopics' | 'pii',
  ) => void;
}

export function FormTabs({ formMode, setFormMode }: FormTabsProps) {
  return (
    <div className="mb-4 border-b">
      <div className="flex space-x-4">
        <button
          onClick={() => setFormMode('basic')}
          className={`pb-2 px-1 ${formMode === 'basic' ? 'border-b-2 border-primary font-medium' : 'text-muted-foreground'}`}
        >
          Basic Info
        </button>
        <button
          onClick={() => setFormMode('content')}
          className={`pb-2 px-1 ${formMode === 'content' ? 'border-b-2 border-primary font-medium' : 'text-muted-foreground'}`}
        >
          Content Filters
        </button>
        <button
          onClick={() => setFormMode('wordFilters')}
          className={`pb-2 px-1 ${formMode === 'wordFilters' ? 'border-b-2 border-primary font-medium' : 'text-muted-foreground'}`}
        >
          Word Filters
        </button>
        <button
          onClick={() => setFormMode('deniedTopics')}
          className={`pb-2 px-1 ${formMode === 'deniedTopics' ? 'border-b-2 border-primary font-medium' : 'text-muted-foreground'}`}
        >
          Denied Topics
        </button>
        <button
          onClick={() => setFormMode('pii')}
          className={`pb-2 px-1 ${formMode === 'pii' ? 'border-b-2 border-primary font-medium' : 'text-muted-foreground'}`}
        >
          PII Entities
        </button>
      </div>
    </div>
  );
}
