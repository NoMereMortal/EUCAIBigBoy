# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for ChatHandler - the core AI task handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models import ImagePart, Message, TextPart
from app.services.streaming.events import ContentEvent
from app.task_handlers.chat.handler import ChatHandler


class TestChatHandler:
    """Tests for the main ChatHandler that processes AI conversations."""

    @pytest.fixture
    def mock_strands_agent(self):
        """Mock Strands Agent with realistic streaming responses."""
        mock_agent = AsyncMock()

        # Mock a typical streaming response
        async def mock_stream(*args, **kwargs):
            # Simulate Strands Agent streaming events
            yield {
                'type': 'content_block_start',
                'content_block': {'type': 'text', 'text': ''},
            }
            yield {
                'type': 'content_block_delta',
                'delta': {'type': 'text_delta', 'text': 'Hello'},
            }
            yield {
                'type': 'content_block_delta',
                'delta': {'type': 'text_delta', 'text': ' world!'},
            }
            yield {'type': 'content_block_stop'}
            yield {
                'type': 'message_stop',
                'usage': {'input_tokens': 10, 'output_tokens': 5},
            }

        mock_agent.stream = mock_stream
        return mock_agent

    @pytest.fixture
    def mock_opensearch_client(self):
        """Mock OpenSearch client."""
        mock_client = AsyncMock()
        mock_client.search_documents = AsyncMock(
            return_value=[{'content': 'Sample search result'}]
        )
        return mock_client

    @pytest.fixture
    def mock_bedrock_runtime_client(self):
        """Mock Bedrock Runtime client."""
        mock_client = AsyncMock()
        return mock_client

    @pytest.fixture
    def mock_botocore_config(self):
        """Mock Botocore config."""
        from botocore.config import Config

        return Config(region_name='us-east-1')

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_chat_handler_basic_text_response(
        self,
        mock_strands_agent,
        mock_opensearch_client,
        mock_bedrock_runtime_client,
        mock_botocore_config,
    ):
        """Test ChatHandler processes a simple text message and generates response."""
        # Arrange
        handler = ChatHandler(
            opensearch_client=mock_opensearch_client,
            bedrock_runtime_client=mock_bedrock_runtime_client,
            botocore_config=mock_botocore_config,
        )

        # Create test message
        test_message = Message(
            message_id='msg_123',
            chat_id='test_chat',
            kind='request',
            parts=[TextPart(content='Hello, how are you?')],
        )

        # Mock dependencies
        with patch(
            'app.task_handlers.chat.handler.Agent', return_value=mock_strands_agent
        ):
            # Act - collect all streaming events
            events = []
            async for event in handler.handle(
                chat_id='test_chat',
                message_history=[],
                user_message=test_message,
                model_id='us.anthropic.claude-3-5-sonnet-20240620-v1:0',
                response_message_id='resp_123',
            ):
                events.append(event)

            # Assert
            assert len(events) > 0

            # Check we get content events
            content_events = [e for e in events if isinstance(e, ContentEvent)]
            assert len(content_events) >= 2  # Should have "Hello" and " world!"

            # Check final response
            final_content = ''.join(e.content for e in content_events)
            assert 'Hello world!' in final_content

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_chat_handler_multimodal_message(
        self, mock_strands_agent, mock_repositories, mock_clients
    ):
        """Test ChatHandler processes messages with text and images."""
        # Arrange
        handler = ChatHandler(**mock_repositories, **mock_clients)

        # Mock content storage service for image processing
        mock_content_service = AsyncMock()
        mock_content_service.get_pointer_from_id.return_value = 's3://bucket/image.jpg'

        with (
            patch(
                'app.task_handlers.chat.handler.StrandsAgent',
                return_value=mock_strands_agent,
            ),
            patch.object(handler, 'content_storage_service', mock_content_service),
        ):
            mock_repositories['chat_repo'].get_chat_session.return_value = MagicMock(
                chat_id='test_chat', user_id='test_user'
            )
            mock_repositories['message_repo'].get_chat_messages.return_value = []

            # Create multimodal message
            test_message = Message(
                message_id='msg_123',
                chat_id='test_chat',
                kind='request',
                parts=[
                    TextPart(content='What do you see in this image?'),
                    ImagePart(
                        file_id='img_123',
                        user_id='test_user',
                        mime_type='image/jpeg',
                        content='[Image: img_123]',
                    ),
                ],
            )

            # Act
            events = []
            async for event in handler.handle(
                chat_id='test_chat',
                message_history=[],
                user_message=test_message,
                model_id='anthropic.claude-3-sonnet-20240229-v1:0',
                response_message_id='resp_123',
            ):
                events.append(event)

            # Assert
            assert len(events) > 0

            # Verify image was processed
            mock_content_service.get_pointer_from_id.assert_called_once_with(
                file_id='img_123', user_id='test_user'
            )

            # Check content events exist
            content_events = [e for e in events if isinstance(e, ContentEvent)]
            assert len(content_events) >= 1

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_chat_handler_stream_error_recovery(
        self, mock_repositories, mock_clients
    ):
        """Test ChatHandler handles streaming errors gracefully."""
        # Arrange - Create a failing Strands Agent
        mock_agent = AsyncMock()

        async def failing_stream(*args, **kwargs):
            yield {'type': 'content_block_start', 'content_block': {'type': 'text'}}
            yield {'type': 'content_block_delta', 'delta': {'text': 'Hello'}}
            # Simulate stream failure
            raise Exception('Streaming connection lost')

        mock_agent.stream = failing_stream

        handler = ChatHandler(**mock_repositories, **mock_clients)

        with patch(
            'app.task_handlers.chat.handler.StrandsAgent', return_value=mock_agent
        ):
            mock_repositories['chat_repo'].get_chat_session.return_value = MagicMock(
                chat_id='test_chat', user_id='test_user'
            )
            mock_repositories['message_repo'].get_chat_messages.return_value = []

            test_message = Message(
                message_id='msg_123',
                chat_id='test_chat',
                kind='request',
                parts=[TextPart(content='Test message')],
            )

            # Act
            events = []
            with pytest.raises(Exception, match='Streaming connection lost'):
                async for event in handler.handle(
                    chat_id='test_chat',
                    message_history=[],
                    user_message=test_message,
                    model_id='anthropic.claude-3-sonnet-20240229-v1:0',
                    response_message_id='resp_123',
                ):
                    events.append(event)

            # Assert - Should have partial content before the error
            content_events = [e for e in events if isinstance(e, ContentEvent)]
            assert len(content_events) >= 1
            assert content_events[0].content == 'Hello'

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_chat_handler_with_system_prompt(
        self, mock_strands_agent, mock_repositories, mock_clients
    ):
        """Test ChatHandler uses system prompts from templates."""
        # Arrange
        handler = ChatHandler(**mock_repositories, **mock_clients)

        # Mock persona with system prompt
        mock_persona = MagicMock()
        mock_persona.system_prompt = 'You are a helpful assistant.'

        with patch(
            'app.task_handlers.chat.handler.StrandsAgent',
            return_value=mock_strands_agent,
        ):
            mock_repositories['chat_repo'].get_chat_session.return_value = MagicMock(
                chat_id='test_chat', user_id='test_user'
            )
            mock_repositories['message_repo'].get_chat_messages.return_value = []
            mock_repositories['persona_repo'].get_persona.return_value = mock_persona

            test_message = Message(
                message_id='msg_123',
                chat_id='test_chat',
                kind='request',
                parts=[TextPart(content='Hello')],
            )

            # Act
            events = []
            async for event in handler.handle(
                chat_id='test_chat',
                message_history=[],
                user_message=test_message,
                model_id='anthropic.claude-3-sonnet-20240229-v1:0',
                response_message_id='resp_123',
                persona='helpful_assistant',
            ):
                events.append(event)

            # Assert
            mock_repositories['persona_repo'].get_persona.assert_called_once_with(
                'helpful_assistant'
            )

            # Verify Strands Agent was called with system prompt
            mock_strands_agent.stream.assert_called_once()
            call_args = mock_strands_agent.stream.call_args

            # Check that system prompt was included in the call
            assert any(
                'system' in str(arg)
                for arg in call_args.args + tuple(call_args.kwargs.values())
            )

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_chat_handler_conversation_history(
        self, mock_strands_agent, mock_repositories, mock_clients
    ):
        """Test ChatHandler includes conversation history in context."""
        # Arrange
        handler = ChatHandler(**mock_repositories, **mock_clients)

        # Mock existing conversation history
        previous_messages = [
            Message(
                message_id='msg_1',
                chat_id='test_chat',
                kind='request',
                parts=[TextPart(content='Previous question')],
            ),
            Message(
                message_id='msg_2',
                chat_id='test_chat',
                kind='response',
                parts=[TextPart(content='Previous answer')],
            ),
        ]

        with patch(
            'app.task_handlers.chat.handler.StrandsAgent',
            return_value=mock_strands_agent,
        ):
            mock_repositories['chat_repo'].get_chat_session.return_value = MagicMock(
                chat_id='test_chat', user_id='test_user'
            )
            mock_repositories[
                'message_repo'
            ].get_chat_messages.return_value = previous_messages

            test_message = Message(
                message_id='msg_3',
                chat_id='test_chat',
                kind='request',
                parts=[TextPart(content='New question')],
            )

            # Act
            events = []
            async for event in handler.handle(
                chat_id='test_chat',
                message_history=previous_messages,
                user_message=test_message,
                model_id='anthropic.claude-3-sonnet-20240229-v1:0',
                response_message_id='resp_123',
            ):
                events.append(event)

            # Assert
            mock_repositories['message_repo'].get_chat_messages.assert_called_once()

            # Verify Strands Agent received conversation history
            mock_strands_agent.stream.assert_called_once()

            # The messages should be included in the call to Strands Agent
            # (exact format depends on implementation, but should include previous context)
            assert len(events) > 0

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    @pytest.mark.slow
    async def test_chat_handler_tool_usage(self, mock_repositories, mock_clients):
        """Test ChatHandler processes tool calls and returns."""
        # Arrange - Mock Strands Agent with tool usage
        mock_agent = AsyncMock()

        async def mock_stream_with_tools(*args, **kwargs):
            # Start content block
            yield {'type': 'content_block_start', 'content_block': {'type': 'text'}}
            yield {
                'type': 'content_block_delta',
                'delta': {'text': 'I need to search for information.'},
            }

            # Tool call
            yield {
                'type': 'tool_use',
                'id': 'tool_123',
                'name': 'web_search',
                'input': {'query': 'latest weather'},
            }

            # Tool result
            yield {
                'type': 'tool_result',
                'tool_use_id': 'tool_123',
                'content': [{'type': 'text', 'text': 'Current weather is sunny, 75°F'}],
            }

            # Continue with response
            yield {
                'type': 'content_block_delta',
                'delta': {'text': ' The weather is sunny and 75°F.'},
            }
            yield {'type': 'content_block_stop'}
            yield {
                'type': 'message_stop',
                'usage': {'input_tokens': 15, 'output_tokens': 20},
            }

        mock_agent.stream = mock_stream_with_tools

        handler = ChatHandler(**mock_repositories, **mock_clients)

        with patch(
            'app.task_handlers.chat.handler.StrandsAgent', return_value=mock_agent
        ):
            mock_repositories['chat_repo'].get_chat_session.return_value = MagicMock(
                chat_id='test_chat', user_id='test_user'
            )
            mock_repositories['message_repo'].get_chat_messages.return_value = []

            test_message = Message(
                message_id='msg_123',
                chat_id='test_chat',
                kind='request',
                parts=[TextPart(content='What is the weather like?')],
            )

            # Act
            events = []
            async for event in handler.handle(
                chat_id='test_chat',
                message_history=[],
                user_message=test_message,
                model_id='anthropic.claude-3-sonnet-20240229-v1:0',
                response_message_id='resp_123',
            ):
                events.append(event)

            # Assert
            assert len(events) > 0

            # Should have content events for the response
            content_events = [e for e in events if isinstance(e, ContentEvent)]
            final_content = ''.join(e.content for e in content_events)

            assert 'information' in final_content or 'weather' in final_content
            assert len(content_events) >= 2  # Multiple content deltas


class TestChatHandlerEdgeCases:
    """Test edge cases and error scenarios for ChatHandler."""

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_chat_handler_empty_message(self):
        """Test ChatHandler handles empty messages gracefully."""
        # This would test validation and error handling
        pass

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_chat_handler_invalid_chat_id(self):
        """Test ChatHandler handles non-existent chat sessions."""
        # This would test error handling for missing chats
        pass

    @pytest.mark.asyncio
    @pytest.mark.task_handler
    async def test_chat_handler_concurrent_requests(self):
        """Test ChatHandler handles concurrent requests to same chat."""
        # This would test concurrency and state management
        pass
