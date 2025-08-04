// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

/**
 * Chat Workbench API
 * Main export file that consolidates all API endpoints and utilities
 */

// Import all APIs
import {
  apiClient,
  isServer,
  setAuthObject,
  getHeaders,
} from '@/lib/api/client';
import { chatApi } from '@/lib/api/resources/chat';
import { messageApi } from '@/lib/api/resources/message';
import { modelApi } from '@/lib/api/resources/model';
import { promptApi } from '@/lib/api/resources/prompt';
import { personaApi } from '@/lib/api/resources/persona';
import { guardrailApi } from '@/lib/api/resources/guardrail';
import { userApi } from '@/lib/api/resources/user';
import { fileApi } from '@/lib/api/resources/file';
import { taskHandlerApi } from '@/lib/api/resources/task-handler';

// Export client utilities
export { apiClient, isServer, setAuthObject, getHeaders };

// Export resource APIs
export { chatApi };
export { messageApi };
export { modelApi };
export { promptApi };
export { personaApi };
export { guardrailApi };
export { userApi };
export { fileApi };
export { taskHandlerApi };

// Create a consolidated API object with namespaced resources
export const api = {
  // Namespaced resources
  chat: chatApi,
  message: messageApi,
  model: modelApi,
  prompt: promptApi,
  persona: personaApi,
  guardrail: guardrailApi,
  user: userApi,
  file: fileApi,
  taskHandler: taskHandlerApi,

  // Backward compatibility exports
  // Chat Session Management
  createChat: chatApi.createChat,
  getChats: chatApi.getChats,
  getChat: chatApi.getChat,
  updateChat: chatApi.updateChat,
  deleteChat: chatApi.deleteChat,

  // Message Generation
  generateMessageStream: messageApi.generateMessageStream,
  generateMessage: messageApi.generateMessage,
  generateMessageWebSocket: messageApi.generateMessageWebSocket,

  // Prompt Library Management
  createPrompt: promptApi.createPrompt,
  getPrompt: promptApi.getPrompt,
  getPrompts: promptApi.getPrompts,
  searchPrompts: promptApi.searchPrompts,
  updatePrompt: promptApi.updatePrompt,
  deletePrompt: promptApi.deletePrompt,

  // Persona Management
  createPersona: personaApi.createPersona,
  getPersona: personaApi.getPersona,
  getPersonas: personaApi.getPersonas,
  updatePersona: personaApi.updatePersona,
  deletePersona: personaApi.deletePersona,

  // Guardrail Management
  getGuardrails: guardrailApi.getGuardrails,
  getGuardrail: guardrailApi.getGuardrail,
  createGuardrail: guardrailApi.createGuardrail,
  updateGuardrail: guardrailApi.updateGuardrail,
  deleteGuardrail: guardrailApi.deleteGuardrail,
  publishGuardrailVersion: guardrailApi.publishGuardrailVersion,
};

// Default export for convenience
export default api;
