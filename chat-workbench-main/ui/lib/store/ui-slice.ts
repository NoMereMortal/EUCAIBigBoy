// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { create } from 'zustand';
import { UIState } from '@/lib/store/types';

export const useUIStore = create<UIState>((set) => ({
  // Default states
  isSidebarOpen: true,
  isSettingsOpen: false,
  activeModal: null,
  tooltips: {},
  theme: 'system', // Default to system theme

  // Sidebar actions
  toggleSidebar: () => {
    set((state) => ({ isSidebarOpen: !state.isSidebarOpen }));
  },

  // Settings actions
  openSettings: () => {
    set({ isSettingsOpen: true });
  },

  closeSettings: () => {
    set({ isSettingsOpen: false });
  },

  // Modal actions
  openModal: (modalId) => {
    set({ activeModal: modalId });
  },

  closeModal: () => {
    set({ activeModal: null });
  },

  // Tooltip actions
  showTooltip: (tooltipId) => {
    set((state) => ({
      tooltips: {
        ...state.tooltips,
        [tooltipId]: true,
      },
    }));
  },

  hideTooltip: (tooltipId) => {
    set((state) => {
      const newTooltips = { ...state.tooltips };
      delete newTooltips[tooltipId];
      return { tooltips: newTooltips };
    });
  },

  // Theme actions
  setTheme: (theme) => {
    set({ theme });
    // Optionally persist theme preference to localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem('theme', theme);
    }
  },
}));
