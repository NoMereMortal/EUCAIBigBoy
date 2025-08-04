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
import { TaskHandler } from '@/lib/api/resources/task-handler';
import { useTaskHandlers } from '@/hooks/use-task-handlers';
import { Bot, MessageSquare, Search } from 'lucide-react';

// Icons for different task handlers
const getTaskHandlerIcon = (name: string) => {
  switch (name) {
    case 'chat':
      return <MessageSquare className="h-4 w-4" />;
    case 'rag_oss':
      return <Search className="h-4 w-4" />;
    default:
      return <Bot className="h-4 w-4" />;
  }
};

// Display names for task handlers
const getTaskHandlerDisplayName = (name: string) => {
  switch (name) {
    case 'chat':
      return 'Chat';
    case 'rag_oss':
      return 'Document Search';
    default:
      return name.charAt(0).toUpperCase() + name.slice(1).replace('_', ' ');
  }
};

export function TaskHandlerSelector() {
  const { selectedTaskHandler, setSelectedTaskHandler } = useStore();
  const { data: taskHandlers = [], isLoading: loading } = useTaskHandlers();
  const [displayedTaskHandler, setDisplayedTaskHandler] =
    useState(selectedTaskHandler);

  // Initialize task handler if none is selected and we have handlers
  useEffect(() => {
    if (
      !selectedTaskHandler &&
      taskHandlers.length > 0 &&
      setSelectedTaskHandler
    ) {
      const defaultHandler =
        taskHandlers.find((h) => h.is_default) ||
        taskHandlers.find((h) => h.name === 'chat') ||
        taskHandlers[0];
      if (defaultHandler) {
        setSelectedTaskHandler(defaultHandler.name);
      }
    }
  }, [taskHandlers, selectedTaskHandler, setSelectedTaskHandler]);

  // Animation when task handler changes
  useEffect(() => {
    if (selectedTaskHandler && selectedTaskHandler !== displayedTaskHandler) {
      setDisplayedTaskHandler(selectedTaskHandler);
    }
  }, [selectedTaskHandler, displayedTaskHandler]);

  // Get the current task handler for display
  const displayedHandler = taskHandlers.find(
    (handler) => handler.name === displayedTaskHandler,
  );

  // Sort handlers to show chat first, then by default status
  const sortedHandlers = [...taskHandlers].sort((a, b) => {
    if (a.name === 'chat') return -1;
    if (b.name === 'chat') return 1;
    if (a.is_default && !b.is_default) return -1;
    if (b.is_default && !a.is_default) return 1;
    return a.name.localeCompare(b.name);
  });

  // Get shortened handler name for compact display
  const getHandlerName = () => {
    if (!displayedHandler) return 'Select handler';
    return getTaskHandlerDisplayName(displayedHandler.name);
  };

  return (
    <div>
      <Select
        value={selectedTaskHandler || undefined}
        onValueChange={(value) => {
          if (setSelectedTaskHandler) {
            setSelectedTaskHandler(value);
            // Immediately update the displayed task handler to show the change
            setDisplayedTaskHandler(value);
          }
        }}
        disabled={loading || taskHandlers.length === 0}
      >
        <SelectTrigger
          className={cn(
            'h-8 px-3 rounded-full bg-transparent border-0 shadow-none focus:ring-0 focus-visible:ring-0 focus-visible:outline-none cursor-pointer min-w-[120px]',
          )}
        >
          <div className="flex items-center gap-2 pr-1">
            {displayedHandler && getTaskHandlerIcon(displayedHandler.name)}
            <span className="text-sm opacity-80 truncate">
              {loading ? 'Loading...' : getHandlerName()}
            </span>
          </div>
        </SelectTrigger>
        <SelectContent className="animate-fade-in min-w-[200px]">
          {sortedHandlers.map((handler) => (
            <SelectItem
              key={handler.name}
              value={handler.name}
              className="hover:bg-accent transition-colors cursor-pointer py-3"
            >
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-3">
                  {getTaskHandlerIcon(handler.name)}
                  <div className="flex flex-col gap-1">
                    <span className="font-medium text-sm">
                      {getTaskHandlerDisplayName(handler.name)}
                    </span>
                    <span className="text-xs text-muted-foreground line-clamp-1 max-w-[160px]">
                      {handler.description}
                    </span>
                  </div>
                </div>
                {handler.is_default && (
                  <span className="text-xs bg-primary/10 text-primary px-1.5 py-0.5 rounded text-nowrap">
                    Default
                  </span>
                )}
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
