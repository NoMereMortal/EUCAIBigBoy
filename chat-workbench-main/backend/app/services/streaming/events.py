# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """Base for all events with common metadata."""

    response_id: str = Field(..., description='The message_id this event belongs to')
    sequence: int = Field(default=0, description='For ordering events')
    emit: bool = Field(default=True, description='Whether to emit to clients')
    persist: bool = Field(default=True, description='Whether to persist in DB')
    timestamp: datetime = Field(
        default_factory=datetime.now, description='Event timestamp'
    )

    # Content block tracking fields
    content_block_index: int | None = Field(
        default=None, description='Content block this event belongs to'
    )
    block_sequence: int | None = Field(
        default=None, description='Sequence within the content block'
    )

    def get_event_type_name(self) -> str:
        """Return the event type name for protocol formatting in snake_case."""
        class_name = self.__class__.__name__

        # Convert specific event types to snake_case
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

        if class_name in type_mapping:
            return type_mapping[class_name]

        # Fallback: convert PascalCase to snake_case
        if class_name.endswith('Event'):
            class_name = class_name[:-5]  # Remove 'Event' suffix

        # Convert to snake_case
        import re

        return re.sub('([A-Z])', r'_\1', class_name).lower().lstrip('_')

    def _filter_internal(self) -> dict[str, Any]:
        """Get event data without internal protocol fields."""
        data = self.model_dump()
        # Remove protocol-internal fields
        internal_fields = {'emit', 'persist', 'sequence'}
        for field in internal_fields:
            data.pop(field, None)

        # Convert datetime to ISO string if present
        if 'timestamp' in data and isinstance(data['timestamp'], datetime):
            data['timestamp'] = data['timestamp'].isoformat()

        return data

    def to_sse(self) -> dict[str, Any]:
        """Format for SSE protocol."""
        return {
            'event_type': self.get_event_type_name(),
            'data': self._filter_internal(),
        }

    def to_websocket(self) -> dict[str, Any]:
        """Format for WebSocket protocol."""
        return {'type': self.get_event_type_name(), **self._filter_internal()}

    def to_sync(self) -> dict[str, Any]:
        """Format for synchronous/invoke API."""
        return self._filter_internal()


class ResponseStartEvent(BaseEvent):
    """Event for a response start."""

    request_id: str
    chat_id: str
    task: str
    model_id: str
    parent_id: str | None = None


class ResponseEndEvent(BaseEvent):
    """Event for a response end."""

    usage: dict[str, Any]
    status: str = Field(description="Status: 'completed', 'error', etc.")
    chat_id: str | None = None


class ContentEvent(BaseEvent):
    """Complete content in one event."""

    content: str


class ToolCallEvent(BaseEvent):
    """Complete tool call in one event."""

    tool_name: str
    tool_args: dict[str, Any]
    tool_id: str


class ToolReturnEvent(BaseEvent):
    """Event for a tool return."""

    tool_name: str
    tool_id: str
    result: Any


class MetadataEvent(BaseEvent):
    """Event for metadata."""

    metadata: dict[str, Any]


class DocumentEvent(BaseEvent):
    """Event for a document."""

    document_id: str
    title: str
    pointer: str = Field(..., description='s3://<bucket>/<key> or file://<path>')
    mime_type: str
    page_count: int | None = None
    word_count: int | None = None


class CitationEvent(BaseEvent):
    """Event for a citation."""

    document_id: str
    text: str
    page: int | None = None
    section: str | None = None
    citation_id: str | None = None
    reference_number: int | None = None
    document_title: str | None = None
    document_pointer: str | None = None


class StatusEvent(BaseEvent):
    """Event for a status."""

    status: str
    message: str | None = None


class ErrorEvent(BaseEvent):
    """Event for an error."""

    error_type: str
    message: str
    details: dict[str, Any] | None = None
    chat_id: str | None = None


class ReasoningEvent(BaseEvent):
    """Event for reasoning content from models."""

    text: str | None = None
    signature: str | None = None
    redacted_content: bytes | None = None
