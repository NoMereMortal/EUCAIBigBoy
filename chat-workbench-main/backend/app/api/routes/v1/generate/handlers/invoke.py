# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Invoke handler for generation requests."""

from loguru import logger

from app.api.routes.v1.generate.models import GenerateRequest, GenerateResponse
from app.clients.registry import ClientRegistry
from app.clients.valkey.client import ValkeyClient
from app.models import MessagePart
from app.services.chat import ChatService
from app.services.streaming import StreamingService
from app.task_handlers.registry import TaskHandlerRegistry


async def handle_generate_invoke(
    request: GenerateRequest,
    chat_service: ChatService,
    task_handler_registry: TaskHandlerRegistry,
    client_registry: ClientRegistry,
) -> GenerateResponse:  # type: ignore
    """
    Handle non-streaming generation request with the new streaming service.

    Args:
        request: The generation request
        chat_service: The chat service
        task_handler_registry: The task handler registry
        client_registry: The client registry

    Returns:
        A generation response
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

    # No longer need protocol handlers - we use direct event collection

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

    try:
        # Get task handler
        task_handler = await task_handler_registry.get_handler(request.task)
        if not task_handler:
            raise ValueError(f'Task handler {request.task} not found')

        # Start the handler generator - process_task_handler_events will handle if it's a coroutine
        handler_generator = task_handler.handle(
            chat_id=str(request.chat_id),
            message_history=message_history,
            user_message=user_message,
            model_id=request.model_id,
            response_message_id=response_id,
            context=request.context,
            persona=request.persona,
        )

        # Import the process function
        from app.api.routes.v1.generate.handlers.process import (
            process_task_handler_events,
        )

        # Process events from the handler (wait for completion)
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

        # Get the final message from the database (not from in-memory state)
        # The in-memory state doesn't have the saved metadata with token usage
        response_message = await chat_service.message_repo.get_message(
            request.chat_id, response_id
        )
        if not response_message:
            raise ValueError(f'No response message found for {response_id}')

        # Extract usage from metadata if available
        usage = {}
        logger.info(
            f'Response message metadata from DB: {getattr(response_message, "metadata", "NO_METADATA")}'
        )
        logger.info(
            f'Response message metadata type: {type(getattr(response_message, "metadata", None))}'
        )
        if hasattr(response_message, 'metadata') and response_message.metadata:
            logger.info(f'Found metadata: {response_message.metadata}')
            logger.info(
                f'Metadata keys: {list(response_message.metadata.keys()) if hasattr(response_message.metadata, "keys") else "NO_KEYS"}'
            )
            if 'usage' in response_message.metadata:
                # Ensure usage is a dict, not None
                metadata_usage = response_message.metadata['usage']
                usage = metadata_usage if isinstance(metadata_usage, dict) else {}
                logger.info(f'Extracted usage from metadata: {usage}')
            elif 'usage_info' in response_message.metadata:
                # Parse usage_info string back to dict
                usage_info = response_message.metadata['usage_info']
                logger.info(f'Found usage_info string: {usage_info}')
                logger.info(f'usage_info type: {type(usage_info)}')
                try:
                    # Convert string representation back to dict
                    import ast

                    usage = (
                        ast.literal_eval(usage_info)
                        if isinstance(usage_info, str)
                        else usage_info
                    )
                    logger.info(f'Parsed usage from usage_info: {usage}')
                except Exception as e:
                    logger.warning(f'Failed to parse usage_info: {e}')
                    usage = {}
            else:
                logger.info("No 'usage' or 'usage_info' key in metadata")
        else:
            logger.info('No metadata found on response message')

        # Create successful response
        # Use ValidatedPartList from models to ensure proper type conversion
        from app.api.routes.v1.generate.models import (
            convert_to_proper_part_types,
        )

        # Validate parts to ensure they match expected type
        validated_parts = convert_to_proper_part_types(response_message.parts)

        # The specific part types are all subclasses of MessagePart, so this is type-safe
        message_parts: list[MessagePart] = validated_parts  # type: ignore

        final_response = GenerateResponse(
            message_id=response_message.message_id,
            chat_id=request.chat_id,
            parts=message_parts,  # Use the validated parts cast to MessagePart list
            usage=usage,
            metadata=response_message.metadata
            if hasattr(response_message, 'metadata')
            else {},
        )
        logger.info(f'Final GenerateResponse usage field: {final_response.usage}')
        return final_response
    except Exception as e:
        logger.error(f'Error in invoke: {e}', exc_info=True)

        # Return an error response
        return GenerateResponse(
            message_id=response_id,
            chat_id=request.chat_id,
            parts=[],
            usage={},
            metadata={'error': str(e), 'error_type': type(e).__name__},
        )
    finally:
        # Clean up resources
        streaming_service.cleanup_response(response_id)
