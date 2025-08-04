// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { StoreApi, UseBoundStore } from 'zustand';

/**
 * Helper function to create auto-memoizing selectors for a Zustand store
 * This dramatically reduces unnecessary re-renders by ensuring components
 * only subscribe to the specific state slices they need.
 */
export function createSelectors<
  T extends object,
  U extends UseBoundStore<StoreApi<T>>,
>(store: U) {
  type StateKeys = keyof T;

  const selectors = Object.keys(store.getState()).reduce(
    (acc, key) => {
      const k = key as StateKeys;

      // Create a selector function for this state slice
      acc[k] = (state?: T) => {
        if (state !== undefined) {
          return state[k];
        }
        return store((s) => s[k]);
      };

      return acc;
    },
    {} as Record<StateKeys, (state?: T) => T[StateKeys]>,
  );

  return Object.assign(store, selectors);
}

/**
 * Creates a selector that only selects a specific property from an object in the state
 * This is useful for subscribing to deeply nested properties
 */
export function createPropertySelectors<T, K extends keyof T>(
  selector: (state: any) => T | undefined | null,
  properties: K[],
) {
  return properties.reduce(
    (acc, property) => {
      // Explicitly handle the case where selector returns null/undefined
      acc[property] = (state: any) => {
        const value = selector(state);
        return value ? value[property] : undefined;
      };
      return acc;
    },
    {} as Record<K, (state: any) => T[K] | undefined>,
  );
}
