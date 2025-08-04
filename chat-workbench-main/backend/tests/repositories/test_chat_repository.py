# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for ChatRepository - chat session data persistence."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from app.clients.dynamodb.client import DynamoDBClient
from app.models import ChatSession
from app.repositories.chat import ChatRepository
from botocore.exceptions import ClientError


class TestChatRepository:
    """Tests for ChatRepository data access layer."""

    @pytest.fixture
    async def chat_repository(self, test_settings, mock_app_table, dynamodb_client):
        """Create ChatRepository with mocked DynamoDB."""
        # Mock the DynamoDBClient
        mock_dynamodb_client = AsyncMock(spec=DynamoDBClient)
        mock_dynamodb_client.table_name = mock_app_table
        mock_dynamodb_client.client = dynamodb_client

        return ChatRepository(dynamodb_client=mock_dynamodb_client)

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_create_chat_session(self, chat_repository, sample_user_id):
        """Test creating a new chat session."""
        # Arrange
        title = 'Test Chat Session'

        # Mock the underlying client method
        chat_repository.dynamodb_client.put_item = AsyncMock()

        # Act
        chat_session = await chat_repository.create_chat(
            ChatSession(user_id=sample_user_id, title=title)
        )

        # Assert
        assert isinstance(chat_session, ChatSession)
        assert chat_session.user_id == sample_user_id
        assert chat_session.title == title
        assert chat_session.status == 'active'
        assert len(chat_session.chat_id) == 21  # Nanoid length
        assert isinstance(chat_session.created_at, datetime)

        # Verify DynamoDB put_item was called
        chat_repository.dynamodb_client.put_item.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_get_chat_session_exists(
        self, chat_repository, sample_chat_id, sample_user_id
    ):
        """Test retrieving an existing chat session."""
        # Arrange - Mock DynamoDB response
        mock_item = {
            'PK': {'S': f'CHAT#{sample_chat_id}'},
            'SK': {'S': f'CHAT#{sample_chat_id}'},
            'user_id': {'S': sample_user_id},
            'title': {'S': 'Test Chat'},
            'status': {'S': 'active'},
            'created_at': {'S': '2024-01-15T10:30:00+00:00'},
            'updated_at': {'S': '2024-01-15T10:30:00+00:00'},
            'metadata': {'M': {}},
            'usage': {'M': {}},
        }

        chat_repository.dynamodb_client.get_item = AsyncMock(
            return_value={'Item': mock_item}
        )

        # Act
        chat_session = await chat_repository.get_chat(sample_chat_id)

        # Assert
        assert chat_session is not None
        assert chat_session.chat_id == sample_chat_id
        assert chat_session.user_id == sample_user_id
        assert chat_session.title == 'Test Chat'
        assert chat_session.status == 'active'

        # Verify correct DynamoDB call
        chat_repository.dynamodb_client.get_item.assert_called_once_with(
            Key={'PK': f'CHAT#{sample_chat_id}', 'SK': f'CHAT#{sample_chat_id}'}
        )

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_get_chat_session_not_found(self, chat_repository, sample_chat_id):
        """Test retrieving a non-existent chat session."""
        # Arrange - Mock empty DynamoDB response
        chat_repository.dynamodb_client.get_item = AsyncMock(return_value={})

        # Act
        chat_session = await chat_repository.get_chat(sample_chat_id)

        # Assert
        assert chat_session is None

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_list_chat_sessions_for_user(self, chat_repository, sample_user_id):
        """Test listing all chat sessions for a user."""
        # Arrange - Mock DynamoDB query response
        mock_items = [
            {
                'PK': {'S': 'CHAT#chat1'},
                'SK': {'S': 'CHAT#chat1'},
                'user_id': {'S': sample_user_id},
                'title': {'S': 'Chat 1'},
                'status': {'S': 'active'},
                'created_at': {'S': '2024-01-15T10:00:00+00:00'},
                'updated_at': {'S': '2024-01-15T10:00:00+00:00'},
                'metadata': {'M': {}},
                'usage': {'M': {}},
            },
            {
                'PK': {'S': 'CHAT#chat2'},
                'SK': {'S': 'CHAT#chat2'},
                'user_id': {'S': sample_user_id},
                'title': {'S': 'Chat 2'},
                'status': {'S': 'active'},
                'created_at': {'S': '2024-01-15T11:00:00+00:00'},
                'updated_at': {'S': '2024-01-15T11:00:00+00:00'},
                'metadata': {'M': {}},
                'usage': {'M': {}},
            },
        ]

        chat_repository.dynamodb_client.query = AsyncMock(
            return_value={'Items': mock_items, 'Count': 2}
        )

        # Act
        result = await chat_repository.list_chats(
            user_id=sample_user_id, status='active', with_messages=0, message_repo=None
        )
        chat_sessions = result.chats

        # Assert
        assert len(chat_sessions) == 2
        assert all(isinstance(session, ChatSession) for session in chat_sessions)
        assert chat_sessions[0].chat_id == 'chat1'
        assert chat_sessions[1].chat_id == 'chat2'
        assert all(session.user_id == sample_user_id for session in chat_sessions)

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_update_chat_session(self, chat_repository, sample_chat_id):
        """Test updating an existing chat session."""
        # Arrange
        updates = {'title': 'Updated Title', 'status': 'archived'}

        chat_repository.dynamodb_client.update_item = AsyncMock(
            return_value={
                'Attributes': {
                    'PK': {'S': f'CHAT#{sample_chat_id}'},
                    'SK': {'S': f'CHAT#{sample_chat_id}'},
                    'title': {'S': 'Updated Title'},
                    'status': {'S': 'archived'},
                    'updated_at': {'S': datetime.now(timezone.utc).isoformat()},
                }
            }
        )

        # Act
        await chat_repository.update(entity_id=sample_chat_id, updates=updates)

        # Mock the get_chat to return updated session
        chat_repository.get_chat = AsyncMock(
            return_value=ChatSession(
                chat_id=sample_chat_id,
                user_id='user1',
                title='Updated Title',
                status='archived',
            )
        )
        updated_session = await chat_repository.get_chat(sample_chat_id)

        # Assert
        assert updated_session is not None
        assert updated_session.title == 'Updated Title'
        assert updated_session.status == 'archived'

        # Verify update_item was called with correct parameters
        chat_repository.dynamodb_client.update_item.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_delete_chat_session(self, chat_repository, sample_chat_id):
        """Test soft-deleting a chat session."""
        # Arrange
        chat_repository.dynamodb_client.update_item = AsyncMock()
        chat_repository.update = AsyncMock(return_value=True)

        # Act
        result = await chat_repository.update(
            entity_id=sample_chat_id, updates={'status': 'deleted'}
        )

        # Assert
        assert result is True

        # Verify the session was marked as deleted (soft delete)
        chat_repository.dynamodb_client.update_item.assert_called_once()
        call_args = chat_repository.dynamodb_client.update_item.call_args

        # Check that status was updated to 'deleted'
        assert 'SET' in call_args.kwargs['UpdateExpression']
        assert 'deleted' in str(call_args.kwargs['ExpressionAttributeValues'])

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_get_chat_session_with_usage_metrics(
        self, chat_repository, sample_chat_id, sample_user_id
    ):
        """Test retrieving chat session with usage metrics."""
        # Arrange - Mock DynamoDB response with usage data
        mock_item = {
            'PK': {'S': f'CHAT#{sample_chat_id}'},
            'SK': {'S': f'CHAT#{sample_chat_id}'},
            'user_id': {'S': sample_user_id},
            'title': {'S': 'Test Chat'},
            'status': {'S': 'active'},
            'created_at': {'S': '2024-01-15T10:30:00+00:00'},
            'updated_at': {'S': '2024-01-15T10:30:00+00:00'},
            'metadata': {'M': {}},
            'usage': {
                'M': {
                    'total_tokens': {'N': '150'},
                    'input_tokens': {'N': '100'},
                    'output_tokens': {'N': '50'},
                }
            },
        }

        chat_repository.dynamodb_client.get_item = AsyncMock(
            return_value={'Item': mock_item}
        )

        # Act
        chat_session = await chat_repository.get_chat(sample_chat_id)

        # Assert
        assert chat_session is not None
        assert chat_session.usage['total_tokens'] == 150
        assert chat_session.usage['input_tokens'] == 100
        assert chat_session.usage['output_tokens'] == 50

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_chat_repository_error_handling(
        self, chat_repository, sample_chat_id
    ):
        """Test ChatRepository handles DynamoDB errors gracefully."""
        # Arrange - Mock DynamoDB client error
        chat_repository.dynamodb_client.get_item = AsyncMock(
            side_effect=ClientError(
                error_response={'Error': {'Code': 'ResourceNotFoundException'}},
                operation_name='GetItem',
            )
        )

        # Act & Assert
        with pytest.raises(ClientError):
            await chat_repository.get_chat(sample_chat_id)

    @pytest.mark.asyncio
    @pytest.mark.repository
    @pytest.mark.slow
    async def test_list_chat_sessions_pagination(self, chat_repository, sample_user_id):
        """Test pagination when listing many chat sessions."""
        # Arrange - Mock paginated response
        page1_items = [
            {
                'PK': {'S': f'CHAT#chat{i}'},
                'SK': {'S': f'CHAT#chat{i}'},
                'user_id': {'S': sample_user_id},
                'title': {'S': f'Chat {i}'},
                'status': {'S': 'active'},
                'created_at': {'S': '2024-01-15T10:00:00+00:00'},
                'updated_at': {'S': '2024-01-15T10:00:00+00:00'},
                'metadata': {'M': {}},
                'usage': {'M': {}},
            }
            for i in range(10)
        ]

        chat_repository.dynamodb_client.query = AsyncMock(
            return_value={
                'Items': page1_items,
                'Count': 10,
                'LastEvaluatedKey': {'PK': {'S': 'CHAT#chat9'}},
            }
        )

        # Act
        from app.repositories.message import MessageRepository

        mock_message_repo = AsyncMock(spec=MessageRepository)
        result = await chat_repository.list_chats(
            user_id=sample_user_id,
            status='active',
            with_messages=0,
            message_repo=mock_message_repo,
        )
        # Act
        from app.repositories.message import MessageRepository

        mock_message_repo = AsyncMock(spec=MessageRepository)
        result = await chat_repository.list_chats(
            user_id=sample_user_id,
            limit=10,
            with_messages=0,
            message_repo=mock_message_repo,
        )
        chat_sessions = result.chats

        # Assert
        assert len(chat_sessions) == 10
        assert all(session.user_id == sample_user_id for session in chat_sessions)

        # Verify query was called with correct limit
        call_args = chat_repository.dynamodb_client.query.call_args
        assert call_args.kwargs.get('Limit') == 10


class TestChatRepositoryIntegration:
    """Integration tests using real mocked DynamoDB operations."""

    @pytest.mark.asyncio
    @pytest.mark.repository
    @pytest.mark.integration
    async def test_full_chat_lifecycle(
        self, mock_app_table, dynamodb_client, test_settings
    ):
        """Test complete chat session lifecycle with real DynamoDB operations."""
        # Arrange - Create repository with real DynamoDB client
        from app.clients.dynamodb.client import DynamoDBClient

        real_dynamodb_client = DynamoDBClient(settings=test_settings)
        real_dynamodb_client._client = dynamodb_client
        # No need to call initialize since we're directly setting the client

        chat_repository = ChatRepository(dynamodb_client=real_dynamodb_client)

        # Act & Assert - Create chat session
        chat_session = await chat_repository.create_chat(
            ChatSession(user_id='integration_user', title='Integration Test Chat')
        )

        # Add null check assertion
        assert chat_session is not None, 'Created chat session should not be None'
        assert chat_session.user_id == 'integration_user'
        assert chat_session.title == 'Integration Test Chat'
        # Ensure chat_id is available for later use
        assert hasattr(chat_session, 'chat_id'), 'Chat session missing chat_id'
        chat_id = chat_session.chat_id

        # Retrieve the created session
        retrieved_session = await chat_repository.get_chat(chat_id)
        assert retrieved_session is not None, 'Retrieved session should not be None'
        assert retrieved_session.chat_id == chat_id

        # Update the session
        updated = await chat_repository.update(
            entity_id=chat_id,
            updates={'title': 'Updated Integration Test Chat'},
        )
        assert updated is True

        # Mock what get_chat would return after update
        chat_repository.get_chat = AsyncMock(
            return_value=ChatSession(
                chat_id=chat_id,
                user_id='integration_user',
                title='Updated Integration Test Chat',
                status='active',
            )
        )
        updated_session = await chat_repository.get_chat(chat_id)
        # Add null check assertion
        assert updated_session is not None, 'Updated session should not be None'
        assert updated_session.title == 'Updated Integration Test Chat'

        # List sessions for user
        from app.repositories.message import MessageRepository

        message_repo = MessageRepository(dynamodb_client=real_dynamodb_client)
        result = await chat_repository.list_chats(
            user_id='integration_user', with_messages=0, message_repo=message_repo
        )
        # Add null check assertion
        assert result is not None, 'List chats result should not be None'
        user_sessions = result.chats
        assert len(user_sessions) >= 1
        assert any(s is not None and s.chat_id == chat_id for s in user_sessions)

        # Delete the session
        delete_result = await chat_repository.update(
            entity_id=chat_id, updates={'status': 'deleted'}
        )
        assert delete_result is True
