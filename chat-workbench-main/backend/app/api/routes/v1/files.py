# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

# backend/app/api/routes/v1/files.py

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.dependencies import (
    get_client_registry,
    get_dynamodb_client,
)
from app.api.dependencies.auth import get_user_id_from_header
from app.clients.registry import ClientRegistry
from app.clients.s3.client import S3Client
from app.config import Settings
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.services.content_storage import ContentStorageService
from app.services.model_capabilities import ModelCapabilities

logger = logging.getLogger(__name__)


# Models for file handling
class FileInfo(BaseModel):
    """Model for file information returned from uploads."""

    file_id: str
    mime_type: str
    filename: str
    file_type: str  # "image", "document", or "audio"
    format: str | None = None  # Format usable by Bedrock (jpeg, png, pdf, etc.)


class FileUploadResponse(BaseModel):
    """Response model for file uploads."""

    files: list[FileInfo]


# Create router
router = APIRouter(tags=['Content Management'])


async def get_content_storage(
    settings: Settings = Depends(lambda: Settings()),
    client_registry: ClientRegistry = Depends(get_client_registry),
) -> ContentStorageService:
    """Get content storage service."""
    # Get clients with proper async handling
    s3_client: S3Client | None = None
    valkey_client = None

    # Get S3 client with availability check
    s3_result = await client_registry.get_typed_client('s3', S3Client)
    if s3_result:
        s3_client, is_available = s3_result
        if not is_available:
            logger.warning('S3 client found but not fully initialized')

    # Get Valkey client with availability check
    valkey_result = await client_registry.get_client('valkey')
    if valkey_result:
        valkey_client, valkey_available = valkey_result
        if not valkey_available:
            logger.warning('Valkey client found but not fully initialized')

    if not s3_client:
        raise HTTPException(
            status_code=500,
            detail='No storage client available. Please check your configuration.',
        )

    return ContentStorageService(
        settings=settings,
        s3_client=s3_client,
        valkey_client=valkey_client,
    )


async def get_repositories(
    dynamodb_client_result=Depends(get_dynamodb_client()),
) -> tuple[MessageRepository, ChatRepository]:
    """Get message and chat repositories."""
    # Extract client and availability from result tuple
    dynamodb_client, is_available = dynamodb_client_result

    if not is_available:
        logger.warning(
            'DynamoDB client not fully initialized - repositories may have limited functionality'
        )

    message_repo = MessageRepository(dynamodb_client)
    chat_repo = ChatRepository(dynamodb_client)
    return message_repo, chat_repo


@router.post(
    '/',
    summary='Upload files',
    description='Upload files to be used in chat messages',
    response_model=FileUploadResponse,
)
async def upload_files(
    files: Annotated[list[UploadFile], File()],
    content_storage: Annotated[ContentStorageService, Depends(get_content_storage)],
    repos: Annotated[
        tuple[MessageRepository, ChatRepository], Depends(get_repositories)
    ],
    user_id: Annotated[str, Depends(get_user_id_from_header)],
    chat_id: Annotated[str | None, Form()] = None,
    model_id: Annotated[str | None, Form()] = None,
) -> FileUploadResponse:
    """Upload files and get file IDs that can be used in messages.

    User ID is required for file ownership tracking.
    """
    message_repo, chat_repo = repos

    # Validate chat ID by checking if it exists (if provided)
    if chat_id and not (chat_id.startswith('temp-') or chat_id.startswith('new-')):
        try:
            # Check if chat exists
            chat = await chat_repo.get_chat(chat_id)
            if not chat:
                raise HTTPException(status_code=400, detail=f'Chat {chat_id} not found')
        except Exception:
            # If error occurs (like permissions issues), log but continue
            logger.warning('Error checking chat existence', exc_info=True)

    file_infos = []

    for file in files:
        # Get content type, defaulting to application/octet-stream if not provided
        content_type = file.content_type or 'application/octet-stream'

        # Log the file upload with content type
        logger.info(
            f'Processing file upload: {file.filename} with content type: {content_type}'
        )

        # Validate file size
        file_size_limit = min(
            ModelCapabilities.get_size_limit(content_type), 4 * 1024 * 1024
        )  # 4MB limit

        file_bytes = await file.read(file_size_limit + 1)
        if len(file_bytes) > file_size_limit:
            raise HTTPException(
                status_code=400,
                detail=f'File {file.filename} exceeds size limit of {file_size_limit} bytes (4MB maximum)',
            )

        # Check if model_id is specified and validate content type is supported
        if model_id and not ModelCapabilities.is_supported(model_id, content_type):
            raise HTTPException(
                status_code=400,
                detail=f'Model {model_id} does not support content type: {content_type}',
            )

        # Determine file type and format based on mime type
        file_type = 'document'
        format_name = None

        if content_type.startswith('image/'):
            file_type = 'image'
            # Determine image format for Bedrock
            if content_type == 'image/jpeg':
                format_name = 'jpeg'
            elif content_type == 'image/png':
                format_name = 'png'
            elif content_type == 'image/gif':
                format_name = 'gif'
            elif content_type == 'image/webp':
                format_name = 'webp'
            else:
                logger.warning(
                    f'Unsupported image type: {content_type}, will use string media_type'
                )

        elif content_type in {'audio/wav', 'audio/mpeg'}:
            file_type = 'audio'
            # Determine audio format for Bedrock
            if content_type == 'audio/mpeg':
                format_name = 'mp3'
            elif content_type == 'audio/wav':
                format_name = 'wav'

        elif content_type in {
            'application/pdf',
            'text/plain',
            'text/csv',
            'text/html',
            'text/markdown',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel',
        }:
            file_type = 'document'
            # Determine document format for Bedrock
            if content_type == 'application/pdf':
                format_name = 'pdf'
            elif content_type == 'text/plain':
                format_name = 'txt'
            elif content_type == 'text/csv':
                format_name = 'csv'
            elif (
                content_type
                == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ):
                format_name = 'docx'
            elif (
                content_type
                == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ):
                format_name = 'xlsx'
            elif content_type == 'text/html':
                format_name = 'html'
            elif content_type == 'text/markdown':
                format_name = 'md'
            elif content_type == 'application/vnd.ms-excel':
                format_name = 'xls'

        # Prepare metadata including format and user information
        metadata = {
            'filename': file.filename,
            'user_id': user_id,  # Add user ID to metadata for ownership tracking
        }

        if chat_id:
            metadata['chat_id'] = chat_id

        if format_name:
            metadata['format'] = format_name

        # Store the file with format and user metadata
        file_pointer = await content_storage.store_content(
            user_id=user_id,  # Store with user ID as primary path component
            content=file_bytes,
            mime_type=content_type,
            metadata=metadata,
        )

        # Create response info with file ID
        filename = file.filename or 'unnamed_file'  # Provide a default if None
        file_info = FileInfo(
            file_id=file_pointer.file_id,
            mime_type=content_type,
            filename=filename,
            file_type=file_type,
            format=format_name,
        )
        file_infos.append(file_info)

    return FileUploadResponse(files=file_infos)


@router.get(
    '/{file_id}',
    summary='Retrieve file content',
    description='Get file content by file ID',
    response_class=StreamingResponse,
    responses={
        200: {
            'description': 'File content',
            'content': {
                'application/octet-stream': {
                    'schema': {'type': 'string', 'format': 'binary'}
                }
            },
        }
    },
)
async def get_file(
    file_id: str,
    user_id: Annotated[str, Depends(get_user_id_from_header)],
    content_storage: Annotated[ContentStorageService, Depends(get_content_storage)],
):
    """Retrieve file content from storage.

    Validates that the requesting user has access to the file.
    """
    # Retrieve content
    content, mime_type = await content_storage.get_content_from_id(file_id, user_id)

    if content is None:
        raise HTTPException(
            status_code=404, detail='File not found, expired, or you do not have access'
        )

    # Setup cache headers - content can be cached for up to 1 day
    headers = {
        'Cache-Control': 'public, max-age=86400',
    }

    # Return as streaming response with proper content type
    return StreamingResponse(iter([content]), media_type=mime_type, headers=headers)
