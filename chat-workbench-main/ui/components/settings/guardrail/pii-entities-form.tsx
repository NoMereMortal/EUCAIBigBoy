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
  GuardrailPiiEntity,
  PiiEntityType,
  PiiAction,
} from '@/lib/types';

interface PiiEntitiesFormProps {
  formData: GuardrailCreate;
  handleAddPiiEntity: () => void;
  handlePiiEntityChange: (
    index: number,
    field: keyof GuardrailPiiEntity,
    value: any,
  ) => void;
  handleRemovePiiEntity: (index: number) => void;
}

export function PiiEntitiesForm({
  formData,
  handleAddPiiEntity,
  handlePiiEntityChange,
  handleRemovePiiEntity,
}: PiiEntitiesFormProps) {
  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">PII Entities</h4>
        <Button size="sm" variant="outline" onClick={handleAddPiiEntity}>
          <Plus className=" mr-1" />
          Add Entity
        </Button>
      </div>

      {formData.pii_entities.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No PII entities configured.
        </p>
      ) : (
        <div className="grid gap-3">
          {formData.pii_entities.map((entity, index) => (
            <div key={index} className="border rounded-md p-3 bg-card">
              <div className="flex justify-between items-start mb-2">
                <h5 className="font-medium">Entity {index + 1}</h5>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRemovePiiEntity(index)}
                  className="h-6 w-6 p-0"
                >
                  <X />
                </Button>
              </div>

              <div className="grid gap-2">
                <div>
                  <Label htmlFor={`pii-type-${index}`}>Type</Label>
                  <Select
                    value={entity.type}
                    onValueChange={(value) =>
                      handlePiiEntityChange(
                        index,
                        'type',
                        value as PiiEntityType,
                      )
                    }
                  >
                    <SelectTrigger id={`pii-type-${index}`} className="mt-1">
                      <SelectValue placeholder="Select entity type" />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.values(PiiEntityType).map((type) => (
                        <SelectItem key={type} value={type}>
                          {type}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor={`pii-action-${index}`}>Action</Label>
                  <Select
                    value={entity.action}
                    onValueChange={(value) =>
                      handlePiiEntityChange(index, 'action', value as PiiAction)
                    }
                  >
                    <SelectTrigger id={`pii-action-${index}`} className="mt-1">
                      <SelectValue placeholder="Select action" />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.values(PiiAction).map((action) => (
                        <SelectItem key={action} value={action}>
                          {action}
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
      <p className="text-xs text-muted-foreground">
        Configure how to handle personally identifiable information (PII) in
        both input and output.
      </p>
    </div>
  );
}
