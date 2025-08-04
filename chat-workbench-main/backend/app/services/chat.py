# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Chat service implementation."""

from typing import Any, Literal

from loguru import logger

from app.models import (
    ChatSession,
    CitationPart,
    DocumentPart,
    ImagePart,
    ListChatSessions,
    Message,
    MessagePart,
    ModelRequest,
    ModelResponse,
    PartType,
    ReasoningPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from app.monitoring import OperationMonitor
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.services.event_utils import process_event, process_part_from_events
from app.utils import generate_nanoid


class ChatServiceError(Exception):
    """Base exception for chat service errors."""

    pass


class ChatNotFoundError(ChatServiceError):
    """Exception raised when a chat is not found."""

    pass


class MessageNotFoundError(ChatServiceError):
    """Exception raised when a message is not found."""

    pass


class ChatService:
    """Service for chat operations.

    This service acts as a complete abstraction layer over the message and chat repositories,
    providing a unified interface for all chat-related operations.
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        chat_repo: ChatRepository,
    ):
        """Initialize chat service.

        Args:
            message_repo: Repository for message operations
            chat_repo: Repository for chat operations
        """
        self.message_repo = message_repo
        self.chat_repo = chat_repo
        self.monitor = OperationMonitor('chat_service')

    def _validate_and_convert_parts(self, message_parts: list[Any]) -> list[PartType]:
        """Validate and convert message parts to PartType instances.

        This ensures all parts are properly typed instances of MessagePart subclasses,
        not just dictionaries with the right structure.

        Args:
            message_parts: List of message parts to validate and convert

        Returns:
            List of validated PartType instances
        """
        validated_parts: list[PartType] = []

        for part in message_parts:
            # Skip None parts
            if part is None:
                logger.warning('Skipping None part in message parts')
                continue

            try:
                # If it's already a MessagePart subclass, ensure it's converted to its proper subtype
                if isinstance(part, MessagePart):
                    logger.warning(
                        f'Got generic MessagePart with kind {part.part_kind}, converting to proper type'
                    )
                    # Convert generic MessagePart to specific type based on part_kind
                    part_data = (
                        part.model_dump()
                        if hasattr(part, 'model_dump')
                        else part.dict()
                    )
                    part_kind = part.part_kind

                    # Create appropriate specific part type
                    if part_kind == 'text':
                        validated_parts.append(TextPart(**part_data))
                    elif part_kind == 'image':
                        validated_parts.append(ImagePart(**part_data))
                    elif part_kind == 'document':
                        validated_parts.append(DocumentPart(**part_data))
                    elif part_kind == 'tool-call':
                        validated_parts.append(ToolCallPart(**part_data))
                    elif part_kind == 'tool-return':
                        validated_parts.append(ToolReturnPart(**part_data))
                    elif part_kind == 'reasoning':
                        validated_parts.append(ReasoningPart(**part_data))
                    elif part_kind == 'citation':
                        validated_parts.append(CitationPart(**part_data))
                    else:
                        # Fallback to TextPart for unknown part_kind
                        logger.warning(
                            f"Unknown part_kind '{part_kind}' in MessagePart, converting to TextPart"
                        )
                        content = (
                            part.content if hasattr(part, 'content') else str(part)
                        )
                        validated_parts.append(TextPart(content=content))

                continue

                # If it's a dict, convert it to the appropriate PartType based on part_kind
                if isinstance(part, dict):
                    part_kind = part.get('part_kind')

                    if not part_kind:
                        # Default to TextPart if no part_kind is specified
                        logger.warning(
                            f'No part_kind specified for part, defaulting to text: {part}'
                        )
                        if 'content' in part:
                            validated_parts.append(TextPart(content=part['content']))
                        continue

                    # Create the appropriate PartType subclass based on part_kind
                    if part_kind == 'text':
                        validated_parts.append(TextPart(**part))
                    elif part_kind == 'image':
                        validated_parts.append(ImagePart(**part))
                    elif part_kind == 'document':
                        validated_parts.append(DocumentPart(**part))
                    elif part_kind == 'tool-call':
                        validated_parts.append(ToolCallPart(**part))
                    elif part_kind == 'tool-return':
                        validated_parts.append(ToolReturnPart(**part))
                    elif part_kind == 'reasoning':
                        validated_parts.append(ReasoningPart(**part))
                    elif part_kind == 'citation':
                        validated_parts.append(CitationPart(**part))
                    else:
                        logger.warning(
                            f"Unknown part_kind '{part_kind}', defaulting to text"
                        )
                        if 'content' in part:
                            validated_parts.append(TextPart(content=part['content']))
                else:
                    # If it's not a dict or MessagePart, try to convert it to a string
                    logger.warning(
                        f'Unknown part type {type(part).__name__}, converting to text'
                    )
                    validated_parts.append(TextPart(content=str(part)))
            except Exception as e:
                logger.error(f'Error validating part: {e}. Part: {part}')
                # Add placeholder part to avoid losing data
                try:
                    # Try to capture as much of the original part content as possible
                    content = ''
                    if isinstance(part, dict) and 'content' in part:
                        content = str(part['content'])
                    elif hasattr(part, 'content'):
                        content = str(part.content)
                    else:
                        content = str(part)

                    # Append with error info
                    validated_parts.append(
                        TextPart(
                            content=f'[Error validating part: {e!s}] {content[:100]}...'
                            if len(content) > 100
                            else content
                        )
                    )
                except Exception as e:
                    # Last resort fallback
                    validated_parts.append(
                        TextPart(content='[Error validating message part]')
                    )

        # Log the count of each type of part after validation
        part_type_counts = {}
        for part in validated_parts:
            part_type = type(part).__name__
            if part_type not in part_type_counts:
                part_type_counts[part_type] = 0
            part_type_counts[part_type] += 1

        logger.debug(f'Part types after validation: {part_type_counts}')

        return validated_parts

    async def start(
        self,
        chat_id: str,
        parent_id: str,
        message_parts: list[Any],
    ) -> Message:
        """Initialize a request.

        This method:
        1. Verifies the chat and parent message exist
        2. Creates a new user request message in the database
        3. Validates and converts message parts to proper types

        Args:
            chat_id: The ID of the chat
            parent_id: The ID of the parent message
            message_parts: List of message parts to include in the message

        Returns:
            The created message

        Raises:
            ChatNotFoundError: If the chat is not found
            MessageNotFoundError: If the parent message is not found
        """
        with self.monitor.operation('start'):
            # Verify the chat exists
            chat = await self.chat_repo.get_chat(chat_id)
            if not chat:
                logger.error(f'Chat {chat_id} not found')
                raise ChatNotFoundError(f'Chat {chat_id} not found')

            # If parent_id is not the chat_id, verify it exists
            if parent_id != chat_id:
                parent = await self.message_repo.get_message(chat_id, parent_id)
                if not parent:
                    logger.error(
                        f'Parent message {parent_id} not found in chat {chat_id}'
                    )
                    raise MessageNotFoundError(f'Parent message {parent_id} not found')

            # We don't need to fetch the conversation path in start anymore

            # Create new message with validated parts
            message_id = generate_nanoid()
            logger.debug(f'New message ID: {message_id}')

            # Validate and convert parts to proper types
            validated_parts = self._validate_and_convert_parts(message_parts)
            logger.debug(
                f'Validated {len(validated_parts)} parts for message {message_id}'
            )

            message = ModelRequest(
                message_id=message_id,
                chat_id=chat_id,
                parent_id=parent_id,
                status='pending',
                parts=validated_parts,  # Use validated parts
            )

            # Save the message to the database
            await self.message_repo.create_message(message)

            logger.info(
                f'Started new request: chat_id={chat_id}, message_id={message.message_id}'
            )
            return message

    async def stop(self, chat_id: str, message_id: str) -> Message:
        """Halt an in-progress request.

        This method:
        1. Records final message data
        2. Updates status to 'user_stopped'

        Args:
            chat_id: The ID of the chat
            message_id: The ID of the message to stop

        Returns:
            The updated message

        Raises:
            ChatNotFoundError: If the chat is not found
            MessageNotFoundError: If the message is not found
        """
        with self.monitor.operation('stop'):
            # Get the message
            message = await self.message_repo.get_message(chat_id, message_id)
            if not message:
                logger.error(f'Message {message_id} not found in chat {chat_id}')
                raise MessageNotFoundError(f'Message {message_id} not found')

            # Update status
            message.status = 'user_stopped'

            # Save the updated message
            success = await self.message_repo.save_message(message)
            if not success:
                logger.error(f'Failed to save message {message_id} after stop')
                raise ChatServiceError('Failed to update message status')

            logger.info(f'Stopped request: chat_id={chat_id}, message_id={message_id}')
            return message

    async def complete(
        self,
        chat_id: str,
        message_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """Record final message and completion status.

        This method:
        1. Records final message content
        2. Updates message metadata
        3. Sets status to 'complete'

        If the message doesn't exist, it will create it with the provided content.

        Args:
            chat_id: The ID of the chat
            message_id: The ID of the message to complete
            content: The accumulated content of the message (optional)
            metadata: Additional metadata to attach to the message (optional)

        Returns:
            The updated message
        """
        with self.monitor.operation('complete'):
            # Try to get the message
            message = await self.message_repo.get_message(chat_id, message_id)

            # If message doesn't exist, create it
            if not message:
                logger.info(
                    f'Message {message_id} not found in chat {chat_id}, creating it'
                )

                # We need to find a valid parent_id
                # Use the most recent message or chat_id as fallback
                parent_id = chat_id
                recent_messages = await self.message_repo.get_chat_messages(chat_id)
                if recent_messages and len(recent_messages) > 0:
                    # Use the last request message as parent (it's what triggered this response)
                    for msg in reversed(recent_messages):
                        if msg.kind == 'request':
                            parent_id = msg.message_id
                            break

                # Create parts from the content if provided
                parts: list[PartType] = []
                if content:
                    parts = [TextPart(content=content)]

                # Create a new response message
                message = ModelResponse(
                    message_id=message_id,
                    chat_id=chat_id,
                    parent_id=parent_id,
                    status='pending',
                    parts=parts,
                    kind='response',  # Make sure it's marked as a response
                )

                # Save the new message
                await self.message_repo.create_message(message)
            elif content and not message.parts:
                # If message exists but doesn't have parts and content is provided, add content
                message.parts = [TextPart(content=content)]  # type: ignore

            # Update status
            message.status = 'complete'
            message.metadata = metadata if metadata else {}

            # Save the updated message
            success = await self.message_repo.save_message(message)
            if not success:
                logger.error(f'Failed to save message {message_id} after completion')
                raise ChatServiceError('Failed to update message')

            logger.info(
                f'Completed request: chat_id={chat_id}, message_id={message_id}'
            )
            return message

    async def error(
        self,
        chat_id: str,
        message_id: str,
        error_info: dict[str, Any],
        content: str | None = None,
    ) -> Message:
        """Record error and error status.

        This method:
        1. Records error information and any accumulated content
        2. Updates message status to 'error'

        If the message doesn't exist, it will create it with the provided content
        or the error message as content.

        Args:
            chat_id: The ID of the chat
            message_id: The ID of the message to mark as error
            error_info: Information about the error
            content: Any accumulated content to save (optional)

        Returns:
            The updated message
        """
        with self.monitor.operation('error'):
            # Try to get the message
            message = await self.message_repo.get_message(chat_id, message_id)

            # Extract error message to use as fallback content
            error_message = error_info.get('message', 'An error occurred')

            # If message doesn't exist, create it
            if not message:
                logger.info(
                    f'Message {message_id} not found in chat {chat_id}, creating it as error'
                )

                # We need to find a valid parent_id
                # Use the most recent message or chat_id as fallback
                parent_id = chat_id
                recent_messages = await self.message_repo.get_chat_messages(chat_id)
                if recent_messages and len(recent_messages) > 0:
                    # Use the last request message as parent
                    for msg in reversed(recent_messages):
                        if msg.kind == 'request':
                            parent_id = msg.message_id
                            break

                # Create parts from the content or use error message if no content
                parts: list[PartType] = []
                if content:
                    parts = [TextPart(content=content)]
                else:
                    parts = [TextPart(content=error_message)]

                # Create a new response message
                message = ModelResponse(
                    message_id=message_id,
                    chat_id=chat_id,
                    parent_id=parent_id,
                    status='error',  # Set status to error right away
                    parts=parts,
                    kind='response',  # Make sure it's marked as a response
                )

                # Save the new message
                await self.message_repo.create_message(message)
            elif not message.parts or len(message.parts) == 0:
                # If message exists but has no parts, add the error message as content
                message.parts = [TextPart(content=error_message)]  # type: ignore
            elif content and not message.parts:
                message.parts = [TextPart(content=content)]  # type: ignore

            # Update metadata with error info
            error_metadata = {'error': error_info}

            # Update status
            message.status = 'error'
            message.metadata = error_metadata

            # Save the updated message
            success = await self.message_repo.save_message(message)
            if not success:
                logger.error(f'Failed to save message {message_id} after error')
                raise ChatServiceError('Failed to update message with error')

            logger.info(
                f'Request error: chat_id={chat_id}, message_id={message_id}, error={error_info}'
            )
            return message

    async def get(self, chat_id: str) -> list[Message]:
        """Retrieve full message history for UI display.

        This method:
        1. Retrieves all messages for a chat (including all siblings/branches)
        2. Filters out empty messages and system prompt parts
        3. Does not resolve pointers

        Args:
            chat_id: The ID of the chat

        Returns:
            List of messages for UI display

        Raises:
            ChatNotFoundError: If the chat is not found
        """
        with self.monitor.operation('get'):
            # Verify the chat exists
            chat = await self.chat_repo.get_chat(chat_id)
            if not chat:
                logger.error(f'Chat {chat_id} not found')
                raise ChatNotFoundError(f'Chat {chat_id} not found')

            # Retrieve all messages for the chat
            all_messages = await self.message_repo.get_chat_messages(chat_id)

            # Filter out empty messages
            messages = [msg for msg in all_messages if msg.parts]

            # Filter out system prompt parts from message parts
            for message in messages:
                if hasattr(message, 'parts') and message.parts:
                    # Keep all parts except system prompts
                    filtered_parts = []
                    for part in message.parts:
                        if (
                            hasattr(part, 'part_kind')
                            and part.part_kind != 'system-prompt'
                        ):
                            filtered_parts.append(part)
                    message.parts = filtered_parts

            logger.info(f'Retrieved {len(messages)} messages for chat {chat_id}')
            return messages

    async def get_conversation_path(
        self,
        chat_id: str,
        message_id: str,
    ) -> list[Message]:
        """Get the conversation path from root to a message.

        This method:
        1. Retrieves the linear path from root to the specified message
        2. Includes system prompts (needed for model context)

        Args:
            chat_id: The ID of the chat
            message_id: The ID of the message to trace back from

        Returns:
            List of messages in the conversation path from root to message_id

        Raises:
            ChatNotFoundError: If the chat is not found
            MessageNotFoundError: If the message is not found
        """
        with self.monitor.operation('get_conversation_path'):
            # Verify the chat exists
            chat = await self.chat_repo.get_chat(chat_id)
            if not chat:
                logger.error(f'Chat {chat_id} not found')
                raise ChatNotFoundError(f'Chat {chat_id} not found')

            # Get the conversation path from the repository
            conversation_path = await self.message_repo.get_conversation_path(
                chat_id, message_id
            )

            if not conversation_path and message_id != chat_id:
                logger.error(f'Message {message_id} not found in chat {chat_id}')
                raise MessageNotFoundError(f'Message {message_id} not found')

            logger.info(
                f'Retrieved conversation path with {len(conversation_path)} messages for chat {chat_id}'
            )
            return conversation_path

    # ----- Chat Management Methods -----

    async def create_chat(
        self,
        title: str,
        user_id: str = 'anonymous',
        metadata: dict[str, Any] | None = None,
    ) -> ChatSession | None:
        """Create a new chat session.

        Args:
            title: The title of the chat
            user_id: The ID of the user who owns the chat
            metadata: Additional metadata to attach to the chat

        Returns:
            The created chat session
        """
        with self.monitor.operation('create_chat'):
            chat = ChatSession(title=title, user_id=user_id, metadata=metadata or {})

            result = await self.chat_repo.create_chat(chat)
            if result:
                logger.info(
                    f"Created new chat: {result.chat_id}, title='{title}', user='{user_id}'"
                )
            else:
                logger.error(
                    f"Failed to create chat: title='{title}', user='{user_id}'"
                )
            return result

    async def get_chat(self, chat_id: str) -> ChatSession | None:
        """Get a chat by ID without messages.

        Args:
            chat_id: The ID of the chat to retrieve

        Returns:
            The chat session or None if not found
        """
        with self.monitor.operation('get_chat'):
            chat = await self.chat_repo.get_chat(chat_id)
            if not chat:
                logger.warning(f'Chat {chat_id} not found')
                return None

            return chat

    async def get_chat_with_messages(self, chat_id: str) -> ChatSession | None:
        """Get a chat by ID with its message history.

        Args:
            chat_id: The ID of the chat to retrieve

        Returns:
            The chat session with messages or None if not found
        """
        with self.monitor.operation('get_chat_with_messages'):
            # First get the chat
            chat = await self.get_chat(chat_id)
            if not chat:
                return None

            # Then get messages
            try:
                messages = await self.get(chat_id)
                chat.messages = messages
            except ChatNotFoundError:
                # This shouldn't happen since we just confirmed the chat exists
                logger.error(
                    f'Inconsistent state: Chat {chat_id} found but then not found when getting messages'
                )

            return chat

    async def update_chat(
        self,
        chat_id: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
        status: Literal['active', 'archived', 'deleted'] | None = None,
    ) -> ChatSession | None:  # Explicitly allowing None as return value
        """Update a chat's properties.

        Args:
            chat_id: The ID of the chat to update
            title: New title for the chat (optional)
            metadata: New metadata to merge with existing metadata (optional)
            status: New status for the chat (optional)

        Returns:
            The updated chat session or None if not found
        """
        with self.monitor.operation('update_chat'):
            # Get existing chat
            chat = await self.chat_repo.get_chat(chat_id)
            if not chat:
                logger.warning(f'Chat {chat_id} not found for update')
                return None

            # Track what was updated
            updated_fields = []

            # Update metadata if provided
            if metadata is not None:
                updated_metadata = {**chat.metadata, **metadata}
                await self.chat_repo.update_chat_metadata(chat_id, updated_metadata)
                updated_fields.append('metadata')

            # Update status if provided
            if status is not None:
                chat.status = status
                updated_fields.append('status')
                # Will be saved below if title is also updated

            # Update title if provided
            if title is not None:
                chat.title = title
                updated_fields.append('title')

            # Save the chat if title or status was updated
            if title is not None or status is not None:
                await self.chat_repo.create_chat(chat)

            # Log the update
            if updated_fields:
                logger.info(
                    f'Updated chat {chat_id}: changed {", ".join(updated_fields)}'
                )

            # Fetch and return the updated chat
            return await self.chat_repo.get_chat(chat_id)

    async def list_chats(
        self,
        user_id: str | None = None,
        status: str = 'active',
        limit: int = 100,
        last_key: dict[str, Any] | None = None,
        with_messages: int = 0,
    ) -> ListChatSessions:
        """List chats with pagination.

        Args:
            user_id: Filter by user ID (optional)
            status: Filter by status ('active', 'archived', 'deleted')
            limit: Maximum number of chats to return
            last_key: Last evaluated key for pagination
            with_messages: Number of recent chats to include messages for (0 to disable)

        Returns:
            Object containing chat list and pagination info
        """
        with self.monitor.operation('list_chats'):
            if not user_id:
                logger.warning(
                    'list_chats called without user_id, returning empty result'
                )
                return ListChatSessions(chats=[], last_evaluated_key=None)

            # Get list of chats without messages first
            result = await self.chat_repo.list_chats(
                user_id=user_id,
                status=status,
                limit=limit,
                last_key=last_key,
                with_messages=0,  # Always 0 here, we'll handle messages separately
                message_repo=self.message_repo,
            )

            # If we need to include messages for some chats
            if with_messages > 0 and result.chats:
                # Get messages for the most recent chats
                chats_with_messages = result.chats[
                    : min(with_messages, len(result.chats))
                ]

                for chat in chats_with_messages:
                    try:
                        # Make sure chat is not None before accessing chat_id
                        if (
                            chat is not None
                            and hasattr(chat, 'chat_id')
                            and chat.chat_id
                        ):
                            messages = await self.get(chat.chat_id)
                            chat.messages = messages
                        else:
                            logger.warning(
                                'Chat object is None or missing chat_id attribute'
                            )
                    except Exception as e:
                        # Log error but continue with other chats
                        chat_id = getattr(chat, 'chat_id', 'unknown')
                        logger.error(
                            f'Error retrieving messages for chat {chat_id}: {e!s}'
                        )

            return result

    async def delete_chat(self, chat_id: str) -> ChatSession | None:
        """Mark a chat as deleted (soft delete).

        Args:
            chat_id: The ID of the chat to delete

        Returns:
            The updated chat session or None if not found
        """
        with self.monitor.operation('delete_chat'):
            return await self.update_chat(chat_id, status='deleted')

    # Method aliases for backward compatibility
    def process_part_from_events(self, events: list[Any]) -> PartType | None:
        """Alias for the event_utils.process_part_from_events function."""
        return process_part_from_events(events)

    process_part = process_part_from_events

    async def process_event(self, event: Any, streaming_service=None) -> bool:
        """Alias for the event_utils.process_event function."""
        return await process_event(self, event, streaming_service)
