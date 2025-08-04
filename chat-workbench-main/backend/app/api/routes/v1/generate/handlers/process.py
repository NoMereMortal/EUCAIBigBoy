# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Process task handler results and send events to streaming service."""

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from loguru import logger

from app.models import ModelResponse, PartType
from app.services.chat import ChatService
from app.services.event_utils import process_part_from_events
from app.services.streaming.events import (
    BaseEvent,
    ErrorEvent,
    ResponseEndEvent,
    ResponseStartEvent,
)
from app.services.streaming.utils import is_completion_event


async def process_task_handler_events(
    streaming_service,
    response_id: str,
    handler_generator,
    chat_service: ChatService,
    chat_id: str,
    model_id: str,
    request_id: str,
    task: str,
    parent_id: str | None,
):
    """
    Process events from a task handler with simplified event processing.

    This function implements a clean and straightforward approach to event processing:
    1. Events are received from the handler generator
    2. Events are organized by content block
    3. Content blocks are processed into message parts
    4. Message parts are added to the message and saved to the database

    Args:
        streaming_service: Service for handling streaming events to clients
        response_id: ID of the response message
        handler_generator: Async generator yielding events
        chat_service: Service for managing chat data
        chat_id: ID of the chat
        model_id: ID of the model used
        request_id: ID of the request message
        task: Task description
        parent_id: ID of the parent message
    """
    logger.info(f'Starting event processing for response {response_id}')
    logger.debug(
        f'Processing task handler events - chat_id={chat_id}, response_id={response_id}, request_id={request_id}, model_id={model_id}'
    )

    # 1. First, create an empty response message that we'll populate as we go
    # This ensures the message exists from the start
    message = ModelResponse(
        message_id=response_id,
        chat_id=chat_id,
        parent_id=request_id,  # Use request_id as parent_id
        model_name=model_id,
        status='pending',
        parts=[],  # Start with empty parts
    )

    # Create the message in the database
    logger.debug(f'Creating initial response message: {response_id}')
    await chat_service.message_repo.create_message(message)

    # 2. Track content blocks and events
    content_blocks: dict[int, list[BaseEvent]] = {}  # {block_index: [events]}
    non_block_events: list[BaseEvent] = []  # Events without content_block_index
    completion_event = None
    event_count = 0

    try:
        # 3. Send initial event for streaming to clients
        start_event = ResponseStartEvent(
            response_id=response_id,
            request_id=request_id,
            chat_id=chat_id,
            task=task,
            model_id=model_id,
            parent_id=parent_id,
            sequence=0,
            emit=True,
            persist=True,
        )
        await streaming_service.process_event(start_event)

        # 4. Process events from the handler
        # Check if handler_generator is a coroutine or an async generator
        if asyncio.iscoroutine(handler_generator):
            logger.debug('Handler generator is a coroutine, awaiting it first')
            handler_generator = await handler_generator

        # Now process events from the async generator
        async for event in handler_generator:
            event_count += 1

            # A. Ensure chat_id is set on all events that need it
            if isinstance(event, (ResponseEndEvent, ErrorEvent)):
                event.chat_id = chat_id
                logger.debug(
                    f'Ensured chat_id is set to {chat_id} for {type(event).__name__}'
                )

            # B. Track the completion event for later use
            if is_completion_event(event):
                completion_event = event

            # C. Organize events by content block
            block_idx = getattr(event, 'content_block_index', None)
            if block_idx is not None:
                if block_idx not in content_blocks:
                    content_blocks[block_idx] = []
                content_blocks[block_idx].append(event)
                logger.debug(
                    f'Added event to block {block_idx}: {type(event).__name__}'
                )
            else:
                # Keep track of events without block index
                non_block_events.append(event)
                logger.debug(f'Added event without block index: {type(event).__name__}')

            # D. Send event to websocket clients
            await streaming_service.process_event(event)

        # 5. After processing all events, convert content blocks to message parts
        logger.info(f'Processed {event_count} events, now converting to message parts')
        logger.debug(
            f'Found {len(content_blocks)} content blocks and {len(non_block_events)} non-block events'
        )

        all_parts: list[PartType] = []

        # Process each content block in order
        for block_idx in sorted(content_blocks.keys()):
            # Log the content block processing
            logger.debug(f'Processing content block {block_idx} events')

            # Group events by type within this block
            events_by_type = {}
            for event in content_blocks[block_idx]:
                event_type = type(event).__name__
                if event_type not in events_by_type:
                    events_by_type[event_type] = []
                events_by_type[event_type].append(event)

            # Log the event type distribution
            for event_type, events in events_by_type.items():
                logger.debug(
                    f'  Block {block_idx}: {len(events)} events of type {event_type}'
                )

                # Special logging for citation events
                if event_type == 'CitationEvent':
                    for i, event in enumerate(events):
                        logger.debug(
                            f'  Citation {i} in block {block_idx}: '
                            f'citation_id={getattr(event, "citation_id", "unknown")}, '
                            f'document_id={getattr(event, "document_id", "unknown")}, '
                            f'text_len={len(getattr(event, "text", ""))}, '
                            f"text_preview='{getattr(event, 'text', '')[:50]}...'"
                        )

            # Process each event type group to create parts
            for event_type, events in events_by_type.items():
                logger.debug(
                    f'Converting {len(events)} {event_type} events to part for block {block_idx}'
                )
                part = process_part_from_events(events)
                if part:
                    all_parts.append(part)
                    logger.debug(
                        f'Created {part.part_kind} part from {len(events)} events for block {block_idx}'
                    )

                    # Special logging for citation parts
                    if part.part_kind == 'citation':
                        logger.debug(
                            f'Citation part created for block {block_idx}: '
                            f'document_id={getattr(part, "document_id", "unknown")}, '
                            f'citation_id={getattr(part, "citation_id", "unknown")}, '
                            f'text_len={len(getattr(part, "text", ""))}, '
                            f'content_len={len(getattr(part, "content", ""))}, '
                            f"content_preview='{getattr(part, 'content', '')[:100]}...'"
                        )
                else:
                    logger.warning(
                        f'Failed to create part from {len(events)} {event_type} events for block {block_idx}'
                    )

        # Process events without content blocks (if they can be processed)
        if non_block_events:
            logger.debug(
                f'Processing {len(non_block_events)} events without content block index'
            )

            # Sort all non-block events by sequence first
            sorted_non_block_events = sorted(
                non_block_events, key=lambda e: getattr(e, 'sequence', 0) or 0
            )

            # Group sorted non-block events by type
            non_block_by_type = {}
            for event in sorted_non_block_events:
                event_type = type(event).__name__
                if event_type not in non_block_by_type:
                    non_block_by_type[event_type] = []
                non_block_by_type[event_type].append(event)

            # Log the event type distribution for non-block events
            for event_type, events in non_block_by_type.items():
                logger.debug(f'  Non-block: {len(events)} events of type {event_type}')

                # Special logging for citation events
                if event_type == 'CitationEvent':
                    for i, event in enumerate(events):
                        logger.debug(
                            f'  Non-block Citation {i}: '
                            f'citation_id={getattr(event, "citation_id", "unknown")}, '
                            f'document_id={getattr(event, "document_id", "unknown")}, '
                            f'text_len={len(getattr(event, "text", ""))}'
                        )

            # Try to process each type
            for event_type, events in non_block_by_type.items():
                # Only process types that can produce parts
                if event_type in [
                    'ContentEvent',
                    'ToolCallEvent',
                    'CitationEvent',
                    'DocumentEvent',
                    'ReasoningEvent',
                    'StatusEvent',
                    'ToolReturnEvent',
                ]:
                    logger.debug(
                        f'Converting {len(events)} non-block {event_type} events to part'
                    )
                    part = process_part_from_events(events)
                    if part:
                        all_parts.append(part)
                        logger.debug(
                            f'Created {part.part_kind} part from {len(events)} non-block events'
                        )

                        # Special logging for citation parts
                        if part.part_kind == 'citation':
                            logger.debug(
                                f'Citation part created from non-block events: '
                                f'document_id={getattr(part, "document_id", "unknown")}, '
                                f'citation_id={getattr(part, "citation_id", "unknown")}, '
                                f'text_len={len(getattr(part, "text", ""))}, '
                                f'content_len={len(getattr(part, "content", ""))}'
                            )
                    else:
                        logger.warning(
                            f'Failed to create part from {len(events)} non-block {event_type} events'
                        )

        # 6. Update the message with all parts
        # Apply validation to ensure all parts are properly typed MessagePart instances
        if hasattr(chat_service, '_validate_and_convert_parts'):
            # Use the new validation method if available
            validated_parts = chat_service._validate_and_convert_parts(all_parts)
            logger.debug(
                f'Validated {len(validated_parts)} parts from {len(all_parts)} original parts'
            )
            message.parts = validated_parts
        else:
            # Fallback to direct assignment
            message.parts = all_parts

        logger.info(f'Created {len(message.parts)} message parts')

        # Log detailed part information for debugging
        for i, part in enumerate(all_parts):
            part_kind = part.part_kind
            if part_kind == 'citation':
                # Detailed logging for citation parts
                document_id = getattr(part, 'document_id', 'unknown')
                citation_id = getattr(part, 'citation_id', 'unknown')
                text_len = len(getattr(part, 'text', ''))
                content_len = len(getattr(part, 'content', ''))
                content_preview = getattr(part, 'content', '')[:100] + (
                    '...' if len(getattr(part, 'content', '')) > 100 else ''
                )

                logger.debug(
                    f'Final Part {i} (citation): document_id={document_id}, citation_id={citation_id}, '
                    f"text_len={text_len}, content_len={content_len}, content_preview='{content_preview}'"
                )
            else:
                # General part logging
                content_preview = str(part.content)[:100] + (
                    '...' if len(str(part.content)) > 100 else ''
                )
                logger.debug(
                    f"Final Part {i}: {part.part_kind}, content: '{content_preview}'"
                )

        # 7. Handle completion based on the completion event
        if completion_event:
            if isinstance(completion_event, ResponseEndEvent) and hasattr(
                completion_event, 'usage'
            ):
                logger.info(
                    f'Processing ResponseEndEvent with usage: {completion_event.usage}'
                )
                message.metadata = {'usage_info': str(completion_event.usage)}
                logger.debug(f'Set message.metadata to: {message.metadata}')

            # Mark message as complete
            message.status = 'complete'

            # Save final message to the database
            logger.debug(
                f'About to save completed message {response_id} with {len(all_parts)} parts to database'
            )
            success = await chat_service.message_repo.save_message(message)
            if success:
                logger.info(
                    f'Saved completed message: {response_id} with {len(all_parts)} parts'
                )

                # For debugging, retrieve the saved message to verify parts were properly saved
                saved_message = await chat_service.message_repo.get_message(
                    chat_id, response_id
                )
                if saved_message:
                    logger.debug(
                        f'Verification: Retrieved message {response_id} has {len(saved_message.parts)} parts'
                    )

                    # Verify citation parts if present
                    citation_parts = [
                        p for p in saved_message.parts if p.part_kind == 'citation'
                    ]
                    if citation_parts:
                        for i, part in enumerate(citation_parts):
                            logger.debug(
                                f'Verified Citation {i}: document_id={getattr(part, "document_id", "unknown")}, '
                                f'text_len={len(getattr(part, "text", ""))}, content_len={len(getattr(part, "content", ""))}'
                            )
                else:
                    logger.warning(
                        f'Could not retrieve message {response_id} for verification after save'
                    )
            else:
                logger.error(f'Failed to save completed message: {response_id}')

            # Update request status to complete
            if request_id:
                request_message = await chat_service.message_repo.get_message(
                    chat_id=chat_id, message_id=request_id
                )
                if request_message and request_message.status == 'pending':
                    request_message.status = 'complete'
                    await chat_service.message_repo.save_message(request_message)
                    logger.info(f'Updated request {request_id} status to complete')

    except Exception as e:
        logger.error(f'Critical error in event processing: {e}', exc_info=True)

        # Handle errors by updating message status
        message.status = 'error'
        message.metadata = {'error_type': type(e).__name__, 'error_message': str(e)}
        await chat_service.message_repo.save_message(message)

        # Create and send error event to clients
        error_event = ErrorEvent(
            response_id=response_id,
            chat_id=chat_id,
            error_type=type(e).__name__,
            message=f'Processing error: {e!s}',
            details={'timestamp': datetime.now(timezone.utc).isoformat()},
            sequence=999,
            emit=True,
            persist=True,
        )
        await streaming_service.process_event(error_event)

    finally:
        # Ensure message is complete even if no completion event was received
        if not completion_event:
            logger.warning(
                f'No completion event received for {response_id}, marking as complete anyway'
            )

            message.status = 'complete'
            await chat_service.message_repo.save_message(message)

            # Send a fallback completion event to clients
            fallback_event = ResponseEndEvent(
                response_id=response_id,
                chat_id=chat_id,
                status='complete',
                usage={},
                sequence=1000,
                emit=True,
                persist=True,
            )
            await streaming_service.process_event(fallback_event)

    logger.info(f'Event processing finished for response {response_id}')
    return message
