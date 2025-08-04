// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

'use client';

import { ChatSession } from '@/lib/types';
import { cn } from '@/lib/utils';
import {
  MessageSquare,
  Trash2,
  MoreHorizontal,
  Pencil,
  Check,
  X,
} from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useUpdateChat, useDeleteChat } from '@/hooks/use-chat-api';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface ChatItemProps {
  chat: ChatSession;
  isActive: boolean;
  onClick?: () => void;
}

export function ChatItem({ chat, isActive, onClick }: ChatItemProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [newTitle, setNewTitle] = useState(chat.title);
  const [isHovered, setIsHovered] = useState(false);
  const updateChatMutation = useUpdateChat();
  const deleteChatMutation = useDeleteChat();
  const router = useRouter();

  // Format the date to be more readable
  const formattedDate = new Date(chat.updated_at).toLocaleDateString(
    undefined,
    {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    },
  );

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setShowDeleteDialog(true);
  };

  const handleRename = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setNewTitle(chat.title);
    setIsRenaming(true);
  };

  const handleSaveRename = async (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }

    if (newTitle.trim() && newTitle !== chat.title) {
      await updateChatMutation.mutateAsync({
        chatId: chat.chat_id,
        request: { title: newTitle },
      });
    } else {
      setNewTitle(chat.title);
    }
    setIsRenaming(false);
  };

  const handleCancelRename = (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setNewTitle(chat.title);
    setIsRenaming(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveRename();
    } else if (e.key === 'Escape') {
      handleCancelRename();
    }
  };

  const confirmDelete = async () => {
    await deleteChatMutation.mutateAsync(chat.chat_id);
    setShowDeleteDialog(false);
    router.push('/');
  };

  return (
    <>
      <Link
        href={chat.chat_id === 'new' ? '/' : `/chat/${chat.chat_id}`}
        className={cn(
          'group flex flex-col gap-1 px-3 py-1 text-sm transition-all rounded-md',
          isActive
            ? 'bg-primary/10 dark:bg-card'
            : 'hover:bg-primary/10 hover:dark:bg-card',
          'transition-all duration-200',
        )}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onClick={onClick}
      >
        <div className="flex items-center gap-2">
          {isRenaming ? (
            <div
              className="flex-1 flex items-center gap-2"
              onClick={(e) => e.preventDefault()}
            >
              <Input
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onKeyDown={handleKeyDown}
                className="h-7 w-full"
                autoFocus
                onClick={(e) => e.preventDefault()}
              />
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                onClick={handleSaveRename}
              >
                <Check className="h-3 w-3" />
                <span className="sr-only">Save</span>
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                onClick={handleCancelRename}
              >
                <X className="h-3 w-3" />
                <span className="sr-only">Cancel</span>
              </Button>
            </div>
          ) : (
            <span className="flex-1 truncate font-medium">{chat.title}</span>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className={cn(
                  'hover:cursor-pointer border-0 focus:ring-0 focus-visible:ring-0',
                  isHovered || isActive ? 'opacity-100' : 'opacity-0',
                )}
                aria-label="Chat options"
              >
                <MoreHorizontal className="text-muted-foreground" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="">
              <DropdownMenuItem onClick={handleRename}>
                <Pencil className="icon-sm mr-3" />
                <p>Rename</p>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={handleDelete}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="icon-sm mr-3" />
                <p>Delete</p>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </Link>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className={cn('dialog-startup')}>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Chat</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this chat? This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className={cn('rounded-lg')}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className={cn(
                'bg-destructive text-destructive-foreground hover:bg-destructive/90 rounded-lg',
              )}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
