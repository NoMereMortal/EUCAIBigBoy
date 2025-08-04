// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Loader2, Search, X } from 'lucide-react';
import { useStore } from '@/lib/store/index';
import { Prompt, ListPromptsResponse } from '@/lib/types';
import { cn } from '@/lib/utils';

interface PromptModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function PromptModal({ isOpen, onClose }: PromptModalProps) {
  const { fetchPrompts, searchPrompts, setSelectedPrompt } = useStore();
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [lastKey, setLastKey] = useState<any>(null);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(1);

  // Define loadPrompts and handleSearch with useCallback to use them in useEffect dependencies
  const loadPrompts = useCallback(async () => {
    if (!fetchPrompts) {
      console.error('fetchPrompts is undefined');
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetchPrompts(12);
      setPrompts(response.prompts);
      setLastKey(response.last_evaluated_key);
      setHasMore(!!response.last_evaluated_key);
    } catch (error) {
      console.error('Failed to load prompts:', error);
    } finally {
      setIsLoading(false);
    }
  }, [fetchPrompts]);

  const handleSearch = useCallback(async () => {
    if (!searchPrompts) {
      console.error('searchPrompts is undefined');
      return;
    }

    setIsLoading(true);
    try {
      const response = await searchPrompts(searchQuery, 12);
      setPrompts(response.prompts);
      setLastKey(response.last_evaluated_key);
      setHasMore(!!response.last_evaluated_key);
      setPage(1);
    } catch (error) {
      console.error('Failed to search prompts:', error);
    } finally {
      setIsLoading(false);
    }
  }, [searchPrompts, searchQuery]);

  const loadMorePrompts = useCallback(async () => {
    if (!lastKey || isLoading) return;
    if (!fetchPrompts || !searchPrompts) {
      console.error('fetchPrompts or searchPrompts is undefined');
      return;
    }

    setIsLoading(true);
    try {
      const response = searchQuery
        ? await searchPrompts(searchQuery, 12, lastKey)
        : await fetchPrompts(12, lastKey);

      setPrompts((prev) => [...prev, ...response.prompts]);
      setLastKey(response.last_evaluated_key);
      setHasMore(!!response.last_evaluated_key);
      setPage((prev) => prev + 1);
    } catch (error) {
      console.error('Failed to load more prompts:', error);
    } finally {
      setIsLoading(false);
    }
  }, [fetchPrompts, searchPrompts, isLoading, lastKey, searchQuery]);

  // Load prompts when modal opens
  useEffect(() => {
    if (isOpen) {
      loadPrompts();
    } else {
      // Reset state when modal closes
      setSearchQuery('');
      setPrompts([]);
      setLastKey(null);
      setHasMore(false);
      setPage(1);
    }
  }, [isOpen, loadPrompts]);

  // Handle search input changes
  useEffect(() => {
    const timer = setTimeout(() => {
      if (isOpen) {
        if (searchQuery) {
          handleSearch();
        } else {
          loadPrompts();
        }
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery, isOpen, handleSearch, loadPrompts]);

  const handleSelectPrompt = async (prompt: Prompt) => {
    if (setSelectedPrompt) await setSelectedPrompt(prompt.prompt_id);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Select Prompt Template</DialogTitle>
        </DialogHeader>

        {/* Category and tag filters would go here */}

        {isLoading && prompts.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="icon-md animate-spin text-primary" />
          </div>
        ) : prompts.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            {searchQuery
              ? 'No prompts found matching your search'
              : 'No prompt templates available'}
          </div>
        ) : (
          <>
            <ScrollArea className="flex-1 pr-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pb-4">
                {prompts.map((prompt) => (
                  <div
                    key={prompt.prompt_id}
                    className="border rounded-lg p-4 hover:border-primary cursor-pointer transition-all hover:shadow-md"
                    onClick={() => handleSelectPrompt(prompt)}
                  >
                    <h3 className="font-medium mb-1">{prompt.name}</h3>
                    <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                      {prompt.description}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {prompt.tags?.map((tag) => (
                        <span
                          key={tag}
                          className="bg-secondary text-secondary-foreground text-xs px-2 py-0.5 rounded-full"
                        >
                          {tag}
                        </span>
                      ))}
                      <span className="bg-primary/10 text-primary text-xs px-2 py-0.5 rounded-full">
                        {prompt.category}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>

            {/* Search bar beneath the tags */}
            <div className="relative mt-4 mb-2">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search prompt templates..."
                className="pl-10 pr-10"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute right-2 top-1/2 transform -translate-y-1/2 h-6 w-6"
                  onClick={() => setSearchQuery('')}
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </div>

            {hasMore && (
              <div className="flex justify-center mt-4">
                <Button
                  variant="outline"
                  onClick={loadMorePrompts}
                  disabled={isLoading}
                  className="w-full"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    `Load More (Page ${page})`
                  )}
                </Button>
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
