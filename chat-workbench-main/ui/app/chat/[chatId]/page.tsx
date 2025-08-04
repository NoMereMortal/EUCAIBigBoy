// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import { Chat } from '@/components/chat/chat';

export default async function ChatPage({
  params,
}: {
  params: Promise<{ chatId: string }>;
}) {
  // Get the chatId from params
  const resolvedParams = await params;
  const chatId = resolvedParams.chatId;

  // Pass the chatId to the Chat component, which will update the store
  return <Chat chatId={chatId} />;
}
