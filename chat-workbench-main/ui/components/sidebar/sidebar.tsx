// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { Button } from '@/components/ui/button';
import {
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  Loader2,
} from 'lucide-react';
import { SearchInput } from '@/components/ui/search-input';
import { useMessageStore, useStore } from '@/lib/store/index';
import { ChatItem } from '@/components/sidebar/chat-item';
import { useRouter, usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useState, useEffect, useRef } from 'react';
import { useMediaQuery } from '@/hooks/use-media-query';
import { useUserProfile } from '@/hooks/use-user-profile';
import { ChatSession } from '@/lib/types';

export function Sidebar() {
  // Replace chat store with message store
  const { fetchChats, chats, isLoadingChats, error } = useMessageStore();

  // Auth stuff for user ID
  const { userProfile } = useUserProfile();

  const router = useRouter();
  const pathname = usePathname();
  const [searchQuery, setSearchQuery] = useState('');
  const [isCollapsed, setIsCollapsed] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollHint, setShowScrollHint] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Fetch chats when component mounts and user ID is available
  useEffect(() => {
    if (userProfile?.id) {
      fetchChats(userProfile.id);
    }
  }, [fetchChats, userProfile?.id]);

  // Group chats by date: Today, This Week, This Month, Older
  const groupChatsByDate = (chats: ChatSession[]) => {
    const now = new Date();

    // Start of today (midnight)
    const startOfToday = new Date(now);
    startOfToday.setHours(0, 0, 0, 0);

    const oneWeekAgo = new Date(now);
    oneWeekAgo.setDate(now.getDate() - 7);

    const oneMonthAgo = new Date(now);
    oneMonthAgo.setMonth(now.getMonth() - 1);

    return {
      today: chats.filter((chat) => new Date(chat.updated_at) >= startOfToday),
      thisWeek: chats.filter(
        (chat) =>
          new Date(chat.updated_at) >= oneWeekAgo &&
          new Date(chat.updated_at) < startOfToday,
      ),
      thisMonth: chats.filter(
        (chat) =>
          new Date(chat.updated_at) >= oneMonthAgo &&
          new Date(chat.updated_at) < oneWeekAgo,
      ),
      older: chats.filter((chat) => new Date(chat.updated_at) < oneMonthAgo),
    };
  };

  const filteredChats = searchQuery
    ? chats.filter((chat: ChatSession) =>
        chat.title.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : chats;

  const groupedChats = groupChatsByDate(filteredChats);

  // Check if scrollable content exists
  useEffect(() => {
    const checkForScrollableContent = () => {
      const container = scrollContainerRef.current;
      if (container) {
        setShowScrollHint(container.scrollHeight > container.clientHeight);
      }
    };

    checkForScrollableContent();
    // Re-check when chats change
    if (chats.length > 0) {
      checkForScrollableContent();
    }

    // Add resize listener
    window.addEventListener('resize', checkForScrollableContent);
    return () =>
      window.removeEventListener('resize', checkForScrollableContent);
  }, [chats, filteredChats]);

  // Client-side only media queries
  const [isMounted, setIsMounted] = useState(false);
  const isSmallScreen = useMediaQuery('(max-width: 640px)');
  const isExtraSmallScreen = useMediaQuery('(max-width: 480px)');

  // Mount check for hydration
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    // Only run this effect on the client after mounting
    if (!isMounted) return;

    if (isSmallScreen && !isExtraSmallScreen) {
      setIsCollapsed(true);
    }
  }, [isSmallScreen, isExtraSmallScreen, isMounted]);

  const activeChatId =
    pathname === '/'
      ? 'new'
      : pathname?.startsWith('/chat/')
        ? pathname.split('/').pop()
        : undefined;

  const handleNewChat = () => {
    // Clear any existing message state before navigation to ensure a clean slate
    useMessageStore.getState().clearMessages();
    // Navigate to the home route
    router.push('/');
  };

  const handleChatItemClick = () => {
    if (isExtraSmallScreen) {
      setIsCollapsed(true);
    }
  };

  return (
    <div
      className={cn(
        'flex h-full flex-col border-r transition-all duration-500 sidebar shadow-xs',
        isCollapsed
          ? 'w-16 bg-background'
          : isExtraSmallScreen
            ? 'w-full'
            : 'w-64',
        isExtraSmallScreen && !isCollapsed ? 'absolute inset-0 z-50' : '',
        isCollapsed && !isExtraSmallScreen ? 'border-none' : '',
      )}
    >
      <div className={cn('flex items-center p-4', isCollapsed ? 'pr-0' : '')}>
        {!isCollapsed ? (
          <>
            <Button
              size="icon"
              variant={'ghost'}
              onClick={() => setIsCollapsed(true)}
              title="Close sidebar"
              className={cn(
                'icon-md flex-shrink-0',
                'rounded-lg hover:bg-primary/10',
              )}
            >
              <PanelLeftClose />
            </Button>
            <div
              className={cn(
                'flex items-center w-full transition-opacity duration-700 delay-300 ml-2',
                isCollapsed ? 'opacity-0' : 'opacity-100',
              )}
            >
              <SearchInput
                placeholder="Search chats..."
                onSearch={setSearchQuery}
                className="flex-1"
              />

              <div className="flex items-center ml-2">
                <Button
                  size="icon"
                  variant={'ghost'}
                  onClick={handleNewChat}
                  title="New chat"
                  className={cn(
                    'icon-md flex-shrink-0',
                    'rounded-lg hover:bg-primary/10',
                  )}
                >
                  <MessageSquarePlus />
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex items-center h-8">
            <Button
              size="icon"
              variant={'ghost'}
              onClick={() => setIsCollapsed(false)}
              title="Open sidebar"
              className={cn('icon-md rounded-lg hover:bg-primary/10')}
            >
              <PanelLeftOpen />
            </Button>
            <Button
              size="icon"
              variant={'ghost'}
              onClick={handleNewChat}
              title="New chat"
              className={cn(
                'icon-md flex-shrink-0 ml-2',
                'rounded-lg hover:bg-primary/10',
              )}
            >
              <MessageSquarePlus />
            </Button>
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto px-2" ref={scrollContainerRef}>
        {isLoadingChats ? (
          <div className="flex items-center justify-center p-4">
            <Loader2 className="icon-sm animate-spin text-muted-foreground mr-2" />
            <p className="text-sm text-muted-foreground">Loading chats...</p>
          </div>
        ) : filteredChats.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-4 gap-2">
            {searchQuery ? (
              <p className="text-sm text-muted-foreground">
                No matching chats found
              </p>
            ) : (
              !isCollapsed && (
                <p className="text-sm text-muted-foreground text-center">
                  No chat history
                </p>
              )
            )}
          </div>
        ) : (
          !isCollapsed && (
            <div className="space-y-2">
              {groupedChats.today.length > 0 && (
                <div>
                  <h3 className="px-3 py-4 text-xs font-bold text-primary dark:text-muted-foreground select-none">
                    Today
                  </h3>
                  <div className="space-y-1">
                    {groupedChats.today.map((chat) => (
                      <ChatItem
                        key={chat.chat_id}
                        chat={chat}
                        isActive={chat.chat_id === activeChatId}
                        onClick={handleChatItemClick}
                      />
                    ))}
                  </div>
                </div>
              )}

              {groupedChats.thisWeek.length > 0 && (
                <div>
                  <h3 className="px-3 py-4 text-xs font-bold text-primary dark:text-muted-foreground select-none">
                    This Week
                  </h3>
                  <div className="space-y-1">
                    {groupedChats.thisWeek.map((chat) => (
                      <ChatItem
                        key={chat.chat_id}
                        chat={chat}
                        isActive={chat.chat_id === activeChatId}
                        onClick={handleChatItemClick}
                      />
                    ))}
                  </div>
                </div>
              )}

              {groupedChats.thisMonth.length > 0 && (
                <div>
                  <h3 className="px-3 py-4 mt-4 text-xs font-bold text-primary dark:text-muted-foreground select-none">
                    This Month
                  </h3>
                  <div className="space-y-1">
                    {groupedChats.thisMonth.map((chat) => (
                      <ChatItem
                        key={chat.chat_id}
                        chat={chat}
                        isActive={chat.chat_id === activeChatId}
                        onClick={handleChatItemClick}
                      />
                    ))}
                  </div>
                </div>
              )}

              {groupedChats.older.length > 0 && (
                <div>
                  <h3 className="px-3 py-4 mt-4 text-xs font-bold text-primary dark:text-muted-foreground select-none">
                    Older
                  </h3>
                  <div className="space-y-1">
                    {groupedChats.older.map((chat) => (
                      <ChatItem
                        key={chat.chat_id}
                        chat={chat}
                        isActive={chat.chat_id === activeChatId}
                        onClick={handleChatItemClick}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        )}
      </div>
    </div>
  );
}
