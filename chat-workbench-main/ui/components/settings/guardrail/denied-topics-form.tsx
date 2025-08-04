// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Plus, X } from 'lucide-react';
import { GuardrailCreate, GuardrailDeniedTopic } from '@/lib/types';

interface DeniedTopicsFormProps {
  formData: GuardrailCreate;
  handleAddDeniedTopic: () => void;
  handleDeniedTopicChange: (
    index: number,
    field: keyof GuardrailDeniedTopic,
    value: any,
  ) => void;
  handleExamplesChange: (index: number, value: string) => void;
  handleRemoveDeniedTopic: (index: number) => void;
}

export function DeniedTopicsForm({
  formData,
  handleAddDeniedTopic,
  handleDeniedTopicChange,
  handleExamplesChange,
  handleRemoveDeniedTopic,
}: DeniedTopicsFormProps) {
  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">Denied Topics</h4>
        <Button size="sm" variant="outline" onClick={handleAddDeniedTopic}>
          <Plus className=" mr-1" />
          Add Topic
        </Button>
      </div>

      {formData.denied_topics.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No denied topics configured.
        </p>
      ) : (
        <div className="grid gap-4">
          {formData.denied_topics.map((topic, index) => (
            <div key={index} className="border rounded-md p-3 bg-card">
              <div className="flex justify-between items-start mb-2">
                <h5 className="font-medium">Topic {index + 1}</h5>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRemoveDeniedTopic(index)}
                  className="h-6 w-6 p-0"
                >
                  <X />
                </Button>
              </div>

              <div className="grid gap-2">
                <div>
                  <Label htmlFor={`topic-name-${index}`}>Name</Label>
                  <Input
                    id={`topic-name-${index}`}
                    value={topic.name}
                    onChange={(e) =>
                      handleDeniedTopicChange(index, 'name', e.target.value)
                    }
                    placeholder="Topic name"
                    className="mt-1"
                  />
                </div>

                <div>
                  <Label htmlFor={`topic-def-${index}`}>Definition</Label>
                  <Textarea
                    id={`topic-def-${index}`}
                    value={topic.definition}
                    onChange={(e) =>
                      handleDeniedTopicChange(
                        index,
                        'definition',
                        e.target.value,
                      )
                    }
                    placeholder="Describe the topic to be denied"
                    className="mt-1"
                  />
                </div>

                <div>
                  <Label htmlFor={`topic-examples-${index}`}>
                    Examples (comma-separated)
                  </Label>
                  <Input
                    id={`topic-examples-${index}`}
                    value={topic.examples.join(', ')}
                    onChange={(e) =>
                      handleExamplesChange(index, e.target.value)
                    }
                    placeholder="example1, example2, example3"
                    className="mt-1"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
