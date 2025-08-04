# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.dependencies import (
    get_auth_dependency,
    get_dynamodb_client,
)
from app.api.routes.v1.chat.models import CreateChatRequest, UpdateChatRequest
from app.clients.dynamodb.client import DynamoDBClient
from app.models import ChatSession, ListChatSessions
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.services.chat import ChatService

# Create router with our new auth dependencies
router = APIRouter(prefix='/chat', tags=['chat'], dependencies=get_auth_dependency())


def get_chat_repository(
    dynamodb_client: DynamoDBClient = Depends(get_dynamodb_client()),
) -> ChatRepository:
    """Get chat repository instance."""
    return ChatRepository(dynamodb_client)


def get_message_repository(
    dynamodb_client: DynamoDBClient = Depends(get_dynamodb_client()),
) -> MessageRepository:
    """Get message repository instance."""
    return MessageRepository(dynamodb_client)


def get_chat_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    message_repo: MessageRepository = Depends(get_message_repository),
) -> ChatService:
    """Get chat service instance."""
    return ChatService(message_repo=message_repo, chat_repo=chat_repo)


@router.post('')
async def create_chat(
    request: CreateChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatSession:
    """Create a new chat session."""
    # Use ChatService's create_chat method directly
    user_id = request.user_id if request.user_id is not None else 'anonymous'
    chat = await chat_service.create_chat(
        title=request.title, user_id=user_id, metadata=request.metadata
    )

    if not chat:
        raise HTTPException(status_code=500, detail='Failed to create chat')

    return chat


@router.get('/{chat_id}')
async def get_chat(
    chat_id: str,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatSession:
    """Get a chat session by ID with message history."""
    try:
        # Use the dedicated method to get a chat with its messages
        chat = await chat_service.get_chat_with_messages(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail='Chat not found')

        return chat
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f'Error retrieving chat: {e!s}'
        ) from e


@router.get('')
async def list_chats(
    request: Request,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    user_id: str | None = None,
    status: Annotated[str, Query(regex='^(active|archived|deleted)$')] = 'active',
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    last_key: str | None = None,
    with_messages: Annotated[int, Query(ge=0, le=10)] = 5,
) -> ListChatSessions:
    """List chat sessions with pagination.

    If with_messages > 0, includes messages for the N most recent chats.
    Uses authenticated user ID from request if user_id is not provided.
    """
    # Extract user_id from request state if not provided in query params
    if user_id is None and hasattr(request.state, 'user_id'):
        user_id = request.state.user_id

    # Parse the last_key if provided
    last_evaluated_key = json.loads(last_key) if last_key else None

    # Use ChatService.list_chats method directly
    return await chat_service.list_chats(
        user_id=user_id,
        status=status,
        limit=limit,
        last_key=last_evaluated_key,
        with_messages=with_messages,
    )


@router.put('/{chat_id}')
async def update_chat(
    chat_id: str,
    request: UpdateChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatSession:
    """Update a chat session."""
    # Validate status is one of the allowed values
    status = None
    if request.status:
        if request.status in ('active', 'archived', 'deleted'):
            status = request.status
        else:
            raise HTTPException(
                status_code=400, detail=f'Invalid status value: {request.status}'
            )

    # Use the ChatService update_chat method directly
    chat = await chat_service.update_chat(
        chat_id=chat_id, title=request.title, metadata=request.metadata, status=status
    )

    if not chat:
        raise HTTPException(status_code=404, detail='Chat not found')

    return chat


@router.delete('/{chat_id}')
async def delete_chat(
    chat_id: str, chat_service: Annotated[ChatService, Depends(get_chat_service)]
) -> ChatSession:
    """Mark a chat as deleted."""
    # Use the dedicated delete_chat method from ChatService
    chat = await chat_service.delete_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail='Chat not found')
    return chat  # Since we raise an exception if chat is None, this is safe
