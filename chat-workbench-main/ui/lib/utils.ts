// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Creates a throttled function that only invokes the provided function at most once per
 * specified interval.
 *
 * @param func The function to throttle
 * @param limit The time limit in milliseconds
 * @returns A throttled version of the function
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number,
): (...args: Parameters<T>) => void {
  let inThrottle = false;
  let lastArgs: Parameters<T> | null = null;

  return function (this: any, ...args: Parameters<T>): void {
    // Store the latest arguments
    lastArgs = args;

    // If we're not in throttle mode, execute immediately
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;

      // Set a timeout to exit throttle mode
      setTimeout(() => {
        inThrottle = false;

        // If there were calls during the throttle period, execute with the latest args
        if (lastArgs) {
          func.apply(this, lastArgs);
          lastArgs = null;
        }
      }, limit);
    }
  };
}
