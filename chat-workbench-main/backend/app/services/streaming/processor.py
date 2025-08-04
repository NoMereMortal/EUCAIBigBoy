# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Event processor for streaming service."""

import asyncio
from datetime import datetime, timezone
from typing import Any, TypeVar, Union, cast

from loguru import logger

from app.clients.valkey.client import ValkeyClient
from app.models import (
    CitationPart,
    DocumentPart,
    Message,
    MessagePart,
    ModelResponse,
    ReasoningPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
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
from app.services.streaming.utils import get_event_id, get_event_type
from app.utils import generate_nanoid

# Type variable for event types
E = TypeVar('E', bound=BaseEvent)


class EventProcessor:
    """
    Processes streaming events, manages state, and publishes to Valkey.

    This class is responsible for:
    1. Processing events and maintaining state
    2. Publishing events to Valkey channels
    3. Aggregating events into message parts
    4. Managing message lifecycle
    """

    def __init__(self, valkey_client: ValkeyClient):
        """
        Initialize the event processor.

        Args:
            valkey_client: ValkeyClient instance for pub/sub operations
        """
        self.valkey_client = valkey_client
        self._message_states: dict[str, dict[str, Any]] = {}
        self._sequence_counters: dict[str, int] = {}
        self._active_parts: dict[str, dict[int, dict[str, Any]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        # Add deduplication tracking
        self._processed_events: dict[
            str, set[str]
        ] = {}  # response_id -> set of event_ids

    async def _get_lock(self, response_id: str) -> asyncio.Lock:
        """
        Get or create a lock for a specific response_id.

        Args:
            response_id: The response ID to get a lock for

        Returns:
            An asyncio.Lock instance
        """
        if response_id not in self._locks:
            self._locks[response_id] = asyncio.Lock()
        return self._locks[response_id]

    def _get_next_sequence(self, response_id: str) -> int:
        """
        Get the next sequence number for a response.

        Args:
            response_id: The response ID to get a sequence number for

        Returns:
            The next sequence number
        """
        if response_id not in self._sequence_counters:
            self._sequence_counters[response_id] = 0

        seq = self._sequence_counters[response_id]
        self._sequence_counters[response_id] += 1
        return seq

    def _ensure_message_state(self, response_id: str) -> dict[str, Any]:
        """
        Ensure a message state exists for a response ID.

        Args:
            response_id: The response ID to ensure state for

        Returns:
            The message state dictionary
        """
        if response_id not in self._message_states:
            self._message_states[response_id] = {
                'status': 'pending',
                'parts': [],
                'metadata': {},
                'usage': {},
                'model_name': '',
                'model_id': '',
                'timestamp': datetime.now(timezone.utc),
            }
        return self._message_states[response_id]

    def _ensure_active_parts(self, response_id: str) -> dict[int, dict[str, Any]]:
        """
        Ensure active parts tracking exists for a response ID.

        Args:
            response_id: The response ID to ensure active parts for

        Returns:
            The active parts dictionary
        """
        if response_id not in self._active_parts:
            self._active_parts[response_id] = {}
        return self._active_parts[response_id]

    async def _publish_event(self, event: BaseEvent) -> None:
        """
        Publish an event to the appropriate Valkey channel.

        Args:
            event: The BaseEvent to publish
        """
        from app.services.streaming.utils import serialize_event

        response_id = event.response_id
        event_type = type(event).__name__
        sequence = event.sequence
        emit = event.emit

        if not response_id:
            logger.warning(f'Event missing response_id, cannot publish: {event}')
            return

        logger.info(
            f'Preparing to publish event [type={event_type}, response_id={response_id}, sequence={sequence}]'
        )

        # Only publish if emit flag is True or not specified and valkey client is available
        if emit and self.valkey_client:
            channel = f'response:{response_id}'
            try:
                # Serialize event with type information
                event_json = serialize_event(event)

                # Enhanced logging: Log the JSON being published
                logger.debug(f'Event JSON to publish: {event_json[:200]}...')

                # Check if the client is initialized
                if not self.valkey_client._client:
                    logger.warning(
                        'Valkey client not initialized, cannot publish event'
                    )
                    return

                # Publish the event directly using the Valkey client
                start_time = datetime.now()
                await self.valkey_client._client.publish(channel, event_json)
                duration = (datetime.now() - start_time).total_seconds()

                # Enhanced logging: Log successful publication with timing
                logger.info(
                    f'Successfully published event to channel {channel} [type={event_type}, sequence={sequence}, duration={duration:.4f}s]'
                )
                logger.debug(f'Published event content: {str(event)[:200]}...')
            except Exception as e:
                # Enhanced logging: Detailed error information
                logger.error(
                    f'Error publishing event to channel {channel}: {e}',
                    exc_info=True,
                )
                logger.error(
                    f'Failed event details: type={event_type}, sequence={sequence}, response_id={response_id}'
                )
        else:
            # Enhanced logging: Log when events are skipped
            reason = 'emit=False' if not emit else 'no_valkey_client'
            logger.warning(
                f'Skipped publishing event [type={event_type}, response_id={response_id}, sequence={sequence}, reason={reason}]'
            )

    def _create_message_part(
        self, event_type: str, event: Union[BaseEvent, dict[str, Any]]
    ) -> MessagePart | None:
        """
        Create a message part from an event.

        Args:
            event_type: The type of event
            event: The event data

        Returns:
            A MessagePart instance or None if the event doesn't map to a part
        """
        metadata = {}

        # Extract content block tracking data if available
        if (
            isinstance(event, BaseEvent)
            and hasattr(event, 'content_block_index')
            and event.content_block_index is not None
        ):
            metadata['content_block_index'] = event.content_block_index

            if hasattr(event, 'block_sequence') and event.block_sequence is not None:
                metadata['block_sequence'] = event.block_sequence

        # Handle content events
        if event_type == 'ContentEvent':
            if isinstance(event, BaseEvent):
                content = cast(ContentEvent, event).content
            else:
                content = event.get('content', '')

            # Skip creating TextPart for empty content to avoid validation errors
            if not content or not content.strip():
                logger.debug(
                    f'Skipping TextPart creation for empty content in {event_type}'
                )
                return None

            text_part = TextPart(content=content, metadata=metadata)
            return text_part

        # Handle reasoning events
        elif event_type == 'ReasoningEvent':
            if isinstance(event, BaseEvent):
                event_cast = cast(ReasoningEvent, event)
                text = event_cast.text
                signature = event_cast.signature
            else:
                text = event.get('text', '')
                signature = event.get('signature')

            if not text or not text.strip():
                logger.debug(
                    f'Skipping ReasoningPart creation for empty content in {event_type}'
                )
                return None

            reasoning_part = ReasoningPart(
                content=text, signature=signature, metadata=metadata
            )
            return reasoning_part

        # Handle tool call events
        elif event_type == 'ToolCallEvent':
            if isinstance(event, BaseEvent):
                event_cast = cast(ToolCallEvent, event)
                tool_name = event_cast.tool_name
                tool_args = event_cast.tool_args
                tool_id = event_cast.tool_id
            else:
                tool_name = event.get('tool_name', '')
                tool_args = event.get('tool_args', {})
                tool_id = event.get('tool_id', generate_nanoid())

            tool_call_part = ToolCallPart(
                tool_name=tool_name,
                tool_args=tool_args,
                tool_id=tool_id,
                metadata=metadata,
            )
            return tool_call_part

        # Handle tool return events
        elif event_type == 'ToolReturnEvent':
            if isinstance(event, BaseEvent):
                event_cast = cast(ToolReturnEvent, event)
                tool_name = event_cast.tool_name
                tool_id = event_cast.tool_id
                result = event_cast.result
            else:
                tool_name = event.get('tool_name', '')
                tool_id = event.get('tool_id', '')
                result = event.get('result', None)

            tool_return_part = ToolReturnPart(
                tool_name=tool_name, tool_id=tool_id, result=result, metadata=metadata
            )
            return tool_return_part

        # Handle document events
        elif event_type == 'DocumentEvent':
            if isinstance(event, BaseEvent):
                event_cast = cast(DocumentEvent, event)
                pointer = event_cast.pointer
                mime_type = event_cast.mime_type
                title = event_cast.title
                page_count = event_cast.page_count
                word_count = event_cast.word_count
                document_id: str = event_cast.document_id
            else:
                pointer = event.get('pointer', '')
                mime_type = event.get('mime_type', '')
                title = event.get('title', '')
                document_id = event.get('document_id', '')
                page_count = event.get('page_count')
                word_count = event.get('word_count')

            document_part = DocumentPart(
                file_id=document_id,
                pointer=pointer,
                mime_type=mime_type,
                title=title,
                page_count=page_count,
                word_count=word_count,
                metadata=metadata,
            )
            return document_part

        # Other event types don't map directly to message parts
        return None

    async def _handle_response_start(self, event: ResponseStartEvent) -> None:
        """
        Handle a ResponseStartEvent.

        Args:
            event: The ResponseStartEvent
        """
        if isinstance(event, BaseEvent):
            response_id = event.response_id
            model_id = event.model_id
            timestamp = event.timestamp
        else:
            response_id = event.get('response_id')
            model_id = event.get('model_id', '')
            timestamp = event.get('timestamp', datetime.now(timezone.utc))

        if not response_id:
            logger.warning('ResponseStartEvent missing response_id')
            return

        state = self._ensure_message_state(response_id)
        state['status'] = 'in_progress'
        state['model_name'] = model_id  # Use model_id for model_name
        state['model_id'] = model_id
        state['timestamp'] = timestamp

    async def _handle_response_end(self, event: ResponseEndEvent) -> None:
        """
        Handle a ResponseEndEvent.

        Args:
            event: The ResponseEndEvent
        """
        if isinstance(event, BaseEvent):
            response_id = event.response_id
            status = event.status
            usage = event.usage
        else:
            response_id = event.get('response_id')
            status = event.get('status', 'completed')
            usage = event.get('usage', {})

        if not response_id:
            logger.warning('ResponseEndEvent missing response_id')
            return

        state = self._ensure_message_state(response_id)
        state['status'] = status

        # Update usage information
        if usage:
            state['usage'].update(usage)

    async def _handle_tool_return(self, event: ToolReturnEvent) -> None:
        """
        Handle a ToolReturnEvent.

        Args:
            event: The ToolReturnEvent
        """
        if isinstance(event, BaseEvent):
            response_id = event.response_id
            tool_name = event.tool_name
            tool_id = event.tool_id
            result = event.result
        else:
            response_id = event.get('response_id')
            tool_name = event.get('tool_name', '')
            tool_id = event.get('tool_id', '')
            result = event.get('result', None)

        if not response_id:
            logger.warning('ToolReturnEvent missing response_id')
            return

        # Create a ToolReturnPart and add it to the message
        tool_return_part = ToolReturnPart(
            tool_name=tool_name,
            tool_id=tool_id,
            result=result,
        )
        state = self._ensure_message_state(response_id)
        state['parts'].append(tool_return_part)

    async def _handle_metadata(self, event: MetadataEvent) -> None:
        """
        Handle a MetadataEvent.

        Args:
            event: The MetadataEvent
        """
        if isinstance(event, BaseEvent):
            response_id = event.response_id
            metadata = event.metadata
        else:
            response_id = event.get('response_id')
            metadata = event.get('metadata', {})

        if not response_id:
            logger.warning('MetadataEvent missing response_id')
            return

        # Update message metadata
        state = self._ensure_message_state(response_id)
        state['metadata'].update(metadata)

    async def _handle_status(self, event: StatusEvent) -> None:
        """
        Handle a StatusEvent.

        Args:
            event: The StatusEvent
        """
        if isinstance(event, BaseEvent):
            response_id = event.response_id
            status = event.status
            message = event.message
        else:
            response_id = event.get('response_id')
            status = event.get('status', 'unknown')
            message = event.get('message')

        if not response_id:
            logger.warning('StatusEvent missing response_id')
            return

        # Update message status
        state = self._ensure_message_state(response_id)
        state['status'] = status

        # Add message to metadata if provided
        if message:
            state['metadata']['status_message'] = message

    async def _handle_error(self, event: ErrorEvent) -> None:
        """
        Handle an ErrorEvent.

        Args:
            event: The ErrorEvent
        """
        if isinstance(event, BaseEvent):
            response_id = event.response_id
            error_type = event.error_type
            message = event.message
            details = event.details
        else:
            response_id = event.get('response_id')
            error_type = event.get('error_type', 'unknown')
            message = event.get('message', '')
            details = event.get('details')

        if not response_id:
            logger.warning('ErrorEvent missing response_id')
            return

        # Update message status to error
        state = self._ensure_message_state(response_id)
        state['status'] = 'error'

        # Add error details to metadata
        state['metadata']['error_type'] = error_type
        state['metadata']['error_message'] = message

        if details:
            state['metadata']['error_details'] = details

    async def _handle_document(self, event: DocumentEvent) -> None:
        """
        Handle a DocumentEvent.

        Args:
            event: The DocumentEvent
        """

        if isinstance(event, BaseEvent):
            event_cast = cast(DocumentEvent, event)
            response_id = event_cast.response_id
            pointer = event_cast.pointer
            mime_type = event_cast.mime_type
            title = event_cast.title
            page_count = event_cast.page_count
            word_count = event_cast.word_count
            document_id: str = event_cast.document_id
        else:
            response_id = event.get('response_id')
            pointer = event.get('pointer', '')
            mime_type = event.get('mime_type', '')
            title = event.get('title', '')
            document_id = event.get('document_id', '')
            page_count = event.get('page_count')
            word_count = event.get('word_count')

        if not response_id:
            logger.warning('DocumentEvent missing response_id')
            return

        # Create a DocumentPart and add it to the message
        document_part = DocumentPart(
            file_id=document_id,
            pointer=pointer,
            mime_type=mime_type,
            title=title,
            page_count=page_count,
            word_count=word_count,
        )
        state = self._ensure_message_state(response_id)
        state['parts'].append(document_part)

    async def _handle_citation(self, event: CitationEvent) -> None:
        """
        Handle a CitationEvent.

        Args:
            event: The CitationEvent
        """
        if isinstance(event, BaseEvent):
            event_cast = cast(CitationEvent, event)
            response_id = event_cast.response_id
            document_id = event_cast.document_id
            text = event_cast.text
            page = event_cast.page
            section = event_cast.section
        else:
            response_id = event.get('response_id')
            document_id = event.get('document_id', '')
            text = event.get('text', '')
            page = event.get('page')
            section = event.get('section')
            event.get('citation_id')

        if not response_id:
            logger.warning('CitationEvent missing response_id')
            return

        # Create a CitationPart and add it to the message
        citation_part = CitationPart(
            document_id=document_id, text=text, page=page, section=section
        )
        state = self._ensure_message_state(response_id)
        state['parts'].append(citation_part)

    async def process_event(self, event: Union[BaseEvent, dict[str, Any]]) -> None:
        """
        Process an event, update state, and publish to subscribers.

        Args:
            event: The event to process (BaseEvent or dict that will be converted)
        """
        # Enhanced logging: Log event entry with timestamp
        start_time = datetime.now()
        event_type = (
            type(event).__name__ if not isinstance(event, dict) else 'dict_event'
        )
        logger.info(
            f'Processing event [type={event_type}, start_time={start_time.isoformat()}]'
        )

        if isinstance(event, BaseEvent):
            response_id = event.response_id
        else:
            response_id = event.get('response_id')

        if not response_id:
            logger.warning(f'Event missing response_id, cannot process: {event}')
            return

        # Enhanced logging: Log event details
        logger.debug(f'Event details before processing: {str(event)[:200]}...')

        # Ensure the event has a sequence number
        if isinstance(event, BaseEvent):
            if not hasattr(event, 'sequence') or event.sequence is None:
                event.sequence = self._get_next_sequence(response_id)
                logger.debug(
                    f'Assigned sequence number {event.sequence} to event [response_id={response_id}]'
                )
        else:
            if 'sequence' not in event:
                event['sequence'] = self._get_next_sequence(response_id)
                logger.debug(
                    f'Assigned sequence number {event["sequence"]} to event [response_id={response_id}]'
                )

        # Ensure the event has a timestamp
        if isinstance(event, BaseEvent):
            if not hasattr(event, 'timestamp') or event.timestamp is None:
                event.timestamp = datetime.now(timezone.utc)
                logger.debug(f'Assigned timestamp to event [response_id={response_id}]')
        else:
            if 'timestamp' not in event:
                event['timestamp'] = datetime.now(timezone.utc)
                logger.debug(f'Assigned timestamp to event [response_id={response_id}]')

        # Use utility function for consistent event type detection
        event_type = get_event_type(event)

        # Check for duplicate events (especially tool calls)
        event_id = get_event_id(event)
        if response_id not in self._processed_events:
            self._processed_events[response_id] = set()

        if event_id in self._processed_events[response_id]:
            logger.warning(f'Duplicate event detected, skipping: {event_id}')
            return

        # Mark event as processed
        self._processed_events[response_id].add(event_id)

        # Convert dict events to proper event objects if needed
        if isinstance(event, dict):
            logger.debug(f'Received dict event: {event}')

            # Handle init_event_loop event
            if 'init_event_loop' in event:
                logger.debug(f'Received init_event_loop event: {event}')
                # This is just an initialization event, no need to process further
                return

            # Convert dict events to proper typed events based on detected type
            original_sequence = event.get('sequence')
            if event_type == 'ResponseStartEvent':
                # Convert dict to ResponseStartEvent
                event = ResponseStartEvent(
                    response_id=response_id,
                    request_id=event.get('request_id', ''),
                    chat_id=event.get('chat_id', ''),
                    task=event.get('task', ''),
                    model_id=event.get('model_id', ''),
                    parent_id=event.get('parent_id'),
                    sequence=original_sequence or self._get_next_sequence(response_id),
                    emit=True,
                    persist=True,
                )
            elif event_type == 'ResponseEndEvent':
                # Convert dict to ResponseEndEvent
                event = ResponseEndEvent(
                    response_id=response_id,
                    status=event.get('status', 'completed'),
                    usage=event.get('usage', {}),
                    sequence=original_sequence or self._get_next_sequence(response_id),
                    emit=True,
                    persist=True,
                )
            elif event_type == 'StatusEvent':
                status = event.get('status', 'unknown')
                message = event.get('message', '')
                event = StatusEvent(
                    response_id=response_id,
                    status=status,
                    message=message,
                    sequence=original_sequence or self._get_next_sequence(response_id),
                    emit=True,
                    persist=True,
                )
            elif event_type == 'ErrorEvent':
                error_type = str(
                    event.get('error_type', event.get('error', 'UnknownError'))
                )
                message = event.get('message', 'An error occurred')
                event = ErrorEvent(
                    response_id=response_id,
                    error_type=error_type,
                    message=message,
                    details=event.get('details', {}),
                    sequence=original_sequence or self._get_next_sequence(response_id),
                    emit=True,
                    persist=True,
                )
            elif event_type == 'ContentEvent':
                # Extract content using the same logic as the utility
                content = ''
                if 'content' in event and isinstance(event['content'], str):
                    content = event['content']
                elif 'data' in event and isinstance(event['data'], str):
                    content = event['data']
                elif (
                    'event' in event
                    and 'contentBlockDelta' in event['event']
                    and 'delta' in event['event']['contentBlockDelta']
                    and 'text' in event['event']['contentBlockDelta']['delta']
                ):
                    content = event['event']['contentBlockDelta']['delta']['text']

                # Extract content block tracking information if available
                content_block_index = None
                block_sequence = None
                if 'event' in event and 'contentBlockDelta' in event['event']:
                    content_block_delta = event['event']['contentBlockDelta']
                    if 'contentBlockIndex' in content_block_delta:
                        content_block_index = content_block_delta['contentBlockIndex']
                    if 'contentBlockPart' in content_block_delta:
                        block_sequence = content_block_delta['contentBlockPart']

                event = ContentEvent(
                    response_id=response_id,
                    content=content,
                    sequence=original_sequence or self._get_next_sequence(response_id),
                    content_block_index=content_block_index,
                    block_sequence=block_sequence,
                    emit=True,
                    persist=True,
                )
            elif event_type == 'ToolCallEvent':
                # Convert dict to ToolCallEvent
                tool_name = event.get('tool_name', '')
                tool_id = event.get('tool_id', '')
                tool_args = event.get('tool_args', {})

                # Extract content block tracking information if available
                content_block_index = None
                block_sequence = None
                if 'content_block_index' in event:
                    content_block_index = event['content_block_index']
                if 'block_sequence' in event:
                    block_sequence = event['block_sequence']

                event = ToolCallEvent(
                    response_id=response_id,
                    tool_name=tool_name,
                    tool_id=tool_id,
                    tool_args=tool_args,
                    sequence=original_sequence or self._get_next_sequence(response_id),
                    content_block_index=content_block_index,
                    block_sequence=block_sequence,
                    emit=True,
                    persist=True,
                )
            elif event_type == 'MetadataEvent':
                # Convert dict to MetadataEvent
                metadata = {}
                if 'metadata' in event:
                    metadata = event['metadata']
                elif 'usage' in event:
                    # Usage-only events are treated as metadata
                    metadata = {'usage': event['usage']}

                event = MetadataEvent(
                    response_id=response_id,
                    metadata=metadata,
                    sequence=original_sequence or self._get_next_sequence(response_id),
                    emit=True,
                    persist=True,
                )
            elif event_type == 'ReasoningEvent':
                # Convert dict to ReasoningEvent
                text = event.get('text', '')
                signature = event.get('signature')
                redacted_content = event.get('redacted_content')

                # Extract content block tracking information if available
                content_block_index = None
                block_sequence = None
                if 'content_block_index' in event:
                    content_block_index = event['content_block_index']
                if 'block_sequence' in event:
                    block_sequence = event['block_sequence']

                event = ReasoningEvent(
                    response_id=response_id,
                    text=text,
                    signature=signature,
                    redacted_content=redacted_content,
                    sequence=original_sequence or self._get_next_sequence(response_id),
                    content_block_index=content_block_index,
                    block_sequence=block_sequence,
                    emit=True,
                    persist=True,
                )
            elif event_type == 'dict_event':
                # Handle unrecognized dict events
                logger.warning(f'Unknown dict event format: {event}')
                event = StatusEvent(
                    response_id=response_id,
                    status='warning',
                    message='Received unknown event format',
                    sequence=self._get_next_sequence(response_id),
                    emit=True,
                    persist=True,
                )
                event_type = 'StatusEvent'

        # At this point, event is guaranteed to be a BaseEvent
        assert isinstance(event, BaseEvent), (
            f'Event should be BaseEvent after conversion, got {type(event)}'
        )

        # Acquire a lock for this response_id to ensure thread safety
        async with await self._get_lock(response_id):
            # Process events directly based on type
            try:
                if event_type == 'ContentEvent':
                    # Create part directly from content event
                    part = self._create_message_part(event_type, event)
                    if part:
                        state = self._ensure_message_state(response_id)
                        state['parts'].append(part)
                elif event_type == 'ReasoningEvent':
                    # Create part directly from reasoning event
                    part = self._create_message_part(event_type, event)
                    if part:
                        state = self._ensure_message_state(response_id)
                        state['parts'].append(part)
                elif event_type == 'ResponseStartEvent':
                    await self._handle_response_start(cast(ResponseStartEvent, event))
                elif event_type == 'ResponseEndEvent':
                    await self._handle_response_end(cast(ResponseEndEvent, event))
                elif event_type == 'ToolCallEvent':
                    part = self._create_message_part(event_type, event)
                    if part:
                        state = self._ensure_message_state(response_id)
                        state['parts'].append(part)
                elif event_type == 'ToolReturnEvent':
                    await self._handle_tool_return(cast(ToolReturnEvent, event))
                elif event_type == 'MetadataEvent':
                    await self._handle_metadata(cast(MetadataEvent, event))
                elif event_type == 'DocumentEvent':
                    await self._handle_document(cast(DocumentEvent, event))
                elif event_type == 'CitationEvent':
                    await self._handle_citation(cast(CitationEvent, event))
                elif event_type == 'StatusEvent':
                    await self._handle_status(cast(StatusEvent, event))
                elif event_type == 'ErrorEvent':
                    await self._handle_error(cast(ErrorEvent, event))
                else:
                    logger.warning(f'Unknown event type: {event_type}')
            except Exception as e:
                import traceback

                error_msg = str(e)
                error_traceback = traceback.format_exc()
                logger.error(f'Error processing event {event_type}: {error_msg}')
                logger.error(f'Error traceback: {error_traceback}')

                # Create and emit an error event to notify clients
                error_sequence = self._get_next_sequence(response_id)
                error_event = ErrorEvent(
                    response_id=response_id,
                    error_type=type(e).__name__,
                    message=f'Error processing {event_type}: {error_msg}',
                    details={
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'traceback': error_traceback,
                        'event_type': event_type,
                    },
                    sequence=error_sequence,
                    emit=True,
                    persist=True,
                )

                # Publish the error event and update state
                await self._publish_event(error_event)
                await self._handle_error(error_event)

        # Enhanced logging: Log before publishing
        if isinstance(event, BaseEvent):
            sequence = event.sequence
            emit = event.emit
        else:
            sequence = event.get('sequence')
            emit = event.get('emit', True)

        logger.debug(
            f'Event processing complete, preparing to publish [response_id={response_id}, sequence={sequence}, emit={emit}]'
        )

        # Publish the event to subscribers if emit is True or not specified
        if emit:
            await self._publish_event(event)
        else:
            logger.debug(
                f'Skipping publication for event with emit=False [response_id={response_id}, sequence={sequence}]'
            )

        # Enhanced logging: Log event processing completion with timing
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            f'Event processing completed [type={event_type}, response_id={response_id}, sequence={sequence}, duration={duration:.4f}s]'
        )

    def get_message(self, response_id: str) -> Message | None:
        """
        Get the current message state for a response ID.

        Args:
            response_id: The response ID to get the message for

        Returns:
            A Message instance or None if not found
        """
        if response_id not in self._message_states:
            return None

        state = self._message_states[response_id]

        # Create a ModelResponse
        message = ModelResponse(
            message_id=response_id,
            chat_id='',  # This should be set by the caller
            model_name=state['model_name'],
            parts=state['parts'].copy(),
            status=state['status'],
            metadata=state['metadata'].copy(),
            usage=state['usage'].copy(),
            timestamp=state['timestamp'],
        )

        return message

    def cleanup_response(self, response_id: str) -> None:
        """
        Clean up resources for a response ID.

        Args:
            response_id: The response ID to clean up
        """
        if response_id in self._message_states:
            del self._message_states[response_id]

        if response_id in self._sequence_counters:
            del self._sequence_counters[response_id]

        if response_id in self._active_parts:
            del self._active_parts[response_id]

        if response_id in self._locks:
            del self._locks[response_id]

        if response_id in self._processed_events:
            del self._processed_events[response_id]

        logger.debug(f'Cleaned up resources for response {response_id}')
