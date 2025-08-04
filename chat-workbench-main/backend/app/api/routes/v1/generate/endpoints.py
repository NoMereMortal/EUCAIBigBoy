# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

import urllib.parse
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from fastapi.responses import StreamingResponse
from loguru import logger

from app.api.dependencies import (
    get_auth_dependency,
    get_client_registry,
    get_task_handler_registry,
)
from app.api.routes.v1.generate.handlers import (
    handle_generate_invoke,
    handle_generate_stream,
    handle_generate_websocket,
)
from app.api.routes.v1.generate.models import GenerateRequest, GenerateResponse
from app.clients.registry import ClientRegistry
from app.config import Settings
from app.services.chat import ChatService
from app.services.content_storage import ContentStorageService
from app.task_handlers.registry import TaskHandlerRegistry
from app.utils import generate_nanoid

router = APIRouter(prefix='/generate', tags=['Generate'])


async def get_chat_service(request: Request) -> ChatService:
    """Get chat service instance from app state.

    This ensures we use the same chat service instance across the application,
    which is important for consistent event processing.
    """
    # Return the pre-initialized chat service from app state
    return request.app.state.chat_service


async def get_content_storage(
    settings: Settings = Depends(lambda: Settings()),
    client_registry: ClientRegistry = Depends(get_client_registry),
) -> ContentStorageService:
    """Get content storage service."""
    from loguru import logger

    from app.clients.s3.client import S3Client

    # Log details about the client registry
    logger.info(
        f"Client registry: {client_registry}, has 's3': {'s3' in client_registry.get_client_names()}"
    )
    logger.info(f'Available clients: {client_registry.get_client_names()}')

    # Get the S3 client with enhanced logging
    s3_client_instance = None
    if 's3' in client_registry.get_client_names():
        base_client = client_registry.get_client('s3')
        # Ensure we have the right type
        if isinstance(base_client, S3Client):
            s3_client_instance = base_client
            logger.info(
                f'Retrieved S3 client: {s3_client_instance}, type={type(s3_client_instance).__name__}'
            )
            logger.info(
                f'S3 client initialized: {hasattr(s3_client_instance, "_client") and s3_client_instance._client is not None}'
            )
        else:
            logger.error(f'Expected S3Client but got {type(base_client).__name__}')
    else:
        logger.error('S3 client not found in registry! Document retrieval will fail.')

    # Get the Valkey client
    valkey_client = (
        client_registry.get_client('valkey')
        if 'valkey' in client_registry.get_client_names()
        else None
    )

    # Create the content storage service with detailed logging
    logger.info(
        f'Creating ContentStorageService with S3 client: {s3_client_instance is not None}'
    )

    # ContentStorageService requires a valid S3Client
    if s3_client_instance is None:
        logger.error(
            'Cannot create ContentStorageService: S3 client is required but not available'
        )
        raise ValueError(
            'S3 client is required for content storage service but is not available'
        )

    service = ContentStorageService(
        settings=settings,
        s3_client=s3_client_instance,
        valkey_client=valkey_client,
    )

    logger.info(f'ContentStorageService created: {service}')
    return service


# Example for docs
EXAMPLE_REQUEST = {
    'task': 'chat',
    'chat_id': generate_nanoid(),  # Will be auto-updated on docs load
    'model_id': 'us.anthropic.claude-3-5-sonnet-20240620-v1:0',
    'parent_id': generate_nanoid(),
    'parts': [
        {
            'part_kind': 'text',
            'content': 'Hello, can you help me with a Python question?',
        }
    ],
    'persona': 'You are a helpful Python expert',
}


@router.post(
    '/stream',
    summary='Generate a streaming response',
    description='Stream a response from an AI model with server-sent events',
    response_class=StreamingResponse,
    responses={
        200: {
            'description': 'Server-sent events stream',
            'content': {'text/event-stream': {'schema': {'type': 'string'}}},
        }
    },
    openapi_extra={
        'requestBody': {'content': {'application/json': {'example': EXAMPLE_REQUEST}}}
    },
)
async def generate_stream(
    request: Request,
    generate_req: GenerateRequest,
    task_registry: Annotated[TaskHandlerRegistry, Depends(get_task_handler_registry)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry)],
):
    """Stream a response from an AI model with server-sent events."""
    return await handle_generate_stream(
        generate_req,
        chat_service,
        task_registry,
        client_registry,
    )


@router.post(
    '/invoke',
    summary='Generate a complete response',
    description='Generate a complete response from an AI model',
    response_model=GenerateResponse,
    # Add example for docs
    openapi_extra={
        'requestBody': {'content': {'application/json': {'example': EXAMPLE_REQUEST}}}
    },
)
async def generate_invoke(
    request: Request,
    generate_req: GenerateRequest,
    task_registry: Annotated[TaskHandlerRegistry, Depends(get_task_handler_registry)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry)],
):
    """Generate a complete response from an AI model."""
    return await handle_generate_invoke(
        generate_req,
        chat_service,
        task_registry,
        client_registry,
    )


@router.get(
    '/content/{pointer_path:path}',
    summary='Retrieve binary content',
    description='Get binary content by pointer ID',
    dependencies=get_auth_dependency(),
    response_class=StreamingResponse,
    responses={
        200: {
            'description': 'Binary content',
            'content': {
                'application/octet-stream': {
                    'schema': {'type': 'string', 'format': 'binary'}
                }
            },
        }
    },
)
async def get_content(
    pointer_path: str,
    content_storage: Annotated[ContentStorageService, Depends(get_content_storage)],
) -> StreamingResponse:
    """Retrieve binary content from storage."""
    # Convert URL-safe pointer ID back to URI format
    uri = urllib.parse.unquote(pointer_path)

    # Retrieve content
    content, mime_type = await content_storage.get_content(uri)

    if content is None:
        raise HTTPException(status_code=404, detail='Content not found or expired')

    # Setup cache headers - content can be cached for up to 1 day
    headers = {
        'Cache-Control': 'public, max-age=86400',
    }

    # Return as streaming response with proper content type
    return StreamingResponse(iter([content]), media_type=mime_type, headers=headers)


@router.websocket('/ws')
async def generate_websocket(
    websocket: WebSocket,
) -> None:
    """WebSocket endpoint for generation.

    This endpoint handles all WebSocket connections for generation.
    The chat_id is passed in the message payload rather than the URL.
    """
    logger.info('New WebSocket connection request received')

    try:
        # Import worker readiness check
        from app.api.state import check_worker_ready

        # Check if this worker is ready to handle WebSocket connections
        worker_ready = await check_worker_ready(websocket.app)
        if not worker_ready:
            # We must accept before we can close with a status code
            await websocket.accept()
            await websocket.close(
                code=1013, reason='Service still initializing, please try again later'
            )
            return

        # Worker readiness check is sufficient - no need for global initialization check

        # Accept the connection only after we've verified initialization
        await websocket.accept()
        logger.debug('WebSocket connection accepted - fetching dependencies')

        from app.api.dependencies.chat import (
            get_chat_service_ws,
            get_task_handler_registry_ws,
        )
        from app.api.dependencies.clients import get_client_registry_ws

        # Get all dependencies using proper dependency functions with better error handling
        try:
            client_registry = await get_client_registry_ws(websocket)
            task_registry = await get_task_handler_registry_ws(websocket)
            chat_service = await get_chat_service_ws(websocket)

            logger.info('Successfully obtained all WebSocket dependencies')
            handler_names = await task_registry.get_handler_names()
            logger.debug(f'Task registry contains {len(handler_names)} handlers')

        except RuntimeError as e:
            logger.error(f'Service initialization error: {e}')
            await websocket.close(
                code=1011, reason=f'Service initialization error: {str(e)[:100]}'
            )
            return
        except Exception as e:
            logger.error(f'Unexpected dependency error: {e}', exc_info=True)
            await websocket.close(code=1011, reason=f'Unexpected error: {str(e)[:100]}')
            return

        logger.info('All required WebSocket dependencies successfully retrieved')

        # Hand off to the handler implementation with all dependencies
        await handle_generate_websocket(
            websocket,
            chat_service,
            task_registry,
            client_registry,
        )

    except Exception as e:
        logger.error(f'Unexpected WebSocket error: {e}', exc_info=True)
        try:
            # Try to accept if not already accepted
            if websocket.client_state.name != 'CONNECTED':
                await websocket.accept()
            await websocket.close(code=1011, reason=f'Server error: {str(e)[:100]}')
        except Exception as close_error:
            logger.error(f'Error while closing WebSocket: {close_error}')
