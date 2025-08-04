// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { memo, useEffect, useState } from 'react';
import Image from 'next/image';
import { useTheme } from 'next-themes';

interface CachedLogoProps {
  className?: string;
  height?: number;
  width?: number;
  alt?: string;
  forceReload?: number | string; // Add a prop to force reload when changed
}

const CachedLogoComponent = ({
  className = '',
  height = 20,
  width = 20,
  alt = 'Logo',
  forceReload = 0,
}: CachedLogoProps) => {
  // Get current theme
  const { resolvedTheme } = useTheme();

  // Keep track of mounted state for hydration
  const [mounted, setMounted] = useState(false);

  // Set mounted to true on client-side
  useEffect(() => {
    setMounted(true);
  }, []);

  // Use state to store preloaded images
  const [logoCache, setLogoCache] = useState<{
    light: HTMLImageElement | null;
    dark: HTMLImageElement | null;
  }>({ light: null, dark: null });

  // Preload both logo versions on mount - client side only
  useEffect(() => {
    // Skip during SSR
    if (typeof window === 'undefined') return;

    const lightLogo = new window.Image();
    lightLogo.src = '/logo-light.png';
    lightLogo.onload = () => {
      setLogoCache((prev) => ({ ...prev, light: lightLogo }));
    };

    const darkLogo = new window.Image();
    darkLogo.src = '/logo-dark.png';
    darkLogo.onload = () => {
      setLogoCache((prev) => ({ ...prev, dark: darkLogo }));
    };

    // Clean up
    return () => {
      lightLogo.onload = null;
      darkLogo.onload = null;
    };
  }, []);

  // Determine which logo to show based on theme
  // Add cache-busting query parameter when forceReload changes
  const logoSrc = `${
    mounted && resolvedTheme === 'dark' ? '/logo-dark.png' : '/logo-light.png'
  }${forceReload ? `?v=${forceReload}` : ''}`;

  return (
    <Image
      src={logoSrc}
      height={height}
      width={width}
      alt={alt}
      className={className}
      priority={true} // Loads the logo immediately
      // We want logo to load first since it's above the fold
      // Add cache-related props for optimal caching
      unoptimized={false} // Use Next.js optimization
    />
  );
};

// Memoize the component to prevent unnecessary re-renders
// But ensure it re-renders when important props change
export const CachedLogo = memo(CachedLogoComponent, (prevProps, nextProps) => {
  // Return false (trigger re-render) if these props change
  return (
    prevProps.height === nextProps.height &&
    prevProps.width === nextProps.width &&
    prevProps.forceReload === nextProps.forceReload
  );
});
