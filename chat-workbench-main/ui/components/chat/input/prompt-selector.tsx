// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, useEffect } from 'react';
import { BookIcon } from 'lucide-react';
import { useStore } from '@/lib/store/index';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { PromptModal } from '@/components/chat/input/prompt-modal';

export function PromptSelector() {
  const { selectedPromptId } = useStore();
  const [isChanging, setIsChanging] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Animation when prompt changes
  useEffect(() => {
    if (selectedPromptId) {
      setIsChanging(true);
      const timer = setTimeout(() => setIsChanging(false), 500);
      return () => clearTimeout(timer);
    }
  }, [selectedPromptId]);

  return (
    <>
      <div
        className={cn(
          'transition-all duration-300',
          isChanging && 'animate-pulse',
        )}
      >
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'h-9 px-3 hover:scale-105 transition-all rounded-lg bg-background/80 backdrop-blur-xs border-primary/20 hover:border-primary/40',
            selectedPromptId && 'text-primary',
          )}
          onClick={() => setIsModalOpen(true)}
        >
          <BookIcon />
          <span className="sr-only">Select prompt template</span>
        </Button>
      </div>

      <PromptModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
}
