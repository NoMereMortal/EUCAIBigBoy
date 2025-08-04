// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { AuthGuard } from '@/components/auth/auth-guard';
import { Sidebar } from '@/components/sidebar/sidebar';
import { MessageProvider } from '@/components/providers/message-provider';

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <MessageProvider>
        <div className="flex flex-1 overflow-hidden h-full">
          {/* Sidebar is only visible when user is authenticated (controlled by AuthGuard) */}
          <Sidebar />
          <div className="flex-1 overflow-hidden">{children}</div>
        </div>
      </MessageProvider>
    </AuthGuard>
  );
}
