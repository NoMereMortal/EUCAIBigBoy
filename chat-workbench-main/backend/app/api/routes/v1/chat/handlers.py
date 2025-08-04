# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from typing import Any

from app.api.routes.v1.chat.models import CreateChatRequest, UpdateChatRequest
from app.models import ChatSession, ListChatSessions
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.services.chat import ChatService


async def handle_create_chat(
    chat_repo: ChatRepository,
    request: CreateChatRequest,
    chat_service: ChatService | None = None,
) -> ChatSession | None:
    """Create a new chat session."""
    from loguru import logger

    # Ensure user_id is a string and not None
    user_id = request.user_id if request.user_id is not None else 'anonymous'

    # Use ChatService if available
    if chat_service:
        logger.info(
            f"Using ChatService to create chat with title '{request.title}' for user {user_id}"
        )
        return await chat_service.create_chat(
            title=request.title, user_id=user_id, metadata=request.metadata
        )

    # Otherwise fall back to direct repository access
    logger.warning(
        'ChatService not available for chat creation, using direct repository access'
    )
    chat = ChatSession(title=request.title, user_id=user_id, metadata=request.metadata)
    return await chat_repo.create_chat(chat)


async def handle_get_chat(
    chat_repo: ChatRepository,
    chat_id: str,
    message_repo: MessageRepository | None = None,
    chat_service: ChatService | None = None,
) -> dict[str, Any] | None:
    """Get a chat session by ID with message history."""
    from loguru import logger

    logger.info(f'Fetching chat with ID: {chat_id}')

    # Use ChatService if available
    if chat_service:
        logger.info(f'Using ChatService to get chat {chat_id} with messages')
        chat = await chat_service.get_chat_with_messages(chat_id)
        if not chat:
            logger.warning(f'Chat {chat_id} not found')
            return None

        return chat.model_dump()

    # Otherwise fall back to direct repository access
    logger.warning('ChatService not available, using direct repository access')

    # Check if the chat exists
    chat = await chat_repo.get_chat(chat_id)
    if not chat:
        logger.warning(f'Chat not found: {chat_id}')
        return None

    result = chat.model_dump()
    logger.info(f'Found chat: {chat.title} (ID: {chat_id})')

    # If there's no message_repo, we can't get messages
    if message_repo is None:
        logger.warning(
            'MessageRepository not available, returning chat without messages'
        )
        result['messages'] = []
        return result

    # Get messages directly
    try:
        messages = await message_repo.get_chat_messages(chat_id)
        result['messages'] = messages
        logger.info(f'Retrieved {len(messages)} messages directly from repository')
    except Exception as e:
        logger.error(f'Error retrieving messages: {e!s}')
        result['messages'] = []

    return result


async def handle_list_chats(
    chat_repo: ChatRepository,
    user_id: str | None = None,
    status: str = 'active',
    limit: int = 100,
    last_key: dict[str, Any] | None = None,
    message_repo: MessageRepository | None = None,
    with_messages: int = 5,
    chat_service: ChatService | None = None,
) -> ListChatSessions:
    """List chat sessions with pagination.

    If with_messages > 0, includes messages for the N most recent chats.
    """
    from loguru import logger

    # If chat_service is available, use it
    if chat_service:
        logger.info(f'Using ChatService to list chats for user {user_id}')
        return await chat_service.list_chats(
            user_id=user_id,
            status=status,
            limit=limit,
            last_key=last_key,
            with_messages=with_messages,
        )

    # Otherwise, fall back to direct repository access
    logger.warning(
        'ChatService not available for list_chats, falling back to direct repository access'
    )

    if not user_id:
        # Return empty result if no user ID provided
        return ListChatSessions(chats=[], last_evaluated_key=None)

    # We need message_repo to be non-null when using direct repository access
    if message_repo is None:
        logger.error('MessageRepository not available for direct repository access')
        return ListChatSessions(chats=[], last_evaluated_key=None)

    # Get chats from repository when we know message_repo is not None
    return await chat_repo.list_chats(
        user_id=user_id,
        status=status,
        limit=limit,
        last_key=last_key,
        with_messages=with_messages,
        message_repo=message_repo,
    )


async def handle_update_chat(
    chat_repo: ChatRepository,
    chat_id: str,
    request: UpdateChatRequest,
    chat_service: ChatService | None = None,
) -> ChatSession | None:
    """Update a chat session."""
    from loguru import logger

    # Use ChatService if available
    if chat_service:
        logger.info(f'Using ChatService to update chat {chat_id}')

        # Validate status is one of the allowed values
        status = None
        if request.status:
            if request.status in ('active', 'archived', 'deleted'):
                status = request.status
            else:
                logger.warning(
                    f'Invalid status value: {request.status}, using None instead'
                )

        return await chat_service.update_chat(
            chat_id=chat_id,
            title=request.title,
            metadata=request.metadata,
            status=status,  # Using validated status
        )

    # Otherwise fall back to direct repository access
    logger.warning('ChatService not available, using direct repository access')

    # Get existing chat
    chat = await chat_repo.get_chat(chat_id)
    if not chat:
        logger.warning(f'Chat {chat_id} not found')
        return None

    # Update metadata if provided
    if request.metadata is not None:
        updated_metadata = {**chat.metadata, **request.metadata}
        await chat_repo.update_chat_metadata(chat_id, updated_metadata)
        logger.info(f'Updated metadata for chat {chat_id}')

    # Update status if provided
    if request.status:
        chat.status = request.status
        await chat_repo.create_chat(chat)
        logger.info(f"Updated status to '{request.status}' for chat {chat_id}")

    # Update title if provided
    if request.title:
        chat.title = request.title
        await chat_repo.create_chat(chat)
        logger.info(f"Updated title to '{request.title}' for chat {chat_id}")

    # Fetch updated chat
    return await chat_repo.get_chat(chat_id)
