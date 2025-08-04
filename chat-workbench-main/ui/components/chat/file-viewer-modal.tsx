// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState } from 'react';
import Image from 'next/image';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  DownloadCloud,
  Maximize,
  Minimize,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';

// Utility function to check if a file is a text type
function isTextFile(mimeType: string): boolean {
  // Text file types that can be displayed directly
  return (
    mimeType.startsWith('text/') ||
    [
      'application/json',
      'application/javascript',
      'application/typescript',
      'application/xml',
    ].includes(mimeType)
  );
}

// Utility function to check if a file is code
function isCodeFile(mimeType: string, filename: string): boolean {
  // Code file types
  if (
    mimeType.includes('javascript') ||
    mimeType.includes('typescript') ||
    mimeType.includes('python') ||
    mimeType.includes('java') ||
    mimeType.includes('c++') ||
    mimeType.includes('csharp')
  ) {
    return true;
  }

  // Check extensions for common code files
  const codeExtensions = [
    '.js',
    '.ts',
    '.jsx',
    '.tsx',
    '.py',
    '.java',
    '.cpp',
    '.c',
    '.cs',
    '.php',
    '.rb',
    '.go',
    '.swift',
    '.kt',
    '.rs',
  ];

  return codeExtensions.some((ext) => filename.toLowerCase().endsWith(ext));
}

export interface FileViewerProps {
  isOpen: boolean;
  onClose: () => void;
  file: {
    pointer: string;
    mime_type: string;
    filename: string;
    file_type: string;
    preview_url?: string;
  } | null;
}

export function FileViewerModal({ isOpen, onClose, file }: FileViewerProps) {
  const [zoom, setZoom] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);

  if (!file) return null;

  // Get content URL
  const contentUrl =
    file.preview_url ||
    `/api/v1/generate/content/${encodeURIComponent(file.pointer.replace('file://', ''))}`;

  const toggleFullscreen = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen();
      setIsFullscreen(false);
    } else {
      document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    }
  };

  const handleDownload = async () => {
    try {
      const response = await fetch(contentUrl);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      // Create a download link and click it
      const a = document.createElement('a');
      a.href = url;
      a.download = file.filename;
      document.body.appendChild(a);
      a.click();

      // Clean up
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  // Render content based on file type
  const renderContent = () => {
    if (file.mime_type.startsWith('image/')) {
      return (
        <div className="flex flex-col items-center">
          <div className="flex items-center gap-2 mb-4">
            <Button
              onClick={() => setZoom(Math.max(0.25, zoom - 0.25))}
              size="sm"
              variant="outline"
              disabled={zoom <= 0.25}
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span className="text-sm">{Math.round(zoom * 100)}%</span>
            <Button
              onClick={() => setZoom(Math.min(3, zoom + 0.25))}
              size="sm"
              variant="outline"
              disabled={zoom >= 3}
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
          </div>
          <div className="overflow-auto w-full">
            <Image
              src={contentUrl}
              alt={file.filename}
              width={500}
              height={300}
              style={{
                transform: `scale(${zoom})`,
                transformOrigin: 'center top',
              }}
              className="transition-transform mx-auto"
              unoptimized={contentUrl.startsWith('/api/')} // For dynamic content from API
            />
          </div>
        </div>
      );
    }

    if (file.mime_type === 'application/pdf') {
      return (
        <iframe
          src={contentUrl}
          className="w-full h-[70vh]"
          title={file.filename}
        />
      );
    }

    if (
      isTextFile(file.mime_type) ||
      isCodeFile(file.mime_type, file.filename)
    ) {
      return (
        <div className="overflow-auto bg-muted p-4 rounded">
          <iframe
            src={contentUrl}
            className="w-full h-[60vh]"
            title={file.filename}
          />
        </div>
      );
    }

    // Default view for other file types
    return (
      <div className="text-center py-12">
        <p className="mb-4">
          Preview not available for this file type ({file.mime_type})
        </p>
        <Button onClick={handleDownload}>
          <DownloadCloud className="mr-2 h-4 w-4" />
          Download File
        </Button>
      </div>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl w-[90vw]">
        <DialogHeader className="flex justify-between flex-row items-center">
          <DialogTitle className="truncate max-w-[80%]">
            {file.filename}
          </DialogTitle>
          <div className="flex items-center gap-2">
            <Button onClick={handleDownload} size="sm" variant="outline">
              <DownloadCloud className="h-4 w-4" />
            </Button>
            <Button onClick={toggleFullscreen} size="sm" variant="outline">
              {isFullscreen ? (
                <Minimize className="h-4 w-4" />
              ) : (
                <Maximize className="h-4 w-4" />
              )}
            </Button>
          </div>
        </DialogHeader>
        <div className="mt-4">{renderContent()}</div>
      </DialogContent>
    </Dialog>
  );
}
