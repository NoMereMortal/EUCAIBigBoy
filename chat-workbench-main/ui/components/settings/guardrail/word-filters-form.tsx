// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Plus, X } from 'lucide-react';
import { GuardrailCreate } from '@/lib/types';

interface WordFiltersFormProps {
  formData: GuardrailCreate;
  handleAddWordFilter: () => void;
  handleWordFilterChange: (index: number, value: string) => void;
  handleRemoveWordFilter: (index: number) => void;
}

export function WordFiltersForm({
  formData,
  handleAddWordFilter,
  handleWordFilterChange,
  handleRemoveWordFilter,
}: WordFiltersFormProps) {
  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">Word Filters</h4>
        <Button size="sm" variant="outline" onClick={handleAddWordFilter}>
          <Plus className=" mr-1" />
          Add Word
        </Button>
      </div>

      {formData.word_filters.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No word filters configured.
        </p>
      ) : (
        <div className="grid gap-3">
          {formData.word_filters.map((filter, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                value={filter.text}
                onChange={(e) => handleWordFilterChange(index, e.target.value)}
                placeholder="Enter word or phrase to filter"
                className="grow"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleRemoveWordFilter(index)}
                className="icon-md p-0"
              >
                <X />
              </Button>
            </div>
          ))}
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        Word filters block specific words or phrases in both input and output.
      </p>
    </div>
  );
}
