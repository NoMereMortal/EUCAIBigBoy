// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Store-specific types for the application
import { ChatSession, Prompt, ListPromptsResponse, Message } from '@/lib/types';
import { MessageState } from '@/lib/store/message/message-types';

// Chat slice types
export interface ChatState {
  // Chat sessions
  chats: ChatSession[];
  activeChat: ChatSession | null;
  activeChatId: string | null;
  isLoadingChats: boolean;

  // Actions
  fetchChats: (userId?: string) => Promise<void>;
  fetchChat: (chatId: string) => Promise<ChatSession | null>;
  createChat: (title: string, userId?: string) => Promise<ChatSession>;
  setActiveChat: (chatId: string | null, userId?: string) => Promise<void>;
  updateChatTitle: (chatId: string, title: string) => Promise<void>;
  deleteChat: (chatId: string) => Promise<void>;
}

// Settings slice types
export interface SettingsState {
  // Model, persona, prompt, and task handler selection
  selectedModelId: string | null;
  selectedPersonaId: string | null;
  selectedPromptId: string | null;
  selectedPrompt: Prompt | null;
  selectedTaskHandler: string; // Task handler name

  // Actions
  getEffectiveModelId: (defaultModelId?: string | null) => string | null;
  setSelectedModel: (modelId: string) => void;
  setSelectedPersona: (personaId: string | null) => void;
  setSelectedPrompt: (promptId: string | null) => Promise<void>;
  clearSelectedPrompt: () => void;
  fetchPrompts: (
    limit?: number,
    lastKey?: string,
    category?: string,
  ) => Promise<ListPromptsResponse>;
  searchPrompts: (
    query: string,
    limit?: number,
    lastKey?: string,
  ) => Promise<ListPromptsResponse>;
  setSelectedTaskHandler: (taskHandler: string) => void;
}

// UI Slice types
export interface UIState {
  isSidebarOpen: boolean;
  isSettingsOpen: boolean;
  activeModal: string | null;
  tooltips: Record<string, boolean>;
  theme: string;

  // Actions
  toggleSidebar: () => void;
  openSettings: () => void;
  closeSettings: () => void;
  openModal: (modalId: string) => void;
  closeModal: () => void;
  showTooltip: (tooltipId: string) => void;
  hideTooltip: (tooltipId: string) => void;
  setTheme: (theme: string) => void;
}

// Combined store type for the optimized implementation
export interface RootState
  // All action methods from each slice
  extends Omit<
      SettingsState,
      | 'selectedModelId'
      | 'selectedPersonaId'
      | 'selectedPromptId'
      | 'selectedPrompt'
      | 'selectedTaskHandler'
    >,
    Omit<
      UIState,
      'isSidebarOpen' | 'isSettingsOpen' | 'activeModal' | 'tooltips' | 'theme'
    >,
    MessageState {
  // Deprecated auth actions that remain for backward compatibility
  setCurrentUser: (userId: string) => void;
  setUserProfile: (profile: any | null) => void;
  login: () => Promise<void>;
  logout: () => Promise<void>;

  // Root level actions
  resetStore: () => void;

  // Auth state getters (deprecated - use useAuth() hook instead)
  readonly isAuthenticated: boolean;
  readonly currentUserId: string;
  readonly userProfile: {
    id: string;
    email: string;
    name: string;
    preferences: Record<string, any>;
  } | null;

  // Chat state getters
  readonly chats: ChatSession[];
  readonly activeChat: ChatSession | null;
  readonly activeChatId: string | null;
  readonly isLoadingChats: boolean;

  // Settings state getters
  readonly selectedModelId: string | null;
  readonly selectedPersonaId: string | null;
  readonly selectedPromptId: string | null;
  readonly selectedPrompt: Prompt | null;
  readonly selectedTaskHandler: string;

  // UI state getters
  readonly isSidebarOpen: boolean;
  readonly isSettingsOpen: boolean;
  readonly activeModal: string | null;
  readonly tooltips: Record<string, boolean>;
  readonly theme: string;
}

// Type for internal store references
export interface StoreReferences {
  _authStore?: any; // Made optional as auth is now handled by useAuth() hook
  _settingsStore: any;
  _uiStore: any;
  _messageStore: any;
  _citationStore: any;
}
