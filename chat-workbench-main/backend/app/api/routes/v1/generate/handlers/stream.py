# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Stream handler for generation requests."""

import asyncio
import json

from fastapi.responses import StreamingResponse
from loguru import logger

from app.api.routes.v1.generate.models import GenerateRequest
from app.clients.registry import ClientRegistry
from app.clients.valkey.client import ValkeyClient
from app.services.chat import ChatService
from app.services.streaming import StreamingService
from app.services.streaming.events import ResponseEndEvent
from app.services.streaming.utils import format_event_for_sse
from app.task_handlers.registry import TaskHandlerRegistry


async def handle_generate_stream(
    request: GenerateRequest,
    chat_service: ChatService,
    task_handler_registry: TaskHandlerRegistry,
    client_registry: ClientRegistry,
) -> StreamingResponse:
    """
    Handle streaming generation request with the new streaming service.

    Args:
        request: The generation request
        chat_service: The chat service
        task_handler_registry: The task handler registry
        client_registry: The client registry

    Returns:
        A streaming response
    """
    # Get valkey client - needed for streaming service
    valkey_client, valkey_available = await client_registry.get_client('valkey')

    # Validate valkey client - now required for streaming service
    if (
        not valkey_client
        or not valkey_available
        or not isinstance(valkey_client, ValkeyClient)
    ):
        logger.error('Cannot create streaming service: Valkey client not available')
        raise RuntimeError(
            'Cannot create streaming service: Valkey client not available'
        )

    # Create streaming service with the valkey client
    streaming_service = StreamingService(valkey_client)

    # No longer need protocol handlers - we use direct formatting

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
    response_id = await streaming_service.init_response(
        chat_id=request.chat_id,
        parent_id=user_message.message_id,
        model_id=request.model_id,
    )

    # Create streaming response
    async def event_stream():
        try:
            # Create an async queue to receive events
            event_queue = asyncio.Queue()

            # Subscribe to events for this response
            def event_callback(event):
                try:
                    event_queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(
                        f'Event queue full, dropping event for response {response_id}'
                    )
                except Exception as e:
                    logger.error(f'Error adding event to queue: {e}')

            # Direct event subscription using Valkey pubsub (simplified for SSE)
            if valkey_client and isinstance(valkey_client, ValkeyClient):
                pubsub = await valkey_client.pubsub()
                channel = f'response:{response_id}'
                await pubsub.subscribe(channel)

                # Start a task to listen for Valkey events
                async def valkey_listener():
                    try:
                        while True:
                            message = await pubsub.get_message(
                                ignore_subscribe_messages=True, timeout=1.0
                            )
                            if message:
                                from app.services.streaming.utils import (
                                    deserialize_event,
                                )

                                try:
                                    # Ensure message data is string
                                    data = message['data']
                                    if isinstance(data, bytes):
                                        data = data.decode('utf-8')
                                    elif data is None:
                                        continue  # Skip None data
                                    event = deserialize_event(str(data))
                                    event_callback(event)
                                except Exception as e:
                                    logger.error(f'Error deserializing event: {e}')
                                    event_callback(
                                        {
                                            'event_type': 'error',
                                            'data': {'error': str(e)},
                                        }
                                    )
                    except Exception as e:
                        logger.error(f'Error in Valkey listener: {e}')

                asyncio.create_task(valkey_listener())

            # Get task handler
            task_handler = await task_handler_registry.get_handler(request.task)
            if not task_handler:
                raise ValueError(f'Task handler {request.task} not found')

            # Start the handler generator - no await needed as it returns an AsyncGenerator directly
            handler_generator = task_handler.handle(
                chat_id=str(request.chat_id),
                message_history=message_history,
                user_message=user_message,
                model_id=request.model_id,
                response_message_id=response_id,
                context=request.context,
                persona=request.persona,
            )

            # Create a task to process events
            process_task = asyncio.create_task(
                process_events_for_sse(
                    streaming_service,
                    handler_generator,
                    response_id,
                    chat_service,
                    request,
                    user_message,
                )
            )

            # Listen for events from the SSE protocol
            while True:
                try:
                    # Wait for an event with a timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)

                    # Process the event and format as SSE using direct formatting
                    from app.services.streaming.events import BaseEvent

                    if isinstance(event, BaseEvent):
                        # Use direct SSE formatting
                        formatted_event = format_event_for_sse(event)
                        yield formatted_event

                        # Check if this is a completion event to break the loop
                        if isinstance(event, ResponseEndEvent):
                            break
                    elif isinstance(event, dict):
                        # Handle dict events (fallback)
                        event_type = event.get(
                            'event_type',
                            event.get('__typename', event.get('type', 'unknown')),
                        )
                        yield f'event: {event_type}\ndata: {json.dumps(event)}\n\n'

                        # Check if this is a completion event to break the loop
                        if (
                            event_type in ['ResponseEndEvent', 'completed']
                            or event.get('status') == 'completed'
                        ):
                            break
                    else:
                        # Handle non-dict events
                        logger.debug(f'Received non-dict event: {type(event)}')
                        yield f'event: unknown\ndata: {json.dumps({"data": str(event)})}\n\n'

                except asyncio.TimeoutError:
                    # Check if the process task is done
                    if process_task.done():
                        # Check for exceptions
                        try:
                            await process_task
                        except Exception as e:
                            logger.error(f'Error in process task: {e}')
                            yield f'data: {json.dumps({"error": str(e), "complete": True})}\n\n'
                        break

                    # Continue waiting for events
                    continue

                except Exception as e:
                    logger.error(f'Error in SSE event stream: {e}')
                    yield f'data: {json.dumps({"error": str(e), "complete": True})}\n\n'
                    break

        except Exception as e:
            logger.error(f'Error in SSE stream: {e}', exc_info=True)
            yield f'data: {json.dumps({"error": str(e), "complete": True})}\n\n'

        finally:
            # Clean up resources
            streaming_service.cleanup_response(response_id)

    return StreamingResponse(event_stream(), media_type='text/event-stream')


async def process_events_for_sse(
    streaming_service,
    handler_generator,
    response_id: str,
    chat_service: ChatService,
    request: GenerateRequest,
    user_message,
):
    """
    Process events from a task handler for SSE streaming.

    Args:
        streaming_service: The streaming service
        handler_generator: The handler generator
        response_id: The response ID
        chat_service: The chat service
        request: The generation request
    """
    # Import from the module directly
    from app.api.routes.v1.generate.handlers.process import process_task_handler_events

    # Process events from the handler
    await process_task_handler_events(
        streaming_service=streaming_service,
        response_id=response_id,
        handler_generator=handler_generator,
        chat_service=chat_service,
        chat_id=request.chat_id,
        model_id=request.model_id,
        request_id=user_message.message_id,
        task=request.task,
        parent_id=request.parent_id,
    )
