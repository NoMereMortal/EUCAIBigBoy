// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { Button } from '@/components/ui/button';
import { LogIn, MessageSquare } from 'lucide-react';
import { useAuth } from '@/hooks/auth';

export function LandingPage() {
  const { login } = useAuth();

  const handleSignIn = () => {
    login();
  };

  return (
    <div className="flex h-full flex-col items-center justify-center bg-gradient-to-b from-background to-muted/30">
      <div className="max-w-3xl px-4">
        <div className="flex items-center justify-left mb-6">
          <h1 className="text-4xl font-bold">Chat Workbench</h1>
        </div>

        <p className="text-xl text-muted-foreground mb-12 justify-left">
          A production-ready AI application accelerator for building custom chat
          experiences with Amazon Bedrock
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-2">
          <Button size="lg" onClick={handleSignIn} className="min-w-[150]">
            Sign In to Continue
          </Button>
        </div>
      </div>
    </div>
  );
}
