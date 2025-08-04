# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Utility functions for the streaming service."""

import contextlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Union, cast

from app.services.streaming.events import (
    BaseEvent,
    CitationEvent,
    ContentEvent,
    DocumentEvent,
    ErrorEvent,
    MetadataEvent,
    ReasoningEvent,
    ResponseEndEvent,
    ResponseStartEvent,
    StatusEvent,
    ToolCallEvent,
    ToolReturnEvent,
)
from app.utils import make_json_serializable


def get_event_type(event: Union[BaseEvent, dict[str, Any]]) -> str:
    """
    Get the consistent event type name from any event format.

    Args:
        event: The event to get the type for (BaseEvent instance or dict)

    Returns:
        The event type name (e.g., 'StatusEvent', 'ContentEvent', etc.)
    """
    if isinstance(event, dict):
        # Handle dict events (like those from Strands)

        # Check for explicit event_type field first
        if 'event_type' in event:
            return event['event_type']

        # Check for ResponseStartEvent pattern (has unique combination of fields)
        if (
            'request_id' in event
            and 'chat_id' in event
            and 'task' in event
            and 'model_id' in event
        ):
            return 'ResponseStartEvent'

        # Check for ResponseEndEvent pattern (has both status AND usage)
        if 'status' in event and 'usage' in event:
            return 'ResponseEndEvent'

        # Check for status field only (StatusEvent)
        if 'status' in event:
            return 'StatusEvent'

        # Check for error fields (ErrorEvent)
        if 'error_type' in event or 'error' in event:
            return 'ErrorEvent'

        # Check for tool call patterns (ToolCallEvent family)
        if 'tool_name' in event and 'tool_id' in event:
            # Check for ToolReturnEvent first (has result field)
            if 'result' in event:
                return 'ToolReturnEvent'
            # Check for complete ToolCallEvent (has tool_args)
            elif 'tool_args' in event:
                return 'ToolCallEvent'
            # Default to ToolCallEvent (just tool_name and tool_id)
            else:
                return 'ToolCallEvent'

        # Check for tool call pattern (just tool_name or tool_id)
        if 'tool_name' in event or 'tool_id' in event:
            return 'ToolCallEvent'

        # Check for document patterns (DocumentEvent)
        if 'document_id' in event and ('title' in event or 'pointer' in event):
            return 'DocumentEvent'

        # Check for metadata patterns (MetadataEvent)
        if 'metadata' in event:
            return 'MetadataEvent'

        # Check for usage-only events (treat as MetadataEvent since usage is metadata)
        if (
            'usage' in event
            and len(
                [
                    k
                    for k in event
                    if k
                    not in [
                        'response_id',
                        'sequence',
                        'emit',
                        'persist',
                        'timestamp',
                        'usage',
                    ]
                ]
            )
            == 0
        ):
            return 'MetadataEvent'

        # Check for reasoning content (ReasoningEvent)
        if 'text' in event and ('signature' in event or 'redacted_content' in event):
            return 'ReasoningEvent'

        # Check for content field (ContentEvent)
        if 'content' in event and isinstance(event['content'], str):
            return 'ContentEvent'

        # Check for nested event structure (Anthropic/Amazon Bedrock format)
        if 'event' in event:
            nested_event = event['event']
            if isinstance(nested_event, dict):
                if 'contentBlockDelta' in nested_event:
                    return 'ContentEvent'
                elif 'messageStart' in nested_event:
                    return 'ResponseStartEvent'
                elif 'messageStop' in nested_event:
                    return 'ResponseEndEvent'

        # Check for data field as fallback
        if 'data' in event and isinstance(event['data'], str):
            return 'ContentEvent'

        # Default for unrecognized dict events
        return 'dict_event'
    else:
        # Handle BaseEvent instances
        return type(event).__name__


def is_completion_event(event: Union[BaseEvent, dict[str, Any]]) -> bool:
    """
    Check if an event represents a completion.

    Args:
        event: The event to check

    Returns:
        True if this is a completion event
    """
    event_type = get_event_type(event)

    # Direct completion events
    if event_type == 'ResponseEndEvent':
        return True

    # Status events with completed status
    if event_type == 'StatusEvent':
        if isinstance(event, BaseEvent):
            status = cast(StatusEvent, event).status
        else:
            status = event.get('status', '')
        return status in ['completed', 'complete']

    return False


def is_error_event(event: Union[BaseEvent, dict[str, Any]]) -> bool:
    """
    Check if an event represents an error.

    Args:
        event: The event to check

    Returns:
        True if this is an error event
    """
    event_type = get_event_type(event)

    # Direct error events
    if event_type == 'ErrorEvent':
        return True

    # Status events with error status
    if event_type == 'StatusEvent':
        if isinstance(event, BaseEvent):
            status = cast(StatusEvent, event).status
        else:
            status = event.get('status', '')
        return status == 'error'

    # Dict events with error indicators
    if isinstance(event, dict):
        return 'error_type' in event or 'error' in event

    return False


def get_event_id(event: Union[BaseEvent, dict[str, Any]]) -> str:
    """
    Generate a unique identifier for an event for deduplication.

    Args:
        event: The event to generate an ID for

    Returns:
        A unique identifier string
    """
    if isinstance(event, BaseEvent):
        response_id = event.response_id
        sequence = event.sequence
    else:
        response_id = event.get('response_id', 'unknown')
        sequence = event.get('sequence', 0)

    event_type = get_event_type(event)

    return f'{response_id}:{sequence}:{event_type}'


def get_event_type_snake_case(event: Union[BaseEvent, dict[str, Any]]) -> str:
    """
    Get event type in snake_case format for client consumption.

    Args:
        event: The event to get the type for

    Returns:
        The event type name in snake_case (e.g., 'content_delta', 'response_start')
    """
    pascal_case = get_event_type(event)

    # Convert specific event types
    type_mapping = {
        'ResponseStartEvent': 'response_start',
        'ResponseEndEvent': 'response_end',
        'ContentEvent': 'content',
        'StatusEvent': 'status',
        'ErrorEvent': 'error',
        'MetadataEvent': 'metadata',
        'ToolCallEvent': 'tool_call',
        'ToolReturnEvent': 'tool_return',
        'DocumentEvent': 'document',
        'ReasoningEvent': 'reasoning',
        'CitationEvent': 'citation',
    }

    return type_mapping.get(pascal_case, _to_snake_case(pascal_case))


def _to_snake_case(pascal_case: str) -> str:
    """Convert PascalCase to snake_case"""
    return re.sub('([A-Z])', r'_\1', pascal_case).lower().lstrip('_')


def serialize_event(event: BaseEvent) -> str:
    """
    Serialize a BaseEvent to JSON with type information for perfect reconstruction.

    Args:
        event: The BaseEvent instance to serialize

    Returns:
        JSON string with event data and type metadata
    """
    # Get the event data
    event_data = event.model_dump()

    # Add type metadata for reconstruction
    event_data['__event_type__'] = type(event).__name__

    # Ensure timestamp is serializable
    if 'timestamp' in event_data and isinstance(event_data['timestamp'], datetime):
        event_data['timestamp'] = event_data['timestamp'].isoformat()

    return json.dumps(event_data)


def deserialize_event(json_str: str) -> BaseEvent:
    """
    Deserialize JSON back to the correct BaseEvent subclass.

    Args:
        json_str: JSON string with event data and type metadata

    Returns:
        The reconstructed BaseEvent instance

    Raises:
        ValueError: If the event type is unknown or deserialization fails
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid JSON: {e}') from e

    # Get the event type
    event_type = data.pop('__event_type__', None)
    if not event_type:
        raise ValueError('Missing __event_type__ in serialized event') from None

    # Convert timestamp back to datetime if present
    if 'timestamp' in data and isinstance(data['timestamp'], str):
        with contextlib.suppress(ValueError):
            data['timestamp'] = datetime.fromisoformat(
                data['timestamp'].replace('Z', '+00:00')
            )

    # Map event types to classes
    event_classes = {
        'ResponseStartEvent': ResponseStartEvent,
        'ResponseEndEvent': ResponseEndEvent,
        'ContentEvent': ContentEvent,
        'ToolCallEvent': ToolCallEvent,
        'ToolReturnEvent': ToolReturnEvent,
        'DocumentEvent': DocumentEvent,
        'MetadataEvent': MetadataEvent,
        'ReasoningEvent': ReasoningEvent,
        'StatusEvent': StatusEvent,
        'ErrorEvent': ErrorEvent,
        'CitationEvent': CitationEvent,
    }

    event_class = event_classes.get(event_type)
    if not event_class:
        raise ValueError(f'Unknown event type: {event_type}') from None

    try:
        return event_class(**data)
    except Exception as e:
        raise ValueError(f'Failed to reconstruct {event_type}: {e}') from e


def format_event_for_sse(event: BaseEvent) -> str:
    """Format a BaseEvent for SSE delivery."""
    sse_format = event.to_sse()
    return (
        f'event: {sse_format["event_type"]}\ndata: {json.dumps(sse_format["data"])}\n\n'
    )


def format_event_for_websocket(event: BaseEvent) -> str:
    """Format a BaseEvent for WebSocket delivery."""
    ws_format = event.to_websocket()
    message = {
        'type': 'event',
        'data': ws_format,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(make_json_serializable(message))


def format_event_for_sync(event: BaseEvent) -> dict[str, Any]:
    """Format a BaseEvent for synchronous/invoke API delivery."""
    return event.to_sync()
