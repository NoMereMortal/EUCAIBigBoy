// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Pencil, Upload } from 'lucide-react';
import { GuardrailDetail } from '@/lib/types';

interface GuardrailDetailViewProps {
  guardrail: GuardrailDetail;
  handleEdit: (guardrail: GuardrailDetail) => void;
  handlePublish: (guardrailId: string) => void;
  onBackClick: () => void;
}

export function GuardrailDetailView({
  guardrail,
  handleEdit,
  handlePublish,
  onBackClick,
}: GuardrailDetailViewProps) {
  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium flex items-center gap-2">
          <button
            onClick={onBackClick}
            className="text-muted-foreground hover:text-foreground"
          >
            &lt;
          </button>
          {guardrail.name}
        </h3>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleEdit(guardrail)}
          >
            <Pencil className=" mr-1" />
            Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handlePublish(guardrail.id)}
          >
            <Upload className=" mr-1" />
            Publish Version
          </Button>
        </div>
      </div>

      <div className="text-sm text-muted-foreground">
        {guardrail.description}
      </div>

      {/* Versions */}
      <div className="mt-2">
        <h4 className="font-medium mb-1">Versions</h4>
        <div className="text-sm">
          <p>Current version: {guardrail.current_version || 'Draft'}</p>
          {guardrail.versions.length > 0 ? (
            <div className="mt-1 grid gap-1">
              {guardrail.versions.map((version) => (
                <div key={version.version} className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">
                    {version.version}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {new Date(version.created_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              No published versions yet
            </p>
          )}
        </div>
      </div>

      {/* Content Filters */}
      {guardrail.content_filters.length > 0 && (
        <div className="mt-2">
          <h4 className="font-medium mb-1">Content Filters</h4>
          <div className="grid gap-2">
            {guardrail.content_filters.map((filter, index) => (
              <div key={index} className="text-sm border p-2 rounded">
                <div>
                  <strong>Type:</strong> {filter.type}
                </div>
                <div>
                  <strong>Input Strength:</strong> {filter.input_strength}
                </div>
                <div>
                  <strong>Output Strength:</strong> {filter.output_strength}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Word Filters */}
      {guardrail.word_filters.length > 0 && (
        <div className="mt-2">
          <h4 className="font-medium mb-1">Word Filters</h4>
          <div className="flex flex-wrap gap-1">
            {guardrail.word_filters.map((filter, index) => (
              <Badge key={index} variant="secondary" className="text-xs">
                {filter.text}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Denied Topics */}
      {guardrail.denied_topics.length > 0 && (
        <div className="mt-2">
          <h4 className="font-medium mb-1">Denied Topics</h4>
          <div className="grid gap-2">
            {guardrail.denied_topics.map((topic, index) => (
              <div key={index} className="text-sm border p-2 rounded">
                <div>
                  <strong>{topic.name}</strong>
                </div>
                <div className="text-xs mt-1">{topic.definition}</div>
                {topic.examples.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {topic.examples.map((example, i) => (
                      <Badge key={i} variant="outline" className="text-xs">
                        {example}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* PII Entities */}
      {guardrail.pii_entities.length > 0 && (
        <div className="mt-2">
          <h4 className="font-medium mb-1">PII Entities</h4>
          <div className="grid gap-2">
            {guardrail.pii_entities.map((entity, index) => (
              <div
                key={index}
                className="text-sm border p-2 rounded flex justify-between items-center"
              >
                <div>{entity.type}</div>
                <Badge variant="outline" className="text-xs">
                  {entity.action}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
