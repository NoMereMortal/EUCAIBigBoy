# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""WebSocket handler for generation requests."""

import asyncio
import json
from typing import Any

from fastapi import WebSocket
from loguru import logger

from app.api.routes.v1.generate.handlers.process import process_task_handler_events
from app.api.routes.v1.generate.models import GenerateRequest
from app.api.websocket import WebSocketManager
from app.clients.registry import ClientRegistry
from app.services.chat import ChatService
from app.task_handlers.registry import TaskHandlerRegistry
from app.utils import generate_nanoid


async def handle_generate_websocket(
    websocket: WebSocket,
    chat_service: ChatService,
    task_registry: TaskHandlerRegistry,
    client_registry: ClientRegistry,
) -> None:
    """
    Handle WebSocket connection for generation with proper context isolation.

    Uses contextvars.copy_context() to isolate the WebSocket handler context and
    avoid context variable token reuse issues across different requests.

    Args:
        websocket: The WebSocket connection
        chat_service: The chat service
        task_registry: The task handler registry
        client_registry: The client registry from dependencies
    """
    # Validate dependencies before proceeding
    if chat_service is None:
        logger.error('Chat service is None in WebSocket handler')
        await websocket.close(code=1011, reason='Chat service not available')
        return

    if task_registry is None:
        logger.error('Task registry is None in WebSocket handler')
        await websocket.close(code=1011, reason='Task registry not available')
        return

    if client_registry is None:
        logger.error('Client registry is None in WebSocket handler')
        await websocket.close(code=1011, reason='Client registry not available')
        return

    # Avoid context variable issues with websockets
    import contextvars

    # Create a new context for this websocket handler
    ctx = contextvars.copy_context()

    # Use the context to run the actual handler function
    return await ctx.run(
        _handle_generate_websocket_impl,
        websocket,
        chat_service,
        task_registry,
        client_registry,
    )


async def _handle_generate_websocket_impl(
    websocket: WebSocket,
    chat_service: ChatService,
    task_registry: TaskHandlerRegistry,
    client_registry: ClientRegistry,
) -> None:
    """Actual implementation of websocket handler in a fresh context."""
    # Import worker readiness check
    from app.api.state import check_worker_ready

    # Validate app state before proceeding using the same worker readiness check as the endpoint
    worker_ready = await check_worker_ready(websocket.app)
    if not worker_ready:
        logger.error(
            'WebSocket handler execution rejected - application not fully initialized'
        )
        await websocket.close(code=1013, reason='Service still initializing')
        return

    # Always access state components directly to avoid inconsistencies between processes
    # Check if required state components are available using direct attribute access
    websocket_manager = getattr(websocket.app.state, 'websocket_manager', None)

    if not websocket_manager:
        logger.error('WebSocket handler: websocket_manager not available in app state')
        await websocket.close(code=1011, reason='WebSocket manager not available')
        return

    logger.info('WebSocket manager accessed directly from app state')

    # Handle the WebSocket connection
    connection_id = generate_nanoid()

    try:
        # Accept connection with better error handling
        try:
            # Only accept if not already accepted
            if websocket.client_state.name != 'CONNECTED':
                await websocket.accept()
            await websocket_manager.connect(connection_id, websocket)
            logger.debug(f'WebSocket connection established: {connection_id}')
        except Exception as e:
            logger.error(f'Error accepting WebSocket connection: {e}')
            return  # Early return if we can't establish the connection

        # Main message loop
        while True:
            raw_message = await websocket.receive_text()

            try:
                message = json.loads(raw_message)
                message_type = message.get('type')
                logger.info(f'Received WebSocket message [type={message_type}]')

                # Route message based on type
                if message_type == 'initialize':
                    await handle_ws_initialize(
                        websocket_manager,
                        connection_id,
                        message,
                        chat_service,
                        task_registry,
                    )
                elif message_type == 'interrupt':
                    await handle_ws_interrupt(websocket_manager, connection_id, message)
                elif message_type == 'ping':
                    # Send pong response
                    from app.api.websocket import WSMessageType

                    await websocket_manager.send_message(
                        connection_id,
                        WSMessageType.PONG,
                        {'timestamp': asyncio.get_event_loop().time()},
                    )
                else:
                    from app.api.websocket import WSMessageType

                    await websocket_manager.send_message(
                        connection_id,
                        WSMessageType.ERROR,
                        {'error': f'Unknown message type: {message_type}'},
                    )
            except json.JSONDecodeError:
                from app.api.websocket import WSMessageType

                await websocket_manager.send_message(
                    connection_id,
                    WSMessageType.ERROR,
                    {'error': 'Invalid JSON message'},
                )
            except Exception as e:
                logger.error(f'Error processing message: {e}', exc_info=True)
                from app.api.websocket import WSMessageType

                await websocket_manager.send_message(
                    connection_id, WSMessageType.ERROR, {'error': f'Error: {e!s}'}
                )

    except Exception as e:
        logger.error(f'WebSocket connection error: {e}', exc_info=True)
    finally:
        # Clean up connection
        await websocket_manager.disconnect(connection_id)


async def handle_ws_initialize(
    websocket_manager: WebSocketManager,
    connection_id: str,
    message: dict[str, Any],
    chat_service: ChatService,
    task_registry: TaskHandlerRegistry,
) -> None:
    """
    Handle initialize request to start generation.

    Args:
        websocket_manager: The WebSocket manager
        connection_id: The connection ID
        message: The message data
        chat_service: The chat service
        task_registry: The task handler registry
        streaming_service: The streaming service
    """
    try:
        # Extract request data
        data = message.get('data', {})
        if not data or 'chat_id' not in data:
            raise ValueError('Missing required data in initialize message')

        chat_id = data.get('chat_id')
        request = GenerateRequest(**data)

        # Register chat with this connection
        await websocket_manager.register_chat(connection_id, chat_id)

        # Start chat session
        user_message = await chat_service.start(
            request.chat_id,
            request.parent_id if request.parent_id else request.chat_id,
            request.parts,
        )

        # Get conversation path from root to parent_id for model input
        parent_id = request.parent_id if request.parent_id else request.chat_id
        message_history = await chat_service.get_conversation_path(
            request.chat_id,
            parent_id,
        )

        # Initialize response in streaming service
        response_id = await websocket_manager.streaming_service.init_response(
            chat_id=request.chat_id,
            parent_id=user_message.message_id,
            model_id=request.model_id,
        )

        # Track generation in WebSocket manager
        await websocket_manager.track_generation(chat_id, response_id)

        def event_callback(formatted_event_json: str):
            """Send events from Valkey to WebSocket client."""
            try:
                # Get the WebSocket connection for this connection_id
                if connection_id in websocket_manager._active_connections:
                    websocket_conn = websocket_manager._active_connections[
                        connection_id
                    ]
                    # Send the formatted event to the WebSocket client
                    asyncio.create_task(websocket_conn.send_text(formatted_event_json))
                else:
                    logger.warning(
                        f'WebSocket connection {connection_id} not found for event delivery'
                    )
            except Exception as e:
                logger.error(f'Error sending event to WebSocket {connection_id}: {e}')

        # Subscribe to the response channel to receive streaming events
        await websocket_manager.subscribe_to_response(response_id, event_callback)
        logger.info(
            f'Subscribed to events for response {response_id} on connection {connection_id}'
        )

        # Get task handler with better logging
        try:
            # Log available handlers for debugging
            handler_names = await task_registry.get_handler_names()
            logger.debug(f'Available task handlers: {handler_names}')

            # Get the handler for the requested task
            task_handler = await task_registry.get_handler(request.task)
            logger.info(f"Found task handler for task '{request.task}'")
        except ValueError as e:
            logger.error(f'Task handler error: {e}')
            from app.api.websocket import WSMessageType

            await websocket_manager.send_message(
                connection_id,
                WSMessageType.ERROR,
                {'error': f'Task handler not found: {request.task}'},
            )
            return
        except Exception as e:
            logger.error(f'Unexpected error getting task handler: {e}', exc_info=True)
            from app.api.websocket import WSMessageType

            await websocket_manager.send_message(
                connection_id,
                WSMessageType.ERROR,
                {'error': f'Error retrieving task handler: {e}'},
            )
            return

        # Start the handler generator
        # Note: process_task_handler_events will handle the case where this is a coroutine
        handler_generator = task_handler.handle(
            chat_id=str(request.chat_id),
            message_history=message_history,
            user_message=user_message,
            model_id=request.model_id,
            response_message_id=response_id,
            context=request.context,
            persona=request.persona,
        )

        # Process events in a background task
        asyncio.create_task(
            process_task_handler_events(
                streaming_service=websocket_manager.streaming_service,
                response_id=response_id,
                handler_generator=handler_generator,
                chat_service=chat_service,
                chat_id=request.chat_id,
                model_id=request.model_id,
                request_id=user_message.message_id,
                task=request.task,
                parent_id=request.parent_id,
            )
        )

    except Exception as e:
        logger.error(f'Error in initialize handler: {e}', exc_info=True)
        from app.api.websocket import WSMessageType

        await websocket_manager.send_message(
            connection_id, WSMessageType.ERROR, {'error': f'Error initializing: {e!s}'}
        )


async def handle_ws_interrupt(
    websocket_manager: WebSocketManager,
    connection_id: str,
    message: dict[str, Any],
) -> None:
    """
    Handle interrupt request to stop generation.

    Args:
        websocket_manager: The WebSocket manager
        connection_id: The connection ID
        message: The message data
        streaming_service: The streaming service
    """
    try:
        data = message.get('data', {})
        chat_id = data.get('chat_id')
        message_id = data.get('message_id')

        if not chat_id or not message_id:
            raise ValueError('Interrupt request requires chat_id and message_id')

        # Get accumulated content
        websocket_manager.get_accumulated_content(chat_id, message_id)

        # Process interrupt event
        from app.services.streaming.events import ResponseEndEvent, StatusEvent

        await websocket_manager.streaming_service.process_event(
            StatusEvent(
                response_id=message_id,
                status='interrupted',
                message='Generation interrupted by user',
                sequence=998,
                emit=True,
                persist=True,
            )
        )

        # End the response
        await websocket_manager.streaming_service.process_event(
            ResponseEndEvent(
                response_id=message_id,
                status='interrupted',
                usage={},
                sequence=999,
                emit=True,
                persist=True,
            )
        )

        # Stop tracking generation
        await websocket_manager.stop_generation(chat_id)

        # Send status update
        from app.api.websocket import WSMessageType

        await websocket_manager.send_message(
            connection_id,
            WSMessageType.STATUS,
            {
                'status': 'interrupted',
                'chat_id': chat_id,
                'message_id': message_id,
            },
        )

    except Exception as e:
        logger.error(f'Error in interrupt handler: {e}', exc_info=True)
        from app.api.websocket import WSMessageType

        await websocket_manager.send_message(
            connection_id,
            WSMessageType.ERROR,
            {'error': f'Error handling interrupt: {e!s}'},
        )
