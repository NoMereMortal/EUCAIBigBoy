// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { useAuth } from '@/hooks/auth';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { LandingPage } from '@/components/landing/landing-page';
import { Chat } from '@/components/chat/chat';
import { Sidebar } from '@/components/sidebar/sidebar';
import { useMessageStore } from '@/lib/store/message/message-slice';

export default function Home() {
  const { isAuthenticated, isLoading, userProfile } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [isCreatingChat, setIsCreatingChat] = useState(false);
  const router = useRouter();
  const { createChat } = useMessageStore();

  // Mark component as mounted after hydration
  useEffect(() => {
    setMounted(true);
  }, []);

  // DISABLED: Auto-creation was causing infinite loops
  // Will manually navigate to test streaming

  // During server-side rendering or before hydration, render a simple placeholder
  if (!mounted) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-t-transparent border-white"></div>
      </div>
    );
  }

  // Show loading while creating chat
  if (isAuthenticated && isCreatingChat) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-t-transparent border-blue-500 mx-auto mb-4"></div>
          <p>Creating new chat...</p>
        </div>
      </div>
    );
  }

  // If authenticated but not creating chat (fallback), render chat with sidebar
  if (isAuthenticated) {
    return (
      <div className="flex h-full">
        <Sidebar />
        <div className="flex-1 overflow-hidden">
          <Chat />
        </div>
      </div>
    );
  }

  // Otherwise show landing page
  return <LandingPage />;
}
