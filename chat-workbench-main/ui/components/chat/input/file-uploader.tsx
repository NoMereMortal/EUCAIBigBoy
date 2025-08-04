// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  X,
  FileText,
  Image as ImageIcon,
  Paperclip,
  Loader2,
} from 'lucide-react';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { getHeaders } from '@/lib/api/client';
import { fileApi } from '@/lib/api/resources/file';

export interface FilePointer {
  file_id: string;
  user_id?: string; // Added for ownership tracking
  mime_type: string;
  filename: string;
  file_type: string;
  format?: string; // Format used by Bedrock (jpeg, png, pdf, etc.)
}

// For files that haven't been uploaded yet
export interface LocalFileInfo {
  file: File;
  preview_url?: string;
}

interface FileUploaderProps {
  chatId?: string; // Optional - allows usage before a chat is created
  onFilesUploaded?: (files: FilePointer[]) => void; // Called when files are uploaded to server
  onFilesSelected?: (files: LocalFileInfo[]) => void; // Called when files are selected but not uploaded
  maxFiles?: number;
  maxSize?: number;
  className?: string;
  modelId?: string;
  uploadImmediately?: boolean; // Whether to upload files immediately or just select them
}

export function FileUploader({
  chatId,
  onFilesUploaded,
  onFilesSelected,
  maxFiles = 5,
  maxSize = 10 * 1024 * 1024, // 10MB default
  className,
  modelId,
  uploadImmediately = false, // Default to just selecting files
}: FileUploaderProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      // Filter out any files that would exceed the maxFiles limit
      const newFiles = [...files, ...acceptedFiles].slice(0, maxFiles);
      setFiles(newFiles);

      // Generate previews for images
      acceptedFiles.forEach((file) => {
        if (file.type.startsWith('image/')) {
          const reader = new FileReader();
          reader.onload = () => {
            setPreviews((prev) => ({
              ...prev,
              [file.name]: reader.result as string,
            }));
          };
          reader.readAsDataURL(file);
        }
      });

      // Directly notify parent about selected files when not uploading immediately
      if (!uploadImmediately && onFilesSelected) {
        // Use timeout to ensure this happens after state updates
        setTimeout(() => {
          const localFiles: LocalFileInfo[] = newFiles.map((file) => ({
            file,
            preview_url: previews[file.name],
          }));
          onFilesSelected(localFiles);
        }, 0);
      }
    },
    [files, maxFiles, previews, uploadImmediately, onFilesSelected],
  );

  const removeFile = (index: number) => {
    const newFiles = [...files];
    const removedFile = newFiles.splice(index, 1)[0];
    setFiles(newFiles);

    // Clean up preview if exists
    if (previews[removedFile.name]) {
      setPreviews((prev) => {
        const newPreviews = { ...prev };
        delete newPreviews[removedFile.name];
        return newPreviews;
      });
    }
  };

  const uploadFiles = async () => {
    if (files.length === 0) return;

    // If we're just selecting files and not uploading them to server yet
    if (!uploadImmediately || !chatId) {
      if (onFilesSelected) {
        const localFiles: LocalFileInfo[] = files.map((file) => ({
          file,
          preview_url: previews[file.name],
        }));
        onFilesSelected(localFiles);
      }
      return;
    }

    // Otherwise upload to server
    setIsUploading(true);
    setUploadError(null);

    try {
      const formData = new FormData();
      // We know chatId is defined here because of the check above
      formData.append('chat_id', chatId!);

      if (modelId) {
        formData.append('model_id', modelId);
      }

      files.forEach((file) => {
        formData.append('files', file);
      });

      // User ID will be included via X-User-ID header in fileApi
      const result = await fileApi.uploadFiles(formData);

      if (onFilesUploaded) {
        onFilesUploaded(result.files);
      }

      // Clear files after successful upload
      setFiles([]);
      setPreviews({});
    } catch (error) {
      console.error('Upload error:', error);
      setUploadError(
        error instanceof Error ? error.message : 'Failed to upload files',
      );
    } finally {
      setIsUploading(false);
    }
  };

  // We'll update the parent with the selected files only when they change through onDrop
  // and not automatically in a useEffect to avoid infinite loops

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxSize,
    maxFiles: maxFiles - files.length,
    disabled: isUploading || files.length >= maxFiles,
  });

  return (
    <div className={cn('w-full', className)}>
      {files.length > 0 ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="relative group bg-muted rounded-md p-2 flex items-center space-x-2 pr-8"
              >
                {file.type.startsWith('image/') ? (
                  <div className="w-8 h-8">
                    {previews[file.name] ? (
                      <Image
                        src={previews[file.name]}
                        alt={file.name}
                        width={32}
                        height={32}
                        className="w-full h-full object-cover rounded"
                        unoptimized={
                          previews[file.name].startsWith('data:') ||
                          previews[file.name].startsWith('/api/')
                        }
                      />
                    ) : (
                      <ImageIcon className="w-full h-full text-muted-foreground" />
                    )}
                  </div>
                ) : (
                  <FileText className="w-8 h-8 text-muted-foreground" />
                )}
                <span className="text-xs truncate max-w-[150px]">
                  {file.name}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute top-1 right-1 h-5 w-5 rounded-full opacity-70 group-hover:opacity-100"
                  onClick={() => removeFile(index)}
                  disabled={isUploading}
                >
                  <X className="h-3 w-3" />
                  <span className="sr-only">Remove file</span>
                </Button>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between">
            <div
              {...getRootProps()}
              className={cn(
                'cursor-pointer text-xs text-muted-foreground hover:text-foreground transition-colors',
                (isUploading || files.length >= maxFiles) &&
                  'opacity-50 cursor-not-allowed',
              )}
            >
              <input {...getInputProps()} />
              {files.length < maxFiles
                ? 'Add more files'
                : 'Maximum files reached'}
            </div>

            <Button
              size="sm"
              onClick={uploadFiles}
              disabled={isUploading || files.length === 0}
              className="text-xs"
            >
              {isUploading ? (
                <>
                  <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                  Uploading...
                </>
              ) : (
                'Attach to Message'
              )}
            </Button>
          </div>

          {uploadError && (
            <div className="text-xs text-destructive mt-1">{uploadError}</div>
          )}
        </div>
      ) : (
        <div
          {...getRootProps()}
          className={cn(
            'border border-dashed rounded-md p-4 text-center hover:bg-muted/50 transition-colors cursor-pointer',
            isDragActive
              ? 'border-primary bg-primary/5'
              : 'border-muted-foreground/20',
            className,
          )}
        >
          <input {...getInputProps()} />
          <Paperclip className="h-5 w-5 mx-auto text-muted-foreground mb-2" />
          <p className="text-xs text-muted-foreground">
            {isDragActive ? 'Drop files here' : 'Drag files here or'}
          </p>
          <Button
            onClick={(e) => {
              e.stopPropagation();
              const input = document.createElement('input');
              input.type = 'file';
              input.multiple = true;
              input.onchange = (event) => {
                const files = Array.from(
                  (event.target as HTMLInputElement).files || [],
                );
                onDrop(files);
              };
              input.click();
            }}
            variant="outline"
            size="sm"
            className="mt-2"
          >
            Select Files
          </Button>
          <p className="text-[10px] text-muted-foreground/70 mt-1">
            Supports images, PDFs, and text files
          </p>
        </div>
      )}
    </div>
  );
}
