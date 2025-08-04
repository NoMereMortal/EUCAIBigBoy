// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// lib/store/index.ts
import { create } from 'zustand';
import { createSelectors } from '@/lib/store/selector-utils';
import { RootState, StoreReferences } from '@/lib/store/types';
import { useSettingsStore } from '@/lib/store/settings-slice';
import { useUIStore } from '@/lib/store/ui-slice';
import { useMessageStore } from '@/lib/store/message/message-slice';
import { useCitationStore } from '@/lib/store/citation-slice';
import { MessagePart } from '@/lib/types';

const createStore = () => {
  const store = create<Partial<RootState> & StoreReferences>((set, get) => ({
    // Internal store references
    _settingsStore: useSettingsStore,
    _uiStore: useUIStore,
    _messageStore: useMessageStore,
    _citationStore: useCitationStore,

    // Chat slice
    get isLoadingChats() {
      return useMessageStore.getState().isLoadingChats;
    },

    // Settings slice
    get selectedModelId() {
      return useSettingsStore.getState().selectedModelId;
    },
    get selectedPersonaId() {
      return useSettingsStore.getState().selectedPersonaId;
    },
    get selectedPromptId() {
      return useSettingsStore.getState().selectedPromptId;
    },
    get selectedPrompt() {
      return useSettingsStore.getState().selectedPrompt;
    },
    get selectedTaskHandler() {
      return useSettingsStore.getState().selectedTaskHandler;
    },

    // UI slice
    get isSidebarOpen() {
      return useUIStore.getState().isSidebarOpen;
    },
    get isSettingsOpen() {
      return useUIStore.getState().isSettingsOpen;
    },
    get activeModal() {
      return useUIStore.getState().activeModal;
    },
    get tooltips() {
      return useUIStore.getState().tooltips;
    },
    get theme() {
      return useUIStore.getState().theme;
    },

    // Message slice
    get chats() {
      return useMessageStore.getState().chats;
    },
    get activeChatId() {
      // Get the current route's chat ID here to determine active chat
      if (typeof window === 'undefined') return null;
      const pathname = window.location.pathname;
      if (pathname.startsWith('/chat/')) {
        return pathname.split('/')[2];
      }
      return null;
    },
    // Message slice getters
    get messages() {
      return useMessageStore.getState().messages;
    },
    get messagesByChat() {
      return useMessageStore.getState().messagesByChat;
    },
    get activeMessagePath() {
      return useMessageStore.getState().activeMessagePath;
    },
    get isStreaming() {
      return useMessageStore.getState().isStreaming;
    },
    get currentStreamingId() {
      return useMessageStore.getState().currentStreamingId;
    },
    get isMessageError() {
      return useMessageStore.getState().error !== null;
    },
    get messageError() {
      return useMessageStore.getState().error;
    },
    fetchChats: (userId?: string) =>
      useMessageStore.getState().fetchChats(userId),
    fetchChat: (chatId: string) => useMessageStore.getState().fetchChat(chatId),
    createChat: (title: string, userId?: string) =>
      useMessageStore.getState().createChat(title, userId),
    setActiveChat: (chatId: string | null) => {
      // This now just navigates to the chat page
      if (typeof window !== 'undefined') {
        if (!chatId) {
          window.location.href = '/';
        } else {
          window.location.href = `/chat/${chatId}`;
        }
      }
    },
    updateChatTitle: (chatId: string, title: string) =>
      useMessageStore.getState().updateChatTitle(chatId, title),
    deleteChat: (chatId: string) =>
      useMessageStore.getState().deleteChat(chatId),

    // Root level actions
    resetStore: () => {
      // For settings, use any persisted values or null
      const persistedModelId =
        typeof window !== 'undefined'
          ? localStorage.getItem('selectedModelId')
          : null;

      // Reset all the individual stores using their own reset methods
      useSettingsStore.setState({
        selectedModelId: persistedModelId, // Keep persisted model ID
        selectedPersonaId: null,
        selectedPromptId: null,
        selectedPrompt: null,
        selectedTaskHandler: 'chat', // Reset to default
      });
      useUIStore.setState({
        isSidebarOpen: true,
        isSettingsOpen: false,
        activeModal: null,
        tooltips: {},
        theme: 'system',
      });
      // Reset message store
      useMessageStore.getState().clearMessages();
    },

    // Streamlined settings actions with coordinated updates
    setSelectedModel: (modelId: string) => {
      useSettingsStore.getState().setSelectedModel(modelId);
    },
    setSelectedPersona: (personaId: string | null) => {
      useSettingsStore.getState().setSelectedPersona(personaId);
    },
    setSelectedPrompt: (promptId: string | null) =>
      useSettingsStore.getState().setSelectedPrompt(promptId),
    clearSelectedPrompt: () =>
      useSettingsStore.getState().clearSelectedPrompt(),
    setSelectedTaskHandler: (taskHandler: string) =>
      useSettingsStore.getState().setSelectedTaskHandler(taskHandler),
    fetchPrompts: (limit?: number, lastKey?: string, category?: string) =>
      useSettingsStore.getState().fetchPrompts(limit, lastKey, category),
    searchPrompts: (query: string, limit?: number, lastKey?: string) =>
      useSettingsStore.getState().searchPrompts(query, limit, lastKey),

    // Delegated UI actions
    toggleSidebar: () => useUIStore.getState().toggleSidebar(),
    openSettings: () => useUIStore.getState().openSettings(),
    closeSettings: () => useUIStore.getState().closeSettings(),
    openModal: (modalId: string) => useUIStore.getState().openModal(modalId),
    closeModal: () => useUIStore.getState().closeModal(),
    showTooltip: (tooltipId: string) =>
      useUIStore.getState().showTooltip(tooltipId),
    hideTooltip: (tooltipId: string) =>
      useUIStore.getState().hideTooltip(tooltipId),
    setTheme: (theme: string) => useUIStore.getState().setTheme(theme),

    // Delegated message actions
    startMessageGeneration: (
      chatId: string,
      content: string | any[] | MessagePart[],
      parentId?: string | null,
    ) =>
      useMessageStore
        .getState()
        .startMessageGeneration(chatId, content, parentId),
    editMessage: (messageId: string, newContent: string) =>
      useMessageStore.getState().editMessage(messageId, newContent),
    regenerateMessage: (messageId: string) =>
      useMessageStore.getState().regenerateMessage(messageId),
    interruptStream: () => useMessageStore.getState().interruptStream(),
    clearChatMessages: (chatId: string) =>
      useMessageStore.getState().clearChatMessages(chatId),
  }));
  return store;
};

// Create the store with selectors
export const useStore = createSelectors(createStore());

// Export individual store slices for direct usage when needed
export { useSettingsStore, useUIStore, useMessageStore, useCitationStore };

// Note: Auth functionality has been migrated to useAuth() from '@/hooks/auth'
