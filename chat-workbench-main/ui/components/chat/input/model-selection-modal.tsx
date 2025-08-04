// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, useEffect } from 'react';
import { MessagePart } from '@/lib/types';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Model } from '@/lib/api/resources/model';
import { useModels } from '@/hooks/use-models';
import { useStore } from '@/lib/store/index';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Search, SplitSquareVertical, Loader2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUserProfile } from '@/hooks/use-user-profile';

export function ModelSelectionModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { selectedModelId, setSelectedModel, selectedTaskHandler } = useStore();
  const [search, setSearch] = useState('');

  // Use React Query hook for models
  const {
    data: models = [],
    isLoading: loading,
    error: modelQueryError,
  } = useModels();

  // State for error handling
  const [error, setError] = useState<string | null>(null);

  // Update error state when query error changes
  useEffect(() => {
    if (modelQueryError) {
      setError('Failed to load model data');
    } else {
      setError(null);
    }
  }, [modelQueryError]);

  // Comparison mode states
  const [isCompareMode, setIsCompareMode] = useState(false);
  const [leftModelId, setLeftModelId] = useState<string | null>(
    selectedModelId || null,
  );
  const [rightModelId, setRightModelId] = useState<string | null>(null);
  const [comparisonPrompt, setComparisonPrompt] = useState('');
  const [isGeneratingComparison, setIsGeneratingComparison] = useState(false);

  // Response states
  const [leftModelResponse, setLeftModelResponse] = useState<string>('');
  const [rightModelResponse, setRightModelResponse] = useState<string>('');
  const [isGeneratingLeft, setIsGeneratingLeft] = useState(false);
  const [isGeneratingRight, setIsGeneratingRight] = useState(false);
  const [leftError, setLeftError] = useState<string | null>(null);
  const [rightError, setRightError] = useState<string | null>(null);

  // Metadata states
  const [leftMetadata, setLeftMetadata] = useState<{
    requestTokens?: number;
    responseTokens?: number;
    totalTokens?: number;
    startTime?: number;
    endTime?: number;
  } | null>(null);

  const [rightMetadata, setRightMetadata] = useState<{
    requestTokens?: number;
    responseTokens?: number;
    totalTokens?: number;
    startTime?: number;
    endTime?: number;
  } | null>(null);

  // Access user profile for chat creation
  const { userProfile } = useUserProfile();

  // No need for explicit fetch - React Query handles this automatically when component mounts

  // Filter models based on search term
  const filteredModels = search
    ? models.filter(
        (m) =>
          m.name.toLowerCase().includes(search.toLowerCase()) ||
          m.provider.toLowerCase().includes(search.toLowerCase()) ||
          m.description.toLowerCase().includes(search.toLowerCase()),
      )
    : models;

  // Reset comparison mode when modal closes
  useEffect(() => {
    if (!open) {
      setIsCompareMode(false);
      setComparisonPrompt('');
      setRightModelId(null);
      setLeftModelResponse('');
      setRightModelResponse('');
      setLeftError(null);
      setRightError(null);
    }
  }, [open]);

  // Handle model selection
  const handleModelSelect = (modelId: string) => {
    if (setSelectedModel) {
      setSelectedModel(modelId);
      onOpenChange(false);
    }
  };

  // Handle comparison generation
  const handleGenerateComparison = async () => {
    if (
      !leftModelId ||
      !rightModelId ||
      !comparisonPrompt.trim() ||
      !userProfile?.id
    ) {
      return;
    }

    // Reset previous responses
    setLeftModelResponse('');
    setRightModelResponse('');
    setLeftError(null);
    setRightError(null);
    setIsGeneratingComparison(true);
    setIsGeneratingLeft(true);
    setIsGeneratingRight(true);

    try {
      // Import needed functions from the API
      const { api } = await import('@/lib/api/index');

      // Get model names for chat titles
      const leftModel = models.find((m) => m.id === leftModelId);
      const rightModel = models.find((m) => m.id === rightModelId);
      const leftModelName = leftModel
        ? `${leftModel.provider} ${leftModel.name}`
        : 'Left Model';
      const rightModelName = rightModel
        ? `${rightModel.provider} ${rightModel.name}`
        : 'Right Model';

      // Create chats for each model
      const leftChatResponse = await api.createChat({
        title: `${leftModelName} Comparison`,
        user_id: userProfile.id,
      });
      const leftChatId = leftChatResponse.chat_id;

      const rightChatResponse = await api.createChat({
        title: `${rightModelName} Comparison`,
        user_id: userProfile.id,
      });
      const rightChatId = rightChatResponse.chat_id;

      // Reset metadata
      setLeftMetadata(null);
      setRightMetadata(null);

      const now = new Date().toISOString();

      // Generate with left and right models using non-streaming API - process independently
      const leftStartTime = Date.now();

      // Launch both requests
      const leftPromise = api
        .generateMessage({
          task: selectedTaskHandler || 'chat',
          chat_id: leftChatId,
          model_id: leftModelId,
          parts: [
            {
              part_kind: 'text',
              content: comparisonPrompt,
              timestamp: now,
            },
          ],
        })
        .then((result) => {
          // Process left model result as soon as it's available
          const leftEndTime = Date.now();
          const textParts =
            result.parts?.filter(
              (part: MessagePart) => part.part_kind === 'text',
            ) || [];
          const content = textParts
            .map((part: MessagePart) => part.content)
            .join('\n\n');
          console.log('Left model response content:', content);
          setLeftModelResponse(content);

          // Set metadata
          setLeftMetadata({
            requestTokens: result.usage?.request_tokens,
            responseTokens: result.usage?.response_tokens,
            totalTokens: result.usage?.total_tokens,
            startTime: leftStartTime,
            endTime: leftEndTime,
          });

          setIsGeneratingLeft(false);
        })
        .catch((error) => {
          setLeftError('Error generating response');
          console.error('Left model error:', error);
          setIsGeneratingLeft(false);
        });

      const rightStartTime = Date.now();

      const rightPromise = api
        .generateMessage({
          task: selectedTaskHandler || 'chat',
          chat_id: rightChatId,
          model_id: rightModelId,
          parts: [
            {
              part_kind: 'text',
              content: comparisonPrompt,
              timestamp: now,
            },
          ],
        })
        .then((result) => {
          // Process right model result as soon as it's available
          const rightEndTime = Date.now();
          const textParts =
            result.parts?.filter(
              (part: MessagePart) => part.part_kind === 'text',
            ) || [];
          const content = textParts
            .map((part: MessagePart) => part.content)
            .join('\n\n');
          console.log('Right model response content:', content);
          setRightModelResponse(content);

          // Set metadata
          setRightMetadata({
            requestTokens: result.usage?.request_tokens,
            responseTokens: result.usage?.response_tokens,
            totalTokens: result.usage?.total_tokens,
            startTime: rightStartTime,
            endTime: rightEndTime,
          });

          setIsGeneratingRight(false);
        })
        .catch((error) => {
          setRightError('Error generating response');
          console.error('Right model error:', error);
          setIsGeneratingRight(false);
        });

      // Wait for both to complete to mark comparison as complete
      Promise.allSettled([leftPromise, rightPromise]).finally(() =>
        setIsGeneratingComparison(false),
      );
    } catch (error) {
      console.error('Error generating comparison:', error);
      setLeftError('Failed to connect to message service');
      setRightError('Failed to connect to message service');
      setIsGeneratingComparison(false);
      setIsGeneratingLeft(false);
      setIsGeneratingRight(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={`${isCompareMode ? 'sm:max-w-[1100px]' : 'sm:max-w-[800px]'} sm:h-[80vh] max-h-[90vh] flex flex-col overflow-hidden`}
      >
        <DialogHeader className="flex flex-row items-center justify-between">
          <div>
            <DialogTitle>
              {isCompareMode ? 'Compare Models' : 'Select a Model'}
            </DialogTitle>
            <DialogDescription>
              {isCompareMode
                ? 'Select models to compare and enter a prompt'
                : 'Choose a model for your conversation'}
            </DialogDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="flex items-center gap-2 mr-8"
            onClick={() => setIsCompareMode(!isCompareMode)}
          >
            <SplitSquareVertical className="h-4 w-4" />
            {isCompareMode ? 'Back to Selection' : 'Compare Models'}
          </Button>
        </DialogHeader>

        {isCompareMode ? (
          // Comparison Mode UI
          <div className="flex flex-col gap-4 flex-1 overflow-hidden">
            <ScrollArea className="flex-1">
              <div className="pr-4 pb-4">
                <div className="grid grid-cols-2 gap-4">
                  {/* Left Side */}
                  <div className="flex flex-col gap-2 border p-4 rounded-lg">
                    <h3 className="text-sm font-medium mb-1">Model A</h3>
                    <Select
                      value={leftModelId || ''}
                      onValueChange={setLeftModelId}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a model" />
                      </SelectTrigger>
                      <SelectContent>
                        {models.map((model) => (
                          <SelectItem key={`left-${model.id}`} value={model.id}>
                            {model.provider} {model.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {leftModelId && (
                      <div className="text-xs text-muted-foreground mt-2">
                        {models.find((m) => m.id === leftModelId)?.description}
                      </div>
                    )}
                  </div>

                  {/* Right Side */}
                  <div className="flex flex-col gap-2 border p-4 rounded-lg">
                    <h3 className="text-sm font-medium mb-1">Model B</h3>
                    <Select
                      value={rightModelId || ''}
                      onValueChange={setRightModelId}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a model" />
                      </SelectTrigger>
                      <SelectContent>
                        {models.map((model) => (
                          <SelectItem
                            key={`right-${model.id}`}
                            value={model.id}
                          >
                            {model.provider} {model.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {rightModelId && (
                      <div className="text-xs text-muted-foreground mt-2">
                        {models.find((m) => m.id === rightModelId)?.description}
                      </div>
                    )}
                  </div>
                </div>

                {/* Prompt Input */}
                <div className="flex flex-col gap-2 mt-2">
                  <h3 className="text-sm font-medium">Prompt</h3>
                  <Textarea
                    placeholder="Enter your prompt here..."
                    className="min-h-[80px] resize-none"
                    value={comparisonPrompt}
                    onChange={(e) => setComparisonPrompt(e.target.value)}
                  />
                </div>

                {/* Generate Button */}
                <div className="flex justify-end mt-4">
                  <Button
                    onClick={handleGenerateComparison}
                    disabled={
                      !leftModelId ||
                      !rightModelId ||
                      !comparisonPrompt.trim() ||
                      isGeneratingComparison
                    }
                    className="min-w-[150px]"
                  >
                    {isGeneratingComparison ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      'Generate Comparison'
                    )}
                  </Button>
                </div>

                {/* Responses Section */}
                <div className="grid grid-cols-2 gap-4 mt-4">
                  {/* Left Model Response */}
                  <div className="flex flex-col border p-4 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-medium">
                        {models.find((m) => m.id === leftModelId)?.name ||
                          'Model A'}{' '}
                        Response
                      </h3>
                      {isGeneratingLeft && (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      )}
                    </div>
                    <div className="flex flex-col">
                      <div className="bg-muted/50 rounded-md p-3 h-[250px] overflow-y-auto">
                        {leftError ? (
                          <div className="text-destructive">{leftError}</div>
                        ) : leftModelResponse ? (
                          <div className="text-sm whitespace-pre-wrap">
                            {leftModelResponse}
                          </div>
                        ) : isGeneratingLeft ? (
                          <div className="text-sm text-muted-foreground">
                            Generating response...
                          </div>
                        ) : (
                          <div className="text-sm text-muted-foreground">
                            Response will appear here
                          </div>
                        )}
                      </div>

                      {/* Metadata display */}
                      {leftMetadata && (
                        <div className="mt-2 text-xs text-muted-foreground border-t pt-2">
                          <div>
                            Tokens: {leftMetadata.totalTokens || 'N/A'}{' '}
                            (Request: {leftMetadata.requestTokens || 'N/A'},
                            Response: {leftMetadata.responseTokens || 'N/A'})
                          </div>
                          <div>
                            Time:{' '}
                            {((leftMetadata.endTime || 0) -
                              (leftMetadata.startTime || 0)) /
                              1000}
                            s
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right Model Response */}
                  <div className="flex flex-col border p-4 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-medium">
                        {models.find((m) => m.id === rightModelId)?.name ||
                          'Model B'}{' '}
                        Response
                      </h3>
                      {isGeneratingRight && (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      )}
                    </div>
                    <div className="flex flex-col">
                      <div className="bg-muted/50 rounded-md p-3 h-[250px] overflow-y-auto">
                        {rightError ? (
                          <div className="text-destructive">{rightError}</div>
                        ) : rightModelResponse ? (
                          <div className="text-sm whitespace-pre-wrap">
                            {rightModelResponse}
                          </div>
                        ) : isGeneratingRight ? (
                          <div className="text-sm text-muted-foreground">
                            Generating response...
                          </div>
                        ) : (
                          <div className="text-sm text-muted-foreground">
                            Response will appear here
                          </div>
                        )}
                      </div>

                      {/* Metadata display */}
                      {rightMetadata && (
                        <div className="mt-2 text-xs text-muted-foreground border-t pt-2">
                          <div>
                            Tokens: {rightMetadata.totalTokens || 'N/A'}{' '}
                            (Request: {rightMetadata.requestTokens || 'N/A'},
                            Response: {rightMetadata.responseTokens || 'N/A'})
                          </div>
                          <div>
                            Time:{' '}
                            {((rightMetadata.endTime || 0) -
                              (rightMetadata.startTime || 0)) /
                              1000}
                            s
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </div>
        ) : (
          // Regular Selection Mode UI
          <>
            <div className="relative mb-4">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search models by name or provider..."
                className="pl-8"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            {loading ? (
              <div className="flex justify-center items-center py-8">
                <div className="animate-pulse">Loading models...</div>
              </div>
            ) : error ? (
              <div className="text-center py-8 text-destructive">{error}</div>
            ) : (
              <div className="flex-1 overflow-y-auto pr-4 max-h-[60vh]">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pb-4">
                  {filteredModels.map((model) => (
                    <div
                      key={model.id}
                      className={`border p-4 rounded-lg transition-all hover:border-primary cursor-pointer ${
                        selectedModelId === model.id
                          ? 'border-primary bg-muted/40'
                          : ''
                      }`}
                      onClick={() => handleModelSelect(model.id)}
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <div className="font-medium text-lg">
                            {model.name}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {model.provider}
                          </div>
                        </div>
                        <Badge>{model.provider}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground line-clamp-2">
                        {model.description}
                      </p>

                      {model.features.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {model.features.map((feature) => (
                            <Badge
                              key={feature.name}
                              variant="secondary"
                              className="text-xs"
                              title={feature.description}
                            >
                              {feature.name}
                            </Badge>
                          ))}
                        </div>
                      )}

                      <div className="mt-3 flex justify-end">
                        <a
                          href={model.provider_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-muted-foreground hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Provider Documentation
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
