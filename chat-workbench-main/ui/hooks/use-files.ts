// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/index';
import { FilePointer } from '@/components/chat/input/file-uploader';

// Query keys for React Query
export const fileKeys = {
  all: ['files'] as const,
  details: () => [...fileKeys.all, 'detail'] as const,
  detail: (id: string) => [...fileKeys.details(), id] as const,
};

/**
 * Hook for uploading files
 * @returns Mutation hook for file uploads
 */
export function useUploadFiles() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (formData: FormData) => api.file.uploadFiles(formData),
    onSuccess: (response) => {
      // Update cache for each uploaded file
      response.files.forEach((file) => {
        queryClient.setQueryData(fileKeys.detail(file.file_id), file);
      });
    },
  });
}

/**
 * Hook for retrieving a file by ID
 * @param fileId The ID of the file to retrieve
 * @returns Query hook for file retrieval
 */
export function useFile(fileId: string) {
  return useQuery({
    queryKey: fileKeys.detail(fileId),
    queryFn: () => api.file.getFile(fileId),
    enabled: !!fileId,
    staleTime: 1000 * 60 * 30, // 30 minutes - files don't change often
    gcTime: 1000 * 60 * 60, // 60 minutes - renamed from cacheTime in newer React Query versions
  });
}

/**
 * Hook for deleting a file
 * @returns Mutation hook for file deletion
 */
export function useDeleteFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (fileId: string) => api.file.deleteFile(fileId),
    onSuccess: (_, fileId) => {
      // Remove the file from the cache
      queryClient.removeQueries({ queryKey: fileKeys.detail(fileId) });
    },
  });
}
