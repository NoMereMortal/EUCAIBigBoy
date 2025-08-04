# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for DemoHandler - predictable task handler for testing streaming patterns."""

import pytest
from app.models import Message, TextPart
from app.services.streaming.events import (
    ContentEvent,
    DocumentEvent,
    ErrorEvent,
    MetadataEvent,
    ReasoningEvent,
    StatusEvent,
    ToolCallEvent,
    ToolReturnEvent,
)
from app.task_handlers.rag_oss.handler import RagOssHandler as DemoHandler


class TestDemoHandler:
    """Tests for DemoHandler - perfect for testing streaming patterns."""

    @pytest.fixture
    def demo_handler(self):
        """Create DemoHandler instance."""
        from unittest.mock import AsyncMock, MagicMock

        from app.clients.bedrock_runtime.client import BedrockRuntimeClient
        from app.clients.opensearch.client import OpenSearchClient

        # Create mock clients
        mock_opensearch_client = AsyncMock(spec=OpenSearchClient)
        mock_bedrock_runtime_client = AsyncMock(spec=BedrockRuntimeClient)

        # Make the AsyncMock behave like a real client for get_sync_client method
        mock_bedrock_runtime_client.get_sync_client = AsyncMock(
            return_value=MagicMock()
        )

        return DemoHandler(
            opensearch_client=mock_opensearch_client,
            bedrock_runtime_client=mock_bedrock_runtime_client,
        )

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_basic_properties(self, demo_handler):
        """Test DemoHandler basic properties and configuration."""
        assert demo_handler.name == 'demo'
        assert 'demo' in demo_handler.description.lower()
        assert isinstance(demo_handler.tools, list)
        assert len(demo_handler.tools) == 0  # Demo handler doesn't use actual tools

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_text_response(self, demo_handler):
        """Test DemoHandler text response pattern."""
        # Create message with "text" keyword
        test_message = Message(
            message_id='msg_123',
            chat_id='chat_456',
            kind='request',
            parts=[TextPart(content='Give me a text response')],
        )

        # Process the message
        events = []
        async for event in demo_handler.handle(
            chat_id='chat_456',
            message_history=[],
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_123',
        ):
            events.append(event)

        # Should get content events
        content_events = [e for e in events if isinstance(e, ContentEvent)]
        assert len(content_events) > 0

        # Check content contains expected text response
        full_content = ''.join(e.content for e in content_events)
        assert len(full_content) > 0
        assert any(
            word in full_content.lower() for word in ['demo', 'text', 'response']
        )

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_streaming_response(self, demo_handler):
        """Test DemoHandler streaming text response with multiple deltas."""
        # Create message with "streaming" keyword
        test_message = Message(
            message_id='msg_stream',
            chat_id='chat_stream',
            kind='request',
            parts=[TextPart(content='Show me streaming response')],
        )

        # Process the message
        events = []
        async for event in demo_handler.handle(
            chat_id='chat_stream',
            message_history=[],
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_stream',
        ):
            events.append(event)

        # Should get multiple content events (streaming pattern)
        content_events = [e for e in events if isinstance(e, ContentEvent)]
        assert len(content_events) >= 3  # Should have multiple deltas

        # Events should have sequential order
        for i, event in enumerate(content_events):
            assert event.sequence == i + 1

        # Content should build up over time
        accumulated_content = ''
        for event in content_events:
            accumulated_content += event.content
            assert len(accumulated_content) > 0

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_tool_response(self, demo_handler):
        """Test DemoHandler tool call and return pattern."""
        # Create message with "tool" keyword
        test_message = Message(
            message_id='msg_tool',
            chat_id='chat_tool',
            kind='request',
            parts=[TextPart(content='Use a tool to calculate something')],
        )

        # Process the message
        events = []
        async for event in demo_handler.handle(
            chat_id='chat_tool',
            message_history=[],
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_tool',
        ):
            events.append(event)

        # Should have tool call and return events
        tool_call_events = [e for e in events if isinstance(e, ToolCallEvent)]
        tool_return_events = [e for e in events if isinstance(e, ToolReturnEvent)]

        assert len(tool_call_events) >= 1
        assert len(tool_return_events) >= 1

        # Check tool call details
        tool_call = tool_call_events[0]
        assert tool_call.tool_name == 'calculator'
        assert isinstance(tool_call.tool_args, dict)
        assert tool_call.tool_id is not None

        # Check tool return details
        tool_return = tool_return_events[0]
        assert tool_return.tool_name == 'calculator'
        assert tool_return.tool_id == tool_call.tool_id
        assert tool_return.result is not None

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_document_response(self, demo_handler):
        """Test DemoHandler document response pattern."""
        # Create message with "document" keyword
        test_message = Message(
            message_id='msg_doc',
            chat_id='chat_doc',
            kind='request',
            parts=[TextPart(content='Show me a document response')],
        )

        # Process the message
        events = []
        async for event in demo_handler.handle(
            chat_id='chat_doc',
            message_history=[],
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_doc',
        ):
            events.append(event)

        # Should have document events
        document_events = [e for e in events if isinstance(e, DocumentEvent)]
        assert len(document_events) >= 1

        # Check document event details
        doc_event = document_events[0]
        assert hasattr(doc_event, 'document_id')
        assert hasattr(doc_event, 'title')
        assert hasattr(doc_event, 'content_preview')

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_metadata_response(self, demo_handler):
        """Test DemoHandler metadata response pattern."""
        # Create message with "metadata" keyword
        test_message = Message(
            message_id='msg_meta',
            chat_id='chat_meta',
            kind='request',
            parts=[TextPart(content='Show me metadata response')],
        )

        # Process the message
        events = []
        async for event in demo_handler.handle(
            chat_id='chat_meta',
            message_history=[],
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_meta',
        ):
            events.append(event)

        # Should have metadata events
        metadata_events = [e for e in events if isinstance(e, MetadataEvent)]
        assert len(metadata_events) >= 1

        # Check metadata content
        meta_event = metadata_events[0]
        assert isinstance(meta_event.metadata, dict)
        assert len(meta_event.metadata) > 0

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_reasoning_response(self, demo_handler):
        """Test DemoHandler reasoning response pattern."""
        # Create message with "reasoning" keyword
        test_message = Message(
            message_id='msg_reason',
            chat_id='chat_reason',
            kind='request',
            parts=[TextPart(content='Show me reasoning response')],
        )

        # Process the message
        events = []
        async for event in demo_handler.handle(
            chat_id='chat_reason',
            message_history=[],
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_reason',
        ):
            events.append(event)

        # Should have reasoning events
        reasoning_events = [e for e in events if isinstance(e, ReasoningEvent)]
        assert len(reasoning_events) >= 1

        # Check reasoning content
        reasoning_event = reasoning_events[0]
        assert hasattr(reasoning_event, 'text')  # Using 'text' attribute
        assert reasoning_event.text is not None
        assert len(reasoning_event.text) > 0

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_status_response(self, demo_handler):
        """Test DemoHandler status updates pattern."""
        # Create message with "status" keyword
        test_message = Message(
            message_id='msg_status',
            chat_id='chat_status',
            kind='request',
            parts=[TextPart(content='Show me status updates')],
        )

        # Process the message
        events = []
        async for event in demo_handler.handle(
            chat_id='chat_status',
            message_history=[],
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_status',
        ):
            events.append(event)

        # Should have status events
        status_events = [e for e in events if isinstance(e, StatusEvent)]
        assert len(status_events) >= 1

        # Check status progression
        for status_event in status_events:
            assert status_event.status in ['processing', 'completed', 'pending']

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_error_response(self, demo_handler):
        """Test DemoHandler error handling pattern."""
        # Create message with "error" keyword
        test_message = Message(
            message_id='msg_error',
            chat_id='chat_error',
            kind='request',
            parts=[TextPart(content='Trigger an error response')],
        )

        # Process the message
        events = []
        async for event in demo_handler.handle(
            chat_id='chat_error',
            message_history=[],
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_error',
        ):
            events.append(event)

        # Should have error events
        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert len(error_events) >= 1

        # Check error details
        error_event = error_events[0]
        assert error_event.error_type is not None
        assert (
            error_event.message is not None
        )  # Using 'message' instead of 'error_message'
        assert len(error_event.message) > 0

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_complex_response(self, demo_handler):
        """Test DemoHandler complex multi-part response."""
        # Create message with "complex" keyword
        test_message = Message(
            message_id='msg_complex',
            chat_id='chat_complex',
            kind='request',
            parts=[TextPart(content='Show me a complex response')],
        )

        # Process the message
        events = []
        async for event in demo_handler.handle(
            chat_id='chat_complex',
            message_history=[],
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_complex',
        ):
            events.append(event)

        # Should have multiple types of events
        event_types = {type(e).__name__ for e in events}
        assert len(event_types) >= 3  # Should have variety of event types

        # Should have content events
        content_events = [e for e in events if isinstance(e, ContentEvent)]
        assert len(content_events) >= 1

        # Events should be properly sequenced
        sequences = [e.sequence for e in events]
        assert sequences == sorted(sequences)  # Should be in order

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_help_response(self, demo_handler):
        """Test DemoHandler default help response."""
        # Create message without specific keywords
        test_message = Message(
            message_id='msg_help',
            chat_id='chat_help',
            kind='request',
            parts=[TextPart(content='What can you do?')],
        )

        # Process the message
        events = []
        async for event in demo_handler.handle(
            chat_id='chat_help',
            message_history=[],
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_help',
        ):
            events.append(event)

        # Should get help content
        content_events = [e for e in events if isinstance(e, ContentEvent)]
        assert len(content_events) > 0

        # Help content should mention available keywords
        full_content = ''.join(e.content for e in content_events)
        help_keywords = ['text', 'streaming', 'tool', 'document', 'metadata']
        assert any(keyword in full_content.lower() for keyword in help_keywords)

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    @pytest.mark.slow
    async def test_demo_handler_performance_streaming(self, demo_handler):
        """Test DemoHandler streaming performance with timing."""
        import time

        test_message = Message(
            message_id='msg_perf',
            chat_id='chat_perf',
            kind='request',
            parts=[TextPart(content='streaming performance test')],
        )

        # Measure streaming performance
        start_time = time.time()
        events = []

        async for event in demo_handler.handle(
            chat_id='chat_perf',
            message_history=[],
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_perf',
        ):
            events.append(event)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete in reasonable time
        assert duration < 5.0  # Should be fast for demo handler

        # Should have produced events
        assert len(events) > 0

        # Events should have reasonable timing intervals
        if len(events) > 1:
            # Calculate average time between events
            avg_interval = duration / len(events)
            assert avg_interval < 1.0  # Each event should be quick

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_demo_handler_message_history_handling(self, demo_handler):
        """Test DemoHandler handles message history correctly."""
        # Create message history
        history = [
            Message(
                message_id='hist_1',
                chat_id='chat_hist',
                kind='request',
                parts=[TextPart(content='Previous question')],
            ),
            Message(
                message_id='hist_2',
                chat_id='chat_hist',
                kind='response',
                parts=[TextPart(content='Previous answer')],
            ),
        ]

        test_message = Message(
            message_id='current_msg',
            chat_id='chat_hist',
            kind='request',
            parts=[TextPart(content='Current question with text response')],
        )

        # Process with history
        events = []
        async for event in demo_handler.handle(
            chat_id='chat_hist',
            message_history=history,
            user_message=test_message,
            model_id='demo-model',
            response_message_id='resp_hist',
        ):
            events.append(event)

        # Should still process normally with history
        assert len(events) > 0
        content_events = [e for e in events if isinstance(e, ContentEvent)]
        assert len(content_events) > 0
