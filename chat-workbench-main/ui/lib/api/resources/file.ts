// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { apiClient, isServer, getHeaders } from '@/lib/api/client';
import { FilePointer } from '@/components/chat/input/file-uploader';

/**
 * File API for handling uploads and downloads
 */
export const fileApi = {
  /**
   * Upload files to the server
   * Using specialized FormData handling via apiClient
   */
  uploadFiles: async (
    formData: FormData,
  ): Promise<{ files: FilePointer[] }> => {
    // Skip API calls during SSR
    if (isServer()) {
      console.warn('Cannot upload files during server-side rendering');
      return { files: [] };
    }

    try {
      // Use the new apiClient.postFormData method which handles FormData properly
      // Make path explicit to match backend router
      return await apiClient.postFormData<{ files: FilePointer[] }>(
        'files/',
        formData,
      );
    } catch (error) {
      console.error('Upload error:', error);
      throw error;
    }
  },

  /**
   * Get content from file ID
   * @param fileId - The file ID to retrieve
   */
  getFile: async (fileId: string): Promise<Blob> => {
    // Skip API calls during SSR
    if (isServer()) {
      console.warn('Cannot get files during server-side rendering');
      throw new Error('Cannot get files during server-side rendering');
    }

    try {
      // User ID is now passed in the X-User-ID header via getHeaders()
      // Use apiClient to ensure consistency in URL construction and header management
      // Make path explicit to match backend router
      const response = await fetch(apiClient.buildUrl(`files/${fileId}`), {
        headers: getHeaders(),
      });

      if (!response.ok) {
        throw new Error(`Failed to retrieve file: ${response.statusText}`);
      }

      return await response.blob();
    } catch (error) {
      console.error('File retrieval error:', error);
      throw error;
    }
  },

  /**
   * Delete a file
   * @param fileId - The file ID to delete
   */
  deleteFile: async (fileId: string): Promise<void> => {
    // Skip API calls during SSR
    if (isServer()) {
      console.warn('Cannot delete files during server-side rendering');
      throw new Error('Cannot delete files during server-side rendering');
    }

    try {
      // Make path explicit to match backend router
      await apiClient.delete(`files/${fileId}`);
    } catch (error) {
      console.error(`Error deleting file ${fileId}:`, error);
      throw error;
    }
  },
};
