// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Plus, X } from 'lucide-react';
import {
  GuardrailCreate,
  GuardrailContentFilter,
  ContentFilterType,
  FilterStrength,
} from '@/lib/types';

interface ContentFiltersFormProps {
  formData: GuardrailCreate;
  handleAddContentFilter: () => void;
  handleContentFilterChange: (
    index: number,
    field: keyof GuardrailContentFilter,
    value: any,
  ) => void;
  handleRemoveContentFilter: (index: number) => void;
}

export function ContentFiltersForm({
  formData,
  handleAddContentFilter,
  handleContentFilterChange,
  handleRemoveContentFilter,
}: ContentFiltersFormProps) {
  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">Content Filters</h4>
        <Button size="sm" variant="outline" onClick={handleAddContentFilter}>
          <Plus className=" mr-1" />
          Add Filter
        </Button>
      </div>

      {formData.content_filters.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No content filters configured.
        </p>
      ) : (
        <div className="grid gap-3">
          {formData.content_filters.map((filter, index) => (
            <div key={index} className="border rounded-md p-3 bg-card">
              <div className="flex justify-between items-start mb-2">
                <h5 className="font-medium">Filter {index + 1}</h5>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRemoveContentFilter(index)}
                  className="h-6 w-6 p-0"
                >
                  <X />
                </Button>
              </div>

              <div className="grid gap-2">
                <div>
                  <Label htmlFor={`filter-type-${index}`}>Type</Label>
                  <Select
                    value={filter.type}
                    onValueChange={(value) =>
                      handleContentFilterChange(index, 'type', value)
                    }
                  >
                    <SelectTrigger id={`filter-type-${index}`} className="mt-1">
                      <SelectValue placeholder="Select filter type" />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.values(ContentFilterType).map((type) => (
                        <SelectItem key={type} value={type}>
                          {type}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor={`filter-input-${index}`}>
                    Input Strength
                  </Label>
                  <Select
                    value={filter.input_strength}
                    onValueChange={(value) =>
                      handleContentFilterChange(index, 'input_strength', value)
                    }
                  >
                    <SelectTrigger
                      id={`filter-input-${index}`}
                      className="mt-1"
                    >
                      <SelectValue placeholder="Select input strength" />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.values(FilterStrength).map((strength) => (
                        <SelectItem key={strength} value={strength}>
                          {strength}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor={`filter-output-${index}`}>
                    Output Strength
                  </Label>
                  <Select
                    value={filter.output_strength}
                    onValueChange={(value) =>
                      handleContentFilterChange(index, 'output_strength', value)
                    }
                  >
                    <SelectTrigger
                      id={`filter-output-${index}`}
                      className="mt-1"
                    >
                      <SelectValue placeholder="Select output strength" />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.values(FilterStrength).map((strength) => (
                        <SelectItem key={strength} value={strength}>
                          {strength}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
