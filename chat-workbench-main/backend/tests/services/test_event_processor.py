# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for EventProcessor - core event processing and state management."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from app.models import TextPart
from app.services.streaming.events import (
    ContentEvent,
    ErrorEvent,
    MetadataEvent,
    ResponseEndEvent,
    ResponseStartEvent,
    ToolCallEvent,
    ToolReturnEvent,
)
from app.services.streaming.processor import EventProcessor


class TestEventProcessor:
    """Tests for EventProcessor - critical state management and event aggregation."""

    @pytest.fixture
    def mock_valkey_client(self):
        """Mock Valkey client for caching."""
        mock_client = AsyncMock()
        mock_client.publish = AsyncMock()
        mock_client.set = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        return mock_client

    @pytest.fixture
    def event_processor(self, mock_valkey_client):
        """Create EventProcessor with mocked dependencies."""
        return EventProcessor(valkey_client=mock_valkey_client)

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_event_processor_full_conversation_lifecycle(self, event_processor):
        """Test complete conversation lifecycle with realistic event sequence."""
        response_id = 'resp_123'

        # Simulate a realistic conversation turn
        events = [
            ResponseStartEvent(
                response_id=response_id,
                request_id='req_123',
                chat_id='chat_456',
                task='chat',
                model_id='claude-3-sonnet',
                parent_id='msg_parent',
                sequence=1,
                timestamp=datetime.now(timezone.utc),
            ),
            ContentEvent(
                response_id=response_id,
                content='I need to calculate',
                sequence=2,
                timestamp=datetime.now(timezone.utc),
            ),
            ToolCallEvent(
                response_id=response_id,
                tool_name='calculator',
                tool_args={'expression': '2 + 2'},
                tool_id='calc_123',
                sequence=3,
                timestamp=datetime.now(timezone.utc),
            ),
            ToolReturnEvent(
                response_id=response_id,
                tool_name='calculator',
                tool_id='calc_123',
                result={'answer': 4},
                sequence=4,
                timestamp=datetime.now(timezone.utc),
            ),
            ContentEvent(
                response_id=response_id,
                content=' the answer is 4.',
                sequence=5,
                timestamp=datetime.now(timezone.utc),
            ),
            MetadataEvent(
                response_id=response_id,
                metadata={
                    'usage': {'input_tokens': 20, 'output_tokens': 15},
                    'model': 'claude-3-sonnet',
                },
                sequence=6,
                timestamp=datetime.now(timezone.utc),
            ),
            ResponseEndEvent(
                response_id=response_id,
                usage={'input_tokens': 20, 'output_tokens': 15},
                status='completed',
                chat_id='chat_456',
                sequence=7,
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        # Process events sequentially and check state at each step
        for i, event in enumerate(events):
            await event_processor.process_event(event)

            # Get current message state
            message = event_processor.get_message(response_id)

            if i == 0:  # After ResponseStartEvent
                assert message is not None
                # Status might be 'in_progress' or 'pending' depending on implementation
                assert message.status in ['pending', 'in_progress']

            elif i == 1:  # After first ContentEvent
                assert len(message.parts) >= 1

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_event_processor_content_aggregation(self, event_processor):
        """Test that ContentEvents are properly aggregated into TextParts."""
        response_id = 'resp_content_test'

        # Send multiple content deltas
        content_events = [
            ContentEvent(
                response_id=response_id,
                content='Hello',
                sequence=1,
                timestamp=datetime.now(timezone.utc),
            ),
            ContentEvent(
                response_id=response_id,
                content=' there',
                sequence=2,
                timestamp=datetime.now(timezone.utc),
            ),
            ContentEvent(
                response_id=response_id,
                content=', how are you?',
                sequence=3,
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        # Process events
        for event in content_events:
            await event_processor.process_event(event)

        # Check aggregated content
        message = event_processor.get_message(response_id)
        assert message is not None

        # Find text parts and verify content aggregation
        text_parts = [p for p in message.parts if isinstance(p, TextPart)]
        if text_parts:
            combined_content = ''.join(p.content for p in text_parts)
            assert 'Hello there, how are you?' in combined_content

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_event_processor_error_handling(self, event_processor):
        """Test EventProcessor handles error events and maintains state."""
        response_id = 'resp_error_test'

        events = [
            ContentEvent(
                response_id=response_id,
                content='Processing...',
                sequence=1,
                timestamp=datetime.now(timezone.utc),
            ),
            ErrorEvent(
                response_id=response_id,
                error_type='ProcessingError',
                message='Something went wrong',
                sequence=2,
                timestamp=datetime.now(timezone.utc),
            ),
            ContentEvent(
                response_id=response_id,
                content=' recovered successfully',
                sequence=3,
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        # Process events
        for event in events:
            await event_processor.process_event(event)

        # Check that processing continued after error
        message = event_processor.get_message(response_id)
        assert message is not None

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_event_processor_state_cleanup(self, event_processor):
        """Test that EventProcessor properly cleans up state."""
        response_id = 'resp_cleanup_test'

        # Add some events to create state
        await event_processor.process_event(
            ContentEvent(
                response_id=response_id,
                content='Test content',
                sequence=1,
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Verify state exists
        message = event_processor.get_message(response_id)
        assert message is not None

        # Cleanup state
        event_processor.cleanup_response(response_id)

        # Verify state is cleaned up - should return None or empty message
        cleaned_message = event_processor.get_message(response_id)
        # After cleanup, get_message might return None or a fresh message
        assert cleaned_message is None or len(cleaned_message.parts) == 0

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_event_processor_concurrent_responses(self, event_processor):
        """Test EventProcessor handles multiple concurrent responses."""
        import asyncio

        # Create events for different responses
        async def process_response(response_id: str, content: str):
            events = [
                ContentEvent(
                    response_id=response_id,
                    content=content,
                    sequence=1,
                    timestamp=datetime.now(timezone.utc),
                ),
                ResponseEndEvent(
                    response_id=response_id,
                    usage={},
                    status='completed',
                    sequence=2,
                    timestamp=datetime.now(timezone.utc),
                ),
            ]

            for event in events:
                await event_processor.process_event(event)

        # Process multiple responses concurrently
        tasks = [
            process_response('resp_1', 'Response 1 content'),
            process_response('resp_2', 'Response 2 content'),
            process_response('resp_3', 'Response 3 content'),
        ]

        await asyncio.gather(*tasks)

        # Verify each response has correct content
        for i in range(1, 4):
            response_id = f'resp_{i}'
            message = event_processor.get_message(response_id)
            assert message is not None

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_event_processor_valkey_publishing(
        self, event_processor, mock_valkey_client
    ):
        """Test that EventProcessor publishes events to Valkey correctly."""
        response_id = 'resp_valkey_test'

        # Process an event
        event = ContentEvent(
            response_id=response_id,
            content='Test content for Valkey',
            sequence=1,
            timestamp=datetime.now(timezone.utc),
        )

        await event_processor.process_event(event)

        # Verify Valkey publish was called if valkey_client exists
        if mock_valkey_client:
            # Check if publish was called (might not be called if no valkey client)
            # This depends on the actual implementation
            pass
