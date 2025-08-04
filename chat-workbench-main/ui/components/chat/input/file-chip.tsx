// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { Button } from '@/components/ui/button';
import { FileText, Image as ImageIcon, X } from 'lucide-react';
import Image from 'next/image';
import { cn } from '@/lib/utils';

export interface FileDisplayInfo {
  filename: string;
  file_type: string;
  preview_url?: string;
  pointer?: string;
  mime_type?: string;
}

interface FileChipProps {
  file: FileDisplayInfo;
  onRemove?: () => void; // Made optional since view-only chips don't need removal
  onClick?: () => void; // Added onClick handler for opening file viewer
  disabled?: boolean;
  className?: string;
  viewOnly?: boolean; // Flag to indicate if this is a view-only chip
}

export function FileChip({
  file,
  onRemove,
  onClick,
  disabled = false,
  className,
  viewOnly = false,
}: FileChipProps) {
  return (
    <div
      className={cn(
        'relative group bg-muted rounded-md p-2 flex items-center space-x-2',
        onClick && 'cursor-pointer hover:bg-muted/80',
        onRemove && !viewOnly ? 'pr-8' : 'pr-3',
        className,
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {file.file_type === 'image' ? (
        <div className="w-8 h-8">
          {file.preview_url ? (
            <Image
              src={file.preview_url}
              alt={file.filename}
              width={32}
              height={32}
              className="w-full h-full object-cover rounded"
              unoptimized={
                file.preview_url.startsWith('data:') ||
                file.preview_url.startsWith('/api/')
              }
            />
          ) : (
            <ImageIcon className="w-full h-full text-muted-foreground" />
          )}
        </div>
      ) : (
        <FileText className="w-8 h-8 text-muted-foreground" />
      )}
      <span className="text-xs truncate max-w-[150px]">{file.filename}</span>
      {onRemove && !viewOnly && (
        <Button
          variant="ghost"
          size="icon"
          className="absolute top-1 right-1 h-5 w-5 rounded-full opacity-70 group-hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation(); // Prevent triggering onClick of parent
            onRemove();
          }}
          disabled={disabled}
        >
          <X className="h-3 w-3" />
          <span className="sr-only">Remove file</span>
        </Button>
      )}
    </div>
  );
}
