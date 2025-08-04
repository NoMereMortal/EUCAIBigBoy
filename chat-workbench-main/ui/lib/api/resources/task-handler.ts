// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { apiClient } from '@/lib/api/client';
import { logger } from '@/lib/utils/logger';

export interface TaskHandler {
  name: string;
  description: string;
  tools?: string[];
  is_default: boolean;
  config?: Record<string, any>;
}

export interface TaskHandlerInfo {
  name: string;
  description: string;
}

export interface ListTaskHandlersResponse {
  handlers: TaskHandler[];
  last_evaluated_key?: Record<string, any> | null;
}

/**
 * Task Handler management API resource
 */
export const taskHandlerApi = {
  /**
   * Fetch all available task handlers
   * @returns List of task handlers
   */
  getTaskHandlers: async (): Promise<TaskHandler[]> => {
    try {
      const response =
        await apiClient.get<ListTaskHandlersResponse>('task-handlers');
      return response.handlers || [];
    } catch (error) {
      logger.error('TaskHandlerAPI', 'Error fetching task handlers', { error });
      return [];
    }
  },

  /**
   * Get detailed information about a specific task handler
   * @param handlerName The name of the task handler to fetch
   * @returns Task handler details or null if not found
   */
  getTaskHandler: async (handlerName: string): Promise<TaskHandler | null> => {
    try {
      const response = await apiClient.get<TaskHandler>(
        `admin/task/${handlerName}`,
      );
      return response;
    } catch (error) {
      logger.error('TaskHandlerAPI', 'Error fetching task handler', {
        handlerName,
        error,
      });
      return null;
    }
  },

  /**
   * Update task handler configuration
   * @param handlerName The name of the task handler to update
   * @param config The configuration to update
   * @returns Updated task handler or null if failed
   */
  updateTaskHandler: async (
    handlerName: string,
    config: Partial<TaskHandler>,
  ): Promise<TaskHandler | null> => {
    try {
      const response = await apiClient.put<TaskHandler>(
        `admin/task/${handlerName}`,
        config,
      );
      return response;
    } catch (error) {
      logger.error('TaskHandlerAPI', 'Error updating task handler', {
        handlerName,
        config,
        error,
      });
      return null;
    }
  },
};

// For backward compatibility
export const getTaskHandlers = taskHandlerApi.getTaskHandlers;
export const getTaskHandler = taskHandlerApi.getTaskHandler;
