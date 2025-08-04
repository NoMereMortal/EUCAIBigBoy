// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Central type definitions file
// Re-exports types from domain-specific files

export * from './auth-types';
export * from './ui-types';
export * from './guardrail-types';
export * from './message-types';
import { Message } from '@/lib/types/message-types';

// Using Record<string, unknown> instead of empty interface to satisfy the ESLint rule
// while still maintaining the type's intention as an object with potentially any properties
export type WSGenerateResponse = Record<string, unknown>;

// Chat session types
export interface ChatSession {
  chat_id: string;
  user_id?: string | null;
  title: string;
  created_at: string;
  updated_at: string;
  status: string;
  messages: Message[];
  metadata: Record<string, any>;
  usage: Record<string, any>;
}

export interface CreateChatRequest {
  title: string;
  user_id?: string | null;
  metadata?: Record<string, any>;
}

export interface UpdateChatRequest {
  title?: string | null;
  status?: string | null;
  metadata?: Record<string, any> | null;
}

// Persona types
export interface Persona {
  persona_id: string;
  name: string;
  description: string;
  prompt: string;
  created_at: string;
  updated_at: string;
  metadata: Record<string, any>;
  is_active: boolean;
}

export interface CreatePersonaRequest {
  name: string;
  description: string;
  prompt: string;
  metadata?: Record<string, any>;
}

export interface UpdatePersonaRequest {
  name?: string;
  description?: string;
  prompt?: string;
  metadata?: Record<string, any>;
  is_active?: boolean;
}

export interface ListPersonasResponse {
  personas: Persona[];
  last_evaluated_key: any | null;
}

// Prompt types
export interface Prompt {
  prompt_id: string;
  name: string;
  description: string;
  content: string;
  category: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  metadata: Record<string, any>;
  is_active: boolean;
}

export interface CreatePromptRequest {
  name: string;
  description: string;
  content: string;
  category: string;
  tags?: string[];
  metadata?: Record<string, any>;
}

export interface UpdatePromptRequest {
  name?: string;
  description?: string;
  content?: string;
  category?: string;
  tags?: string[];
  metadata?: Record<string, any>;
  is_active?: boolean;
}

export interface ListPromptsResponse {
  prompts: Prompt[];
  last_evaluated_key: any | null;
}
