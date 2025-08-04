// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState } from 'react';
import { Search } from 'lucide-react';
import { Button } from './button';
import { Input } from './input';
import { cn } from '@/lib/utils';

interface SearchInputProps {
  placeholder?: string;
  onSearch?: (query: string) => void;
  className?: string;
}

export function SearchInput({
  placeholder = 'Search...',
  onSearch,
  className,
}: SearchInputProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value);
    onSearch?.(value);
  };

  const handleBlur = () => {
    if (searchQuery.trim() === '') {
      setIsExpanded(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setIsExpanded(false);
      setSearchQuery(''); // Clear the search query when escaping
      e.currentTarget.blur(); // Remove focus from the input
    }
  };

  const toggleSearch = () => {
    setIsExpanded(!isExpanded);
    if (!isExpanded) {
      // Focus will be set by autoFocus when expanded
      setTimeout(() => {
        const input = document.querySelector(
          '.search-input-field',
        ) as HTMLInputElement;
        input?.focus();
      }, 100);
    }
  };

  return (
    <div
      className={cn(
        'flex items-center transition-all duration-[400ms] ease-in-out',
        className,
      )}
    >
      {/* Flexible space that collapses when search is expanded */}
      <div
        className={cn(
          'transition-all duration-500 ease-out',
          isExpanded ? 'w-0' : 'flex-1',
        )}
      ></div>

      {/* Search icon - always visible */}
      <Button
        size="icon"
        variant="ghost"
        onClick={toggleSearch}
        className="icon-md flex-shrink-0 rounded-lg hover:bg-primary/10 z-10"
        aria-label="Search"
      >
        <Search />
      </Button>

      {/* Search input that expands when search is clicked */}
      <div
        className={cn(
          'overflow-hidden transition-all duration-500 ease-out ml-2',
          isExpanded
            ? 'flex-1 opacity-100'
            : 'w-0 opacity-0 pointer-events-none',
        )}
      >
        <Input
          placeholder={placeholder}
          className={cn(
            'h-8 w-full focus:ring-0 focus-visible:ring-0 search-input-field',
            'transition-all duration-500 ease-out',
          )}
          value={searchQuery}
          onChange={handleSearch}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          autoFocus={isExpanded}
          disabled={!isExpanded}
        />
      </div>
    </div>
  );
}
