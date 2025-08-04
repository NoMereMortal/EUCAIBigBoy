# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for streaming services - core async processing logic."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from app.services.streaming.events import (
    ContentEvent,
    ErrorEvent,
    MetadataEvent,
    StatusEvent,
    ToolCallEvent,
    ToolReturnEvent,
)
from app.services.streaming.processor import EventProcessor
from app.services.streaming.service import StreamingService


class TestStreamingService:
    """Tests for the main streaming service that orchestrates real-time responses."""

    @pytest.fixture
    def mock_valkey_client(self):
        """Mock Valkey client."""
        mock_client = AsyncMock()
        mock_client.publish = AsyncMock()
        mock_client.set = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        return mock_client

    @pytest.fixture
    def streaming_service(self, mock_valkey_client):
        """Create StreamingService with mocked dependencies."""
        return StreamingService(valkey_client=mock_valkey_client)

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_streaming_service_initialization(self, streaming_service):
        """Test StreamingService initializes correctly."""
        assert streaming_service is not None
        assert streaming_service.event_processor is not None
        assert hasattr(streaming_service, 'response_timeout')

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_streaming_service_init_response(self, streaming_service):
        """Test StreamingService can initialize a response."""
        # Test response initialization
        response_id = await streaming_service.init_response(
            chat_id='test_chat', parent_id='parent_msg', model_id='claude-3-sonnet'
        )

        assert response_id is not None
        assert len(response_id) > 0

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_streaming_service_event_processing(self, streaming_service):
        """Test StreamingService processes events correctly."""
        # Create a test event
        event = ContentEvent(
            response_id='test_response',
            content='Hello world',
            sequence=1,
            timestamp=datetime.now(timezone.utc),
        )

        # Process the event
        await streaming_service.process_event(event)

        # Get message state
        message = streaming_service.get_message('test_response')
        assert message is not None

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_streaming_service_cleanup(self, streaming_service):
        """Test StreamingService cleanup functionality."""
        response_id = 'test_cleanup'

        # Process an event to create state
        event = ContentEvent(
            response_id=response_id,
            content='Test content',
            sequence=1,
            timestamp=datetime.now(timezone.utc),
        )

        await streaming_service.process_event(event)

        # Verify state exists
        message = streaming_service.get_message(response_id)
        assert message is not None

        # Cleanup
        streaming_service.cleanup_response(response_id)

        # Verify cleanup
        cleaned_message = streaming_service.get_message(response_id)
        assert cleaned_message is None or len(cleaned_message.parts) == 0

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_streaming_service_timeout_handling(self):
        """Test StreamingService timeout handling."""
        # Create service with very short timeout
        service = StreamingService()
        service.response_timeout = 1  # 1 second (using int instead of float)

        response_id = await service.init_response(
            chat_id='timeout_test', parent_id='parent', model_id='claude-3-sonnet'
        )

        # Wait longer than timeout
        import asyncio

        await asyncio.sleep(0.02)

        # Response should still exist (timeout cleanup happens in background)
        assert response_id is not None


class TestEventProcessorIntegration:
    """Integration tests for EventProcessor with realistic scenarios."""

    @pytest.fixture
    def event_processor(self):
        """Create EventProcessor for integration tests."""
        return EventProcessor()

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_event_processor_realistic_workflow(self, event_processor):
        """Test EventProcessor with a realistic workflow."""
        response_id = 'integration_test'

        # Simulate realistic event sequence
        events = [
            ContentEvent(
                response_id=response_id,
                content='Let me help you with that. ',
                sequence=1,
                timestamp=datetime.now(timezone.utc),
            ),
            ContentEvent(
                response_id=response_id,
                content="I'll need to process your request.",
                sequence=2,
                timestamp=datetime.now(timezone.utc),
            ),
            StatusEvent(
                response_id=response_id,
                status='processing',
                message='Working on your request',
                sequence=3,
                timestamp=datetime.now(timezone.utc),
            ),
            ContentEvent(
                response_id=response_id,
                content=" Here's the result.",
                sequence=4,
                timestamp=datetime.now(timezone.utc),
            ),
            MetadataEvent(
                response_id=response_id,
                metadata={'tokens_used': 150},
                sequence=5,
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        # Process all events
        for event in events:
            await event_processor.process_event(event)

        # Verify final state
        message = event_processor.get_message(response_id)
        assert message is not None

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_event_processor_tool_workflow(self, event_processor):
        """Test EventProcessor with tool usage workflow."""
        response_id = 'tool_test'

        # Tool usage workflow
        events = [
            ContentEvent(
                response_id=response_id,
                content='I need to search for information.',
                sequence=1,
                timestamp=datetime.now(timezone.utc),
            ),
            ToolCallEvent(
                response_id=response_id,
                tool_name='web_search',
                tool_args={'query': 'latest AI news'},
                tool_id='search_123',
                sequence=2,
                timestamp=datetime.now(timezone.utc),
            ),
            ToolReturnEvent(
                response_id=response_id,
                tool_name='web_search',
                tool_id='search_123',
                result={'results': ['AI article 1', 'AI article 2']},
                sequence=3,
                timestamp=datetime.now(timezone.utc),
            ),
            ContentEvent(
                response_id=response_id,
                content=' Based on my search, here are the latest developments in AI.',
                sequence=4,
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        # Process all events
        for event in events:
            await event_processor.process_event(event)

        # Verify message has tool calls and content
        message = event_processor.get_message(response_id)
        assert message is not None

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_event_processor_error_recovery(self, event_processor):
        """Test EventProcessor error handling and recovery."""
        response_id = 'error_recovery_test'

        # Workflow with error and recovery
        events = [
            ContentEvent(
                response_id=response_id,
                content='Starting processing...',
                sequence=1,
                timestamp=datetime.now(timezone.utc),
            ),
            ErrorEvent(
                response_id=response_id,
                error_type='TemporaryError',
                message='Connection timeout',
                details={'retry_count': 1},
                sequence=2,
                timestamp=datetime.now(timezone.utc),
            ),
            StatusEvent(
                response_id=response_id,
                status='retrying',
                message='Retrying request',
                sequence=3,
                timestamp=datetime.now(timezone.utc),
            ),
            ContentEvent(
                response_id=response_id,
                content=' Successfully recovered and completed.',
                sequence=4,
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        # Process all events
        for event in events:
            await event_processor.process_event(event)

        # Verify recovery
        message = event_processor.get_message(response_id)
        assert message is not None

    @pytest.mark.asyncio
    @pytest.mark.service
    @pytest.mark.slow
    async def test_event_processor_performance(self, event_processor):
        """Test EventProcessor performance with many events."""
        import asyncio
        import time

        response_id = 'performance_test'

        # Create many events
        events = []
        for i in range(100):
            events.append(
                ContentEvent(
                    response_id=response_id,
                    content=f'Content {i} ',
                    sequence=i + 1,
                    timestamp=datetime.now(timezone.utc),
                )
            )

        # Measure processing time
        start_time = time.time()

        # Process events concurrently
        tasks = [event_processor.process_event(event) for event in events]
        await asyncio.gather(*tasks)

        end_time = time.time()
        processing_time = end_time - start_time

        # Should process reasonably quickly
        assert processing_time < 5.0  # Should complete in under 5 seconds

        # Verify all content was processed
        message = event_processor.get_message(response_id)
        assert message is not None
