// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import React, { useState, useEffect } from 'react';
import { ChatSession } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Settings2, User2, UserCircle, RefreshCw } from 'lucide-react';
import { SettingsDialog } from '@/components/settings/settings-dialog';
import { useRouter, usePathname } from 'next/navigation';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { LogoutButton } from '@/components/auth/logout-button';
import { useUserProfile } from '@/hooks/use-user-profile';
import { CachedLogo } from '@/components/ui/cached-logo';
import { useMessageStore } from '@/lib/store/index';

interface ChatHeaderProps {
  chat?: ChatSession | null | undefined;
}

// No need for additional memoization as CachedLogo is already memoized
// with proper dependency checking

export function ChatHeader({ chat }: ChatHeaderProps) {
  const router = useRouter();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { userProfile } = useUserProfile();

  // Add state for logo size and force reload
  const handleNavigateHome = () => {
    // Clear any existing message state before navigation to ensure a clean slate
    useMessageStore.getState().clearMessages();
    // Navigate to the home route
    router.push('/');
  };

  return (
    <div>
      <div className="flex items-center justify-between px-4 pt-1 shadow-xs">
        <div
          className="flex items-center select-none cursor-pointer hover:opacity-80 transition-opacity"
          onClick={handleNavigateHome}
          title="Go to home"
        >
          <div className="pr-2">
            <CachedLogo
              width={40}
              height={20}
              className={`h-${20 / 4} w-auto`}
            />
          </div>
          <div>
            <span className="text-xl px-2 -mt-1 text-black dark:text-foreground">
              {typeof window !== 'undefined' &&
              window.env &&
              window.env.UI_TITLE
                ? window.env.UI_TITLE
                : ''}
            </span>
          </div>
        </div>

        {/* Center spacer */}
        <div className="flex-1"></div>

        <div className="flex items-center justify-between mb-2">
          {/* <ThemeToggle /> */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSettingsOpen(true)}
            title="Settings"
            className="hover:bg-stone-200"
          >
            <Settings2 className="icon-sm" />
          </Button>
          <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                title="User"
                className="hover:bg-stone-200"
              >
                <User2 className="icon-sm" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="pb-2">
              {userProfile ? (
                <>
                  <DropdownMenuLabel className="flex flex-col">
                    <span>
                      {userProfile.firstName} {userProfile.lastName}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {userProfile.email}
                    </span>
                    {userProfile.isAdmin && (
                      <span className="text-xs mt-1 font-semibold text-blue-500">
                        Admin
                      </span>
                    )}
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                </>
              ) : null}
              <DropdownMenuItem asChild className="cursor-pointer">
                <LogoutButton />
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
}
