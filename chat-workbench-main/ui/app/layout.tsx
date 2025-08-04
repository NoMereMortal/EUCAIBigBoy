// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import './globals.css';
import Script from 'next/script';
import { ThemeProvider } from '@/components/ui/theme-provider';
import { AuthProvider } from '@/hooks/auth';
import { AuthInitializer } from '@/components/auth/auth-initializer';
import { QueryProvider } from '@/components/providers/query-provider';
import { Toaster } from '@/components/ui/toaster';
import { useEffect } from 'react';
import {
  cleanupWebSocketClient,
  ensureWebSocketClient,
} from '@/lib/services/websocket-service';
import { WebSocketCitationHandler } from '@/components/chat/websocket-citation-handler';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Handle cleanup on page navigation
  useEffect(() => {
    return () => {
      // Cleanup websocket client when navigating away from the page
      const client = ensureWebSocketClient();
      if (client && client.isConnected()) {
        cleanupWebSocketClient();
      }
    };
  }, []);

  // Create a custom CSP meta component that renders on client
  const CSPMeta = () => {
    useEffect(() => {
      // This script runs client-side only
      const hostname = window.location.hostname;
      const isLocal =
        hostname === 'localhost' ||
        hostname === '127.0.0.1' ||
        hostname.startsWith('192.168.') ||
        hostname.startsWith('10.') ||
        hostname.endsWith('.local');

      console.debug(
        `Environment detected: ${hostname} (${isLocal ? 'local' : 'production'})`,
      );

      // Remove any existing CSP meta tag
      const existingMeta = document.querySelector(
        'meta[http-equiv="Content-Security-Policy"]',
      );
      if (existingMeta) {
        existingMeta.remove();
      }

      // Add the appropriate CSP meta tag
      const meta = document.createElement('meta');
      meta.setAttribute('http-equiv', 'Content-Security-Policy');

      if (isLocal) {
        // Local environment CSP - allow HTTP for localhost
        meta.setAttribute(
          'content',
          "default-src 'self'; connect-src 'self' http: https: ws: wss:; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'",
        );
        console.debug('Applied local environment policy');
      } else {
        // Production CSP - upgrade all requests to HTTPS
        meta.setAttribute('content', 'upgrade-insecure-requests');
        console.debug('Applied production environment policy');
      }

      document.head.appendChild(meta);
    }, []);

    return null;
  };

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script src="/env.js" strategy="beforeInteractive" />
      </head>
      <body className="font-sans" suppressHydrationWarning>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <QueryProvider>
            <AuthProvider>
              <AuthInitializer />
              <WebSocketCitationHandler />
              <div className="flex flex-col h-screen">
                <main className="flex-1 overflow-hidden h-full">
                  {children}
                </main>
              </div>
              <Toaster />
              {/* CSP Meta tag management */}
              <CSPMeta />
            </AuthProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
