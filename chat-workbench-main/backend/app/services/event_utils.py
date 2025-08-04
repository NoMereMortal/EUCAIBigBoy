# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Event processing utilities."""

import json
from typing import Any

from loguru import logger

from app.models import (
    CitationPart,
    DocumentPart,
    PartType,
    ReasoningPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from app.services.streaming.events import (
    CitationEvent,
    ContentEvent,
    DocumentEvent,
    ErrorEvent,
    ReasoningEvent,
    ResponseEndEvent,
    StatusEvent,
    ToolCallEvent,
    ToolReturnEvent,
)


def process_part_from_events(events: list[Any]) -> PartType | None:
    """
    Process a list of events and convert them into a single consolidated MessagePart.

    This is a pure function with no side effects: it takes events as input
    and returns a properly typed MessagePart as output, with no state management.

    Args:
        events: List of events to consolidate (should be of same type)

    Returns:
        A consolidated MessagePart of the appropriate type, or None if consolidation failed
    """
    if not events:
        return None

    # Determine event type and consolidate accordingly
    sample_event = events[0]  # Use first event to determine type

    # Extract common metadata
    content_block_index = None
    if (
        hasattr(sample_event, 'content_block_index')
        and sample_event.content_block_index is not None
    ):
        content_block_index = sample_event.content_block_index

    # Ensure all metadata values are strings
    string_metadata = {}
    if content_block_index is not None:
        string_metadata['content_block_index'] = str(content_block_index)

    # ContentEvent → TextPart
    if all(isinstance(e, ContentEvent) for e in events):
        # First sort by primary sequence number
        sequence_sorted_events = sorted(
            events, key=lambda e: getattr(e, 'sequence', 0) or 0
        )

        # Then sort by block_sequence within each sequence group if applicable
        sorted_events = sorted(
            sequence_sorted_events, key=lambda e: getattr(e, 'block_sequence', 0) or 0
        )

        # Log the ordering of events for debugging
        logger.debug(f'Combining {len(sorted_events)} content events in sequence order')
        for i, event in enumerate(sorted_events):
            seq = getattr(event, 'sequence', 0) or 0
            block_seq = getattr(event, 'block_sequence', 0) or 0
            content_preview = (
                getattr(event, 'content', '')[:30].replace('\n', ' ') + '...'
            )
            logger.debug(
                f"  Content event {i}: sequence={seq}, block_sequence={block_seq}, content='{content_preview}'"
            )

        # Combine content in sorted order
        combined_content = ''.join(
            getattr(event, 'content', '')
            for event in sorted_events
            if hasattr(event, 'content')
        )

        return TextPart(content=combined_content, metadata=string_metadata)

    # ToolCallEvent → ToolCallPart
    elif all(isinstance(e, ToolCallEvent) for e in events):
        # First sort by primary sequence number
        sequence_sorted_events = sorted(
            events, key=lambda e: getattr(e, 'sequence', 0) or 0
        )

        # Then sort by block_sequence within each sequence group if applicable
        sorted_events = sorted(
            sequence_sorted_events, key=lambda e: getattr(e, 'block_sequence', 0) or 0
        )

        # Log the ordering of events for debugging
        logger.debug(
            f'Combining {len(sorted_events)} tool call events in sequence order'
        )

        # Get base info from first event
        first_event = sorted_events[0]
        tool_name = getattr(first_event, 'tool_name', '')
        tool_id = getattr(first_event, 'tool_id', '')

        # Handle streaming tool_args
        json_fragments = []
        raw_content = ''

        for event in sorted_events:
            args = getattr(event, 'tool_args', {})

            # Case 1: {"delta": "token"} format
            if isinstance(args, dict) and 'delta' in args:
                raw_content += args['delta']

            # Case 2: Direct string token
            elif isinstance(args, str):
                raw_content += args

            # Case 3: Regular dict - keep the last complete one
            elif isinstance(args, dict):
                json_fragments.append(args)

        # Try to create valid JSON from raw content
        combined_args = {}
        if raw_content:
            try:
                # Try parsing as JSON if it looks like JSON
                if raw_content.strip().startswith('{'):
                    combined_args = json.loads(raw_content)
                else:
                    # Otherwise treat as plain string
                    combined_args = {'input': raw_content}
            except json.JSONDecodeError:
                # If parsing fails, store as raw string
                combined_args = {'input': raw_content}

        # If we have complete JSON fragments, use the last one
        elif json_fragments:
            combined_args = json_fragments[-1]

        return ToolCallPart(
            tool_name=tool_name,
            tool_id=tool_id,
            tool_args=combined_args,
            metadata=string_metadata,
        )

    # CitationEvent → CitationPart
    elif all(isinstance(e, CitationEvent) for e in events):
        # Log incoming citation events
        logger.debug(f'Processing {len(events)} citation events')
        for i, event in enumerate(events):
            logger.debug(
                f'Citation event {i}: id={getattr(event, "citation_id", "unknown")}, '
                f'doc_id={getattr(event, "document_id", "unknown")}, '
                f'text_len={len(getattr(event, "text", ""))}, '
                f"text_preview='{getattr(event, 'text', '')[:50]}...'"
            )

        # First sort by primary sequence number
        sequence_sorted_events = sorted(
            events, key=lambda e: getattr(e, 'sequence', 0) or 0
        )

        # Then sort by block_sequence within each sequence group if applicable
        sorted_events = sorted(
            sequence_sorted_events, key=lambda e: getattr(e, 'block_sequence', 0) or 0
        )

        # Log the ordering of events for debugging
        logger.debug(
            f'Combining {len(sorted_events)} citation events in sequence order'
        )

        # Get base info from first event
        first_event = sorted_events[0]
        document_id = getattr(first_event, 'document_id', '')
        if not document_id:
            # Set a default document_id to avoid validation errors
            document_id = 'cd4739en'
            logger.warning(
                f'Citation event missing document_id, setting default: {document_id}'
            )

        page = getattr(first_event, 'page', None)
        section = getattr(first_event, 'section', None)
        citation_id = getattr(first_event, 'citation_id', None)
        if not citation_id:
            # Generate a citation ID if missing
            from app.utils import generate_nanoid

            citation_id = generate_nanoid()
            logger.debug(f'Generated citation_id {citation_id} for event without one')

        # Extract additional critical fields for UI rendering
        reference_number = getattr(first_event, 'reference_number', None)
        document_title = getattr(first_event, 'document_title', None)
        document_pointer = getattr(first_event, 'document_pointer', None)

        logger.debug(
            f'Citation metadata: citation_id={citation_id}, document_id={document_id}, '
            f'page={page}, section={section}, reference_number={reference_number}, '
            f'document_title={document_title}'
        )

        # Combine text with proper spacing
        text_fragments = []
        for event in sorted_events:
            if hasattr(event, 'text') and event.text:
                text_fragments.append(getattr(event, 'text', ''))

        # Join with spaces to ensure readability
        combined_text = ' '.join(text_fragments)
        logger.debug(
            f"Combined citation text ({len(combined_text)} chars): '{combined_text[:100]}...'"
        )

        # Prepare citation data with validation and defaults
        citation_data = {
            'document_id': document_id,
            'text': combined_text,
            'content': combined_text,  # Explicitly set content field to match text for serialization
            'page': page,
            'section': section,
            'citation_id': citation_id,
            'metadata': string_metadata,
        }

        # Add optional fields only if they exist
        if reference_number is not None:
            citation_data['reference_number'] = reference_number
        if document_title is not None:
            citation_data['document_title'] = document_title
        if document_pointer is not None:
            citation_data['document_pointer'] = document_pointer

        try:
            # Create citation part with validated fields
            citation_part = CitationPart(**citation_data)
        except Exception as e:
            # Log error and create a fallback part
            logger.error(f'Failed to create CitationPart: {e}')
            # Create a plain TextPart as fallback
            return TextPart(
                content=f'[Citation from {document_id}]: {combined_text[:200]}...',
                metadata={'citation_error': str(e), **string_metadata},
            )

        # Log the created citation part for verification
        logger.debug(
            f'Created CitationPart: citation_id={citation_part.citation_id}, '
            f'text_len={len(citation_part.text)}, content_len={len(citation_part.content)}, '
            f"content_preview='{citation_part.content[:100]}...'"
        )

        return citation_part

    # ReasoningEvent → ReasoningPart
    elif all(isinstance(e, ReasoningEvent) for e in events):
        # First sort by primary sequence number
        sequence_sorted_events = sorted(
            events, key=lambda e: getattr(e, 'sequence', 0) or 0
        )

        # Then sort by block_sequence within each sequence group if applicable
        sorted_events = sorted(
            sequence_sorted_events, key=lambda e: getattr(e, 'block_sequence', 0) or 0
        )

        # Log the ordering of events for debugging
        logger.debug(
            f'Combining {len(sorted_events)} reasoning events in sequence order'
        )

        # Combine text with line breaks
        combined_text = '\n'.join(
            getattr(event, 'text', '')
            for event in sorted_events
            if hasattr(event, 'text') and event.text
        )

        # Use signature from last event
        last_event = sorted_events[-1]
        signature = getattr(last_event, 'signature', None)

        return ReasoningPart(
            content=combined_text, signature=signature, metadata=string_metadata
        )

    # StatusEvent → Skip (these are for streaming only, not for persistence)
    elif all(isinstance(e, StatusEvent) for e in events):
        logger.debug(f'Skipping {len(events)} status events - these are streaming-only')
        return None

    # DocumentEvent → DocumentPart
    elif all(isinstance(e, DocumentEvent) for e in events):
        logger.debug(f'Processing {len(events)} document events')

        # Take the first event as the source for document information
        event = events[0]

        # Extract document attributes
        document_id = getattr(event, 'document_id', '')
        title = getattr(event, 'title', '')
        pointer = getattr(event, 'pointer', '')
        mime_type = getattr(event, 'mime_type', '')
        page_count = getattr(event, 'page_count', None)
        word_count = getattr(event, 'word_count', None)

        logger.debug(
            f"Creating DocumentPart from event: id={document_id}, title='{title}', mime_type='{mime_type}'"
        )

        # Create DocumentPart
        try:
            return DocumentPart(
                file_id=document_id,
                title=title,
                pointer=pointer,
                mime_type=mime_type,
                page_count=page_count,
                word_count=word_count,
                metadata=string_metadata,
            )
        except Exception as e:
            # Log error and create fallback
            logger.error(f'Failed to create DocumentPart: {e}')
            return TextPart(
                content=f'[Document: {title or document_id}]',
                metadata={'document_error': str(e), **string_metadata},
            )

    # ToolReturnEvent → ToolReturnPart
    elif all(isinstance(e, ToolReturnEvent) for e in events):
        # Take the first event as the source for tool return information
        event = events[0]

        # Extract tool return attributes
        tool_name = getattr(event, 'tool_name', '')
        tool_id = getattr(event, 'tool_id', '')
        result = getattr(event, 'result', {})

        logger.debug(
            f"Creating ToolReturnPart from event: tool_name='{tool_name}', tool_id='{tool_id}'"
        )

        # Create ToolReturnPart
        try:
            return ToolReturnPart(
                tool_name=tool_name,
                tool_id=tool_id,
                result=result,
                metadata=string_metadata,
            )
        except Exception as e:
            # Log error and create fallback
            logger.error(f'Failed to create ToolReturnPart: {e}')
            return TextPart(
                content=f'[Tool Result from {tool_name}]: {str(result)[:200]}...',
                metadata={'tool_return_error': str(e), **string_metadata},
            )

    # Unknown event type
    return None


async def process_event(service, event: Any, streaming_service=None) -> bool:
    """
    Process a completion or error event, persisting it to the database.

    Args:
        service: The chat service instance to handle chat-related operations
        event: The event to process
        streaming_service: Optional streaming service for accessing message state

    Returns:
        Success status
    """
    try:
        if not hasattr(event, 'chat_id') or not event.chat_id:
            logger.warning('Event missing chat_id, cannot process')
            return False

        if not hasattr(event, 'response_id'):
            logger.warning('Event missing response_id, cannot process')
            return False

        chat_id = event.chat_id
        message_id = event.response_id

        # Handle based on event type
        if isinstance(event, ResponseEndEvent):
            # Complete the message - pass usage directly via event
            usage_info = {}
            if hasattr(event, 'usage'):
                usage_info = event.usage

            await service.complete(
                chat_id=chat_id,
                message_id=message_id,
                metadata={'usage_info': str(usage_info)} if usage_info else {},
            )

            return True

        elif isinstance(event, ErrorEvent):
            # Construct error info with string values only
            error_type = 'unknown'
            if hasattr(event, 'error_type'):
                error_type = str(event.error_type)

            error_message = 'Unknown error'
            if hasattr(event, 'message'):
                error_message = str(event.message)

            # Create a simplified error_info dict with string values
            error_info = {'type': error_type, 'message': error_message}

            if hasattr(event, 'details') and event.details:
                # Convert details to string representation
                error_info['details'] = str(event.details)

            # Record error
            await service.error(
                chat_id=chat_id, message_id=message_id, error_info=error_info
            )

            return True

        else:
            # Other event types are not directly handled
            logger.warning(
                f'Unhandled event type for persistence: {type(event).__name__}'
            )
            return False

    except Exception as e:
        logger.error(f'Error processing event: {e}')
        return False
