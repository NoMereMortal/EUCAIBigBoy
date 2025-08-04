// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { Button } from '@/components/ui/button';
import { AlertCircle, MessageSquare } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { AuthProvider } from '@/hooks/auth';

export default function ChatNotFound() {
  const router = useRouter();

  const handleNewChat = () => {
    router.push('/');
  };

  return (
    <AuthProvider>
      <div className="flex h-full flex-col items-center justify-center bg-gradient-to-b from-background to-muted/30">
        <div className="max-w-3xl text-center px-4">
          <div className="flex items-center justify-center mb-6">
            <AlertCircle className="h-12 w-12 text-primary mr-2" />
            <h1 className="text-4xl font-bold">Chat Not Found</h1>
          </div>

          <p className="text-xl text-muted-foreground mb-12">
            The chat you are looking for doesn&apos;t exist or has been deleted.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button size="lg" onClick={handleNewChat} className="min-w-[200px]">
              <MessageSquare className="icon-md mr-2" />
              Start New Chat
            </Button>
          </div>
        </div>
      </div>
    </AuthProvider>
  );
}
