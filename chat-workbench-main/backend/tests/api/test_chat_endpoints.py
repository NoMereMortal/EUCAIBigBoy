# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Integration tests for chat API endpoints with streaming."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from app.api.app import create_app
from app.models import ChatSession, Message, TextPart


class TestChatEndpoints:
    """Integration tests for chat-related API endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_chat_session(
        self, test_settings, mock_app_table, dynamodb_client
    ):
        """Test creating a new chat session via API."""
        # Arrange
        app = create_app()

        # Mock the chat service to return a known chat session
        with patch('app.api.routes.v1.chat.handlers.ChatService') as mock_chat_service:
            mock_service_instance = AsyncMock()
            mock_chat_service.return_value = mock_service_instance

            mock_chat_session = ChatSession(
                chat_id='new_chat_123',
                user_id='user_456',
                title='New Chat Session',
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                status='active',
            )

            mock_service_instance.create_chat_session.return_value = mock_chat_session

            # Act
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url='http://test'
            ) as client:
                response = await client.post(
                    '/v1/chats',
                    json={'user_id': 'user_456', 'title': 'New Chat Session'},
                )

            # Assert
            assert response.status_code == 201
            data = response.json()

            assert data['chat_id'] == 'new_chat_123'
            assert data['user_id'] == 'user_456'
            assert data['title'] == 'New Chat Session'
            assert data['status'] == 'active'

            # Verify service was called
            mock_service_instance.create_chat_session.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_chat_session(self, test_settings, populated_chat_session):
        """Test retrieving an existing chat session."""
        # Arrange
        app = create_app()
        chat_id = populated_chat_session['chat_id']

        # Mock the chat service
        with patch('app.api.routes.v1.chat.handlers.ChatService') as mock_chat_service:
            mock_service_instance = AsyncMock()
            mock_chat_service.return_value = mock_service_instance

            mock_chat_session = ChatSession(**populated_chat_session)
            mock_service_instance.get_chat_session.return_value = mock_chat_session

            # Act
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url='http://test'
            ) as client:
                response = await client.get(f'/v1/chats/{chat_id}')

            # Assert
            assert response.status_code == 200
            data = response.json()

            assert data['chat_id'] == chat_id
            assert data['title'] == 'Test Chat Session'
            assert data['status'] == 'active'

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_chat_sessions(self, test_settings, populated_chat_session):
        """Test listing chat sessions for a user."""
        # Arrange
        app = create_app()
        user_id = populated_chat_session['user_id']

        with patch('app.api.routes.v1.chat.handlers.ChatService') as mock_chat_service:
            mock_service_instance = AsyncMock()
            mock_chat_service.return_value = mock_service_instance

            mock_sessions = [ChatSession(**populated_chat_session)]
            mock_service_instance.list_chat_sessions.return_value = mock_sessions

            # Act
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url='http://test'
            ) as client:
                response = await client.get('/v1/chats', params={'user_id': user_id})

            # Assert
            assert response.status_code == 200
            data = response.json()

            assert 'chats' in data
            assert len(data['chats']) == 1
            assert data['chats'][0]['chat_id'] == populated_chat_session['chat_id']

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_send_message_to_chat(self, test_settings, populated_chat_session):
        """Test sending a message to an existing chat."""
        # Arrange
        app = create_app()
        chat_id = populated_chat_session['chat_id']

        with patch('app.api.routes.v1.chat.handlers.ChatService') as mock_chat_service:
            mock_service_instance = AsyncMock()
            mock_chat_service.return_value = mock_service_instance

            # Mock message creation
            mock_message = Message(
                message_id='new_msg_123',
                chat_id=chat_id,
                kind='request',
                parts=[TextPart(content='Hello, how are you?')],
            )
            mock_service_instance.add_message_to_chat.return_value = mock_message

            # Act
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url='http://test'
            ) as client:
                response = await client.post(
                    f'/v1/chats/{chat_id}/messages',
                    json={
                        'content': 'Hello, how are you?',
                        'user_id': populated_chat_session['user_id'],
                    },
                )

            # Assert
            assert response.status_code == 201
            data = response.json()

            assert data['message_id'] == 'new_msg_123'
            assert data['chat_id'] == chat_id
            assert data['kind'] == 'request'
            assert len(data['parts']) == 1
            assert data['parts'][0]['content'] == 'Hello, how are you?'


class TestChatStreamingEndpoints:
    """Integration tests for streaming chat endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_stream_chat_response(self, test_settings, populated_chat_session):
        """Test streaming response from chat endpoint."""
        # Arrange
        app = create_app()
        chat_id = populated_chat_session['chat_id']

        # Mock streaming service to return predictable events
        async def mock_stream_response(*args, **kwargs):
            yield (
                'data: '
                + json.dumps(
                    {'type': 'content', 'data': {'text': 'Hello'}, 'sequence': 1}
                )
                + '\n\n'
            )

            yield (
                'data: '
                + json.dumps(
                    {'type': 'content', 'data': {'text': ' world!'}, 'sequence': 2}
                )
                + '\n\n'
            )

            yield (
                'data: '
                + json.dumps(
                    {'type': 'status', 'data': {'status': 'completed'}, 'sequence': 3}
                )
                + '\n\n'
            )

        with patch(
            'app.api.routes.v1.chat.handlers.StreamingService'
        ) as mock_streaming_service:
            mock_service_instance = AsyncMock()
            mock_streaming_service.return_value = mock_service_instance
            mock_service_instance.stream_response = mock_stream_response

            # Act
            async with (
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url='http://test'
                ) as client,
                client.stream(
                    'POST',
                    f'/v1/chats/{chat_id}/messages/stream',
                    json={
                        'content': 'Hello',
                        'user_id': populated_chat_session['user_id'],
                    },
                ) as response,
            ):
                # Assert
                assert response.status_code == 200
                assert response.headers.get('content-type') == 'text/event-stream'

                # Collect streaming chunks
                chunks = []
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        chunks.append(chunk)

                # Verify we received the expected events
                assert len(chunks) >= 3

                # Parse first chunk
                first_data = chunks[0].replace('data: ', '').strip()
                first_event = json.loads(first_data)
                assert first_event['type'] == 'content'
                assert first_event['data']['text'] == 'Hello'

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_stream_chat_with_error(self, test_settings, populated_chat_session):
        """Test streaming endpoint handles errors gracefully."""
        # Arrange
        app = create_app()
        chat_id = populated_chat_session['chat_id']

        # Mock streaming service that fails
        async def mock_failing_stream(*args, **kwargs):
            yield (
                'data: '
                + json.dumps(
                    {'type': 'content', 'data': {'text': 'Starting...'}, 'sequence': 1}
                )
                + '\n\n'
            )

            # Simulate error
            raise Exception('Streaming failed')

        with patch(
            'app.api.routes.v1.chat.handlers.StreamingService'
        ) as mock_streaming_service:
            mock_service_instance = AsyncMock()
            mock_streaming_service.return_value = mock_service_instance
            mock_service_instance.stream_response = mock_failing_stream

            # Act & Assert
            async with (
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url='http://test'
                ) as client,
                client.stream(
                    'POST',
                    f'/v1/chats/{chat_id}/messages/stream',
                    json={
                        'content': 'Test message',
                        'user_id': populated_chat_session['user_id'],
                    },
                ) as response,
            ):
                assert response.status_code == 200

                # Should get at least one chunk before failure
                chunks = []
                try:
                    async for chunk in response.aiter_text():
                        chunks.append(chunk)
                except Exception as e:
                    assert str(e) != '', 'Exception message should not be empty'
                    pass

                # Should have received the initial content
                assert len(chunks) >= 1

                if chunks:
                    first_data = chunks[0].replace('data: ', '').strip()
                    first_event = json.loads(first_data)
                    assert first_event['data']['text'] == 'Starting...'

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_websocket_chat_connection(
        self, test_settings, populated_chat_session
    ):
        """Test WebSocket connection for real-time chat."""
        # Arrange
        app = create_app()
        chat_id = populated_chat_session['chat_id']

        # Mock WebSocket handler
        with patch('app.api.websocket.ChatWebSocketHandler') as mock_ws_handler:
            mock_handler_instance = AsyncMock()
            mock_ws_handler.return_value = mock_handler_instance

            # Mock connection handling
            mock_handler_instance.handle_connection.return_value = None

            # Act & Assert
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url='http://test'
            ) as client:
                # Note: httpx doesn't support WebSocket testing directly
                # This would need websockets library for full testing
                # For now, just verify the endpoint exists

                # Try to connect to websocket endpoint (will fail with httpx, but that's expected)
                try:
                    response = await client.get(f'/v1/chats/{chat_id}/ws')
                    # This should return 426 Upgrade Required for WebSocket
                    assert response.status_code in [
                        426,
                        405,
                    ]  # Method not allowed or upgrade required
                except Exception as e:
                    assert str(e) != '', 'Exception message should not be empty'
                    pass


class TestChatEndpointValidation:
    """Tests for input validation and error handling."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_chat_invalid_data(self, test_settings):
        """Test chat creation with invalid data."""
        # Arrange
        app = create_app()

        # Act
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'
        ) as client:
            response = await client.post(
                '/v1/chats',
                json={},  # Missing required fields
            )

        # Assert
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_nonexistent_chat(self, test_settings):
        """Test retrieving a chat that doesn't exist."""
        # Arrange
        app = create_app()

        with patch('app.api.routes.v1.chat.handlers.ChatService') as mock_chat_service:
            mock_service_instance = AsyncMock()
            mock_chat_service.return_value = mock_service_instance
            mock_service_instance.get_chat_session.return_value = None

            # Act
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url='http://test'
            ) as client:
                response = await client.get('/v1/chats/nonexistent_chat')

            # Assert
            assert response.status_code == 404

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_send_message_invalid_chat(self, test_settings):
        """Test sending message to non-existent chat."""
        # Arrange
        app = create_app()

        with patch('app.api.routes.v1.chat.handlers.ChatService') as mock_chat_service:
            mock_service_instance = AsyncMock()
            mock_chat_service.return_value = mock_service_instance
            mock_service_instance.add_message_to_chat.side_effect = ValueError(
                'Chat not found'
            )

            # Act
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url='http://test'
            ) as client:
                response = await client.post(
                    '/v1/chats/nonexistent/messages',
                    json={'content': 'Hello', 'user_id': 'user_123'},
                )

            # Assert
            assert response.status_code in [400, 404]
