// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, useEffect } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useStore } from '@/lib/store/index';
import { cn } from '@/lib/utils';
import { Model } from '@/lib/api/resources/model';
import { useModels } from '@/hooks/use-models';
import {
  useDefaultModel,
  getEffectiveModelId,
} from '@/hooks/use-default-model';
import { CirclePlus, Plus } from 'lucide-react';
import { ModelSelectionModal } from '@/components/chat/input/model-selection-modal';
import { Button } from '@/components/ui/button';

export function ModelSelector() {
  const { selectedModelId, setSelectedModel } = useStore();
  const { data: models = [], isLoading: loading } = useModels();
  const { defaultModel } = useDefaultModel();
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Get the effective model ID (selected or default)
  const effectiveModelId = getEffectiveModelId(
    selectedModelId || null,
    defaultModel,
  );
  const [displayedModelId, setDisplayedModelId] = useState<string | null>(null);

  // Update displayed model when effective model changes
  useEffect(() => {
    setDisplayedModelId(effectiveModelId);
  }, [effectiveModelId]);

  // Animation when effective model changes
  useEffect(() => {
    if (effectiveModelId && effectiveModelId !== displayedModelId) {
      setDisplayedModelId(effectiveModelId);
    }
  }, [effectiveModelId, displayedModelId]);

  // Get the current model for display
  const displayedModel = models.find((model) => model.id === displayedModelId);

  // Only show top 5 models in dropdown
  const topModels = [...models].sort((a, b) => a.order - b.order).slice(0, 5);

  // Check if we're using the default model (no explicit selection)
  const isUsingDefault = !selectedModelId && defaultModel;

  // Get shortened model name for compact display
  const getModelName = () => {
    if (!displayedModel) return 'Select model';
    const modelName = `${displayedModel.provider} ${displayedModel.name}`;
    return isUsingDefault ? `${modelName} (Default)` : modelName;
  };

  return (
    <div>
      <Select
        value={selectedModelId || undefined}
        onValueChange={(value) => {
          if (setSelectedModel) {
            setSelectedModel(value);
            // Immediately update the displayed model ID to show the change
            setDisplayedModelId(value);
          }
        }}
        disabled={loading || models.length === 0}
      >
        <SelectTrigger
          className={cn(
            'h-8 px-3 rounded-full bg-transparent border-0 shadow-none focus:ring-0 focus-visible:ring-0 focus-visible:outline-none cursor-pointer',
          )}
        >
          <div className="flex items-center gap-2 pr-1">
            <span className="text-sm opacity-80">
              {loading ? 'Loading...' : getModelName()}
            </span>
          </div>
        </SelectTrigger>
        <SelectContent className="animate-fade-in">
          {topModels.map((model) => (
            <SelectItem
              key={model.id}
              value={model.id}
              className="hover:bg-accent transition-colors cursor-pointer"
            >
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <span>
                    {model.provider} {model.name}
                  </span>
                </div>
              </div>
            </SelectItem>
          ))}

          <div className="border-t my-1 pt-1">
            <Button
              variant="ghost"
              className="w-full justify-start pl-2 font-normal h-8"
              onClick={(e) => {
                e.preventDefault();
                setIsModalOpen(true);
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              <span>More Models...</span>
            </Button>
          </div>
        </SelectContent>
      </Select>

      <ModelSelectionModal open={isModalOpen} onOpenChange={setIsModalOpen} />
    </div>
  );
}
