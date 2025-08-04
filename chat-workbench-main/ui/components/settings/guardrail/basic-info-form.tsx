// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { GuardrailCreate } from '@/lib/types';

interface BasicInfoFormProps {
  formData: GuardrailCreate;
  handleInputChange: (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => void;
}

export function BasicInfoForm({
  formData,
  handleInputChange,
}: BasicInfoFormProps) {
  return (
    <div className="grid gap-3">
      <div>
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          name="name"
          value={formData.name}
          onChange={handleInputChange}
          placeholder="Guardrail name"
          className="mt-1"
        />
      </div>

      <div>
        <Label htmlFor="description">Description</Label>
        <Textarea
          id="description"
          name="description"
          value={formData.description}
          onChange={handleInputChange}
          placeholder="Brief description"
          className="mt-1"
        />
      </div>

      <div>
        <Label htmlFor="blocked_input_messaging">Blocked Input Message</Label>
        <Input
          id="blocked_input_messaging"
          name="blocked_input_messaging"
          value={formData.blocked_input_messaging}
          onChange={handleInputChange}
          placeholder="Message to show when input is blocked"
          className="mt-1"
        />
      </div>

      <div>
        <Label htmlFor="blocked_output_messaging">Blocked Output Message</Label>
        <Input
          id="blocked_output_messaging"
          name="blocked_output_messaging"
          value={formData.blocked_output_messaging}
          onChange={handleInputChange}
          placeholder="Message to show when output is blocked"
          className="mt-1"
        />
      </div>
    </div>
  );
}
