# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for MessageRepository - critical message serialization and DynamoDB operations."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from app.clients.dynamodb.client import DynamoDBClient
from app.models import (
    CitationPart,
    ImagePart,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from app.repositories.message import MessageRepository
from botocore.exceptions import ClientError


class TestMessageRepository:
    """Tests for MessageRepository - critical serialization/deserialization logic."""

    @pytest.fixture
    async def message_repository(self, test_settings, mock_app_table, dynamodb_client):
        """Create MessageRepository with mocked DynamoDB."""
        mock_dynamodb_client = AsyncMock(spec=DynamoDBClient)
        mock_dynamodb_client.table_name = mock_app_table
        mock_dynamodb_client.client = dynamodb_client

        return MessageRepository(dynamodb_client=mock_dynamodb_client)

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_message_serialization_deserialization_round_trip(
        self, message_repository
    ):
        """Test critical round-trip serialization/deserialization of complex messages."""
        # Create a complex message with multiple part types
        complex_message = ModelRequest(
            message_id='msg_complex_123',
            chat_id='chat_456',
            parts=[
                TextPart(content="Here's a complex message with multiple parts."),
                ToolCallPart(
                    tool_name='calculator',
                    tool_args={'expression': '2 + 2'},
                    tool_id='calc_tool_123',
                ),
                ToolReturnPart(
                    tool_name='calculator',
                    tool_id='calc_tool_123',
                    result={'answer': 4, 'confidence': 0.95},
                ),
                CitationPart(
                    document_id='doc_789',
                    text='According to the research paper, the calculation is correct.',
                    page=15,
                    section='Results',
                    citation_id='cite_abc',
                ),
                ImagePart(
                    file_id='img_456',
                    user_id='user_789',
                    mime_type='image/png',
                    width=800,
                    height=600,
                    content='[Image: img_456]',
                ),
            ],
            timestamp=datetime.now(timezone.utc),
            metadata={'test': True, 'complexity': 'high'},
        )

        # Mock the DynamoDB put_item operation
        message_repository.dynamodb_client.put_item = AsyncMock()

        # Act - Save the message
        await message_repository.create_message(complex_message)

        # Verify put_item was called
        message_repository.dynamodb_client.put_item.assert_called_once()
        call_args = message_repository.dynamodb_client.put_item.call_args

        # Inspect the serialized item
        item = call_args.kwargs.get('Item') or call_args.args[0]['Item']

        # Verify key structure
        assert item['PK']['S'] == 'CHAT#chat_456'
        assert item['SK']['S'] == 'MSG#msg_complex_123'
        assert item['message_id']['S'] == 'msg_complex_123'
        assert item['kind']['S'] == 'request'

        # Verify parts serialization - this is the critical test
        parts_json = item['parts']['S']
        parts_data = json.loads(parts_json)
        assert len(parts_data) == 5

        # Check each part type was serialized correctly
        assert parts_data[0]['part_kind'] == 'text'
        assert parts_data[1]['part_kind'] == 'tool-call'
        assert parts_data[2]['part_kind'] == 'tool-return'
        assert parts_data[3]['part_kind'] == 'citation'
        assert parts_data[4]['part_kind'] == 'image'

        # Mock the get_item operation for deserialization test
        message_repository.dynamodb_client.get_item = AsyncMock(
            return_value={'Item': item}
        )

        # Act - Retrieve the message
        retrieved_message = await message_repository.get_message(
            chat_id='chat_456', message_id='msg_complex_123'
        )

        # Assert - Round-trip verification
        assert retrieved_message is not None
        assert isinstance(retrieved_message, ModelRequest)
        assert retrieved_message.message_id == complex_message.message_id
        assert retrieved_message.chat_id == complex_message.chat_id
        assert len(retrieved_message.parts) == 5

        # Verify each part type was deserialized correctly
        assert isinstance(retrieved_message.parts[0], TextPart)
        assert isinstance(retrieved_message.parts[1], ToolCallPart)
        assert isinstance(retrieved_message.parts[2], ToolReturnPart)
        assert isinstance(retrieved_message.parts[3], CitationPart)
        assert isinstance(retrieved_message.parts[4], ImagePart)

        # Verify content integrity
        assert (
            retrieved_message.parts[0].content
            == "Here's a complex message with multiple parts."
        )
        assert retrieved_message.parts[1].tool_name == 'calculator'
        assert retrieved_message.parts[1].tool_args == {'expression': '2 + 2'}
        assert retrieved_message.parts[2].result == {'answer': 4, 'confidence': 0.95}
        assert retrieved_message.parts[3].document_id == 'doc_789'
        assert retrieved_message.parts[3].page == 15
        assert retrieved_message.parts[4].file_id == 'img_456'

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_message_repository_chat_messages_query(self, message_repository):
        """Test retrieving all messages for a chat with proper ordering."""
        chat_id = 'chat_messages_test'

        # Mock DynamoDB query response with multiple messages
        mock_items = [
            {
                'PK': {'S': f'CHAT#{chat_id}'},
                'SK': {'S': 'MSG#msg_001'},
                'message_id': {'S': 'msg_001'},
                'chat_id': {'S': chat_id},
                'kind': {'S': 'request'},
                'parts': {
                    'S': json.dumps(
                        [
                            {
                                'part_kind': 'text',
                                'content': 'First message',
                                'metadata': {},
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                            }
                        ]
                    )
                },
                'timestamp': {'S': '2024-01-15T10:00:00+00:00'},
                'metadata': {'M': {}},
                'status': {'S': 'complete'},
            },
            {
                'PK': {'S': f'CHAT#{chat_id}'},
                'SK': {'S': 'MSG#msg_002'},
                'message_id': {'S': 'msg_002'},
                'chat_id': {'S': chat_id},
                'kind': {'S': 'response'},
                'parts': {
                    'S': json.dumps(
                        [
                            {
                                'part_kind': 'text',
                                'content': 'Response message',
                                'metadata': {},
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                            }
                        ]
                    )
                },
                'timestamp': {'S': '2024-01-15T10:01:00+00:00'},
                'metadata': {'M': {}},
                'status': {'S': 'complete'},
                'model_name': {'S': 'claude-3-sonnet'},
                'usage': {
                    'M': {'input_tokens': {'N': '10'}, 'output_tokens': {'N': '20'}}
                },
            },
        ]

        message_repository.dynamodb_client.query = AsyncMock(
            return_value={'Items': mock_items}
        )

        # Act
        messages = await message_repository.get_chat_messages(chat_id)

        # Assert
        assert len(messages) == 2

        # Check message types
        assert isinstance(messages[0], ModelRequest)
        assert isinstance(messages[1], ModelResponse)

        # Check ordering (should be chronological)
        assert messages[0].message_id == 'msg_001'
        assert messages[1].message_id == 'msg_002'

        # Check model response specific fields
        assert messages[1].model_name == 'claude-3-sonnet'
        assert messages[1].usage['input_tokens'] == 10
        assert messages[1].usage['output_tokens'] == 20

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_message_repository_update_message_status(self, message_repository):
        """Test updating message status and metadata."""
        chat_id = 'chat_update_test'
        message_id = 'msg_update_123'

        # Mock update_item response
        message_repository.dynamodb_client.update_item = AsyncMock(
            return_value={
                'Attributes': {
                    'PK': {'S': f'CHAT#{chat_id}'},
                    'SK': {'S': f'MSG#{message_id}'},
                    'status': {'S': 'completed'},
                    'updated_at': {'S': datetime.now(timezone.utc).isoformat()},
                }
            }
        )

        # Act
        success = await message_repository.update_message_status(
            chat_id=chat_id, message_id=message_id, status='completed'
        )

        # Assert
        assert success is True

        # Verify update_item was called with correct parameters
        message_repository.dynamodb_client.update_item.assert_called_once()
        call_args = message_repository.dynamodb_client.update_item.call_args

        assert call_args.kwargs['Key'] == {
            'PK': f'CHAT#{chat_id}',
            'SK': f'MSG#{message_id}',
        }
        assert 'SET' in call_args.kwargs['UpdateExpression']

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_message_repository_deserialization_edge_cases(
        self, message_repository
    ):
        """Test message deserialization handles edge cases and malformed data."""
        # Test with empty parts array
        empty_parts_item = {
            'PK': {'S': 'CHAT#test'},
            'SK': {'S': 'MSG#empty'},
            'message_id': {'S': 'empty'},
            'chat_id': {'S': 'test'},
            'kind': {'S': 'request'},
            'parts': {'S': '[]'},  # Empty array
            'timestamp': {'S': '2024-01-15T10:00:00+00:00'},
            'metadata': {'M': {}},
            'status': {'S': 'complete'},
        }

        message_repository.dynamodb_client.get_item = AsyncMock(
            return_value={'Item': empty_parts_item}
        )

        # Should handle empty parts gracefully
        message = await message_repository.get_message('test', 'empty')
        assert message is not None
        assert len(message.parts) == 0

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_message_repository_error_handling(self, message_repository):
        """Test MessageRepository handles DynamoDB errors appropriately."""
        # Test get_message with non-existent message
        message_repository.dynamodb_client.get_item = AsyncMock(
            return_value={}  # Empty response
        )

        result = await message_repository.get_message('nonexistent', 'msg')
        assert result is None

        # Test create_message with DynamoDB error
        message_repository.dynamodb_client.put_item = AsyncMock(
            side_effect=ClientError(
                error_response={'Error': {'Code': 'ValidationException'}},
                operation_name='PutItem',
            )
        )

        test_message = ModelRequest(
            message_id='test_msg', chat_id='test_chat', parts=[TextPart(content='Test')]
        )

        with pytest.raises(ClientError):
            await message_repository.create_message(test_message)

    @pytest.mark.asyncio
    @pytest.mark.repository
    @pytest.mark.slow
    async def test_message_repository_large_message_handling(self, message_repository):
        """Test MessageRepository handles large messages efficiently."""
        # Create a message with many parts (stress test)
        large_parts = []
        for i in range(100):
            large_parts.append(TextPart(content=f'Part {i} ' * 100))  # ~600 chars each

        large_message = ModelRequest(
            message_id='large_msg_123', chat_id='large_chat', parts=large_parts
        )

        message_repository.dynamodb_client.put_item = AsyncMock()

        # Should handle large serialization
        await message_repository.create_message(large_message)

        # Verify put_item was called
        message_repository.dynamodb_client.put_item.assert_called_once()

        # Check that serialized parts data is reasonable size
        call_args = message_repository.dynamodb_client.put_item.call_args
        item = call_args.kwargs.get('Item') or call_args.args[0]['Item']
        parts_json = item['parts']['S']

        # Should be large but manageable (DynamoDB has 400KB item limit)
        assert len(parts_json) > 10000  # Should be substantial
        assert len(parts_json) < 300000  # But not too large for DynamoDB

    @pytest.mark.asyncio
    @pytest.mark.repository
    async def test_message_repository_concurrent_operations(self, message_repository):
        """Test MessageRepository handles concurrent operations safely."""
        import asyncio

        # Create multiple messages concurrently
        async def create_test_message(msg_id: str):
            message = ModelRequest(
                message_id=msg_id,
                chat_id='concurrent_test',
                parts=[TextPart(content=f'Concurrent message {msg_id}')],
            )
            message_repository.dynamodb_client.put_item = AsyncMock()
            await message_repository.create_message(message)

        # Run concurrent operations
        tasks = [create_test_message(f'msg_{i}') for i in range(10)]
        await asyncio.gather(*tasks)

        # All operations should complete without errors
        # Each put_item should have been called once per message
        assert message_repository.dynamodb_client.put_item.call_count == 10


class TestMessageRepositoryIntegration:
    """Integration tests with real mocked DynamoDB operations."""

    @pytest.mark.asyncio
    @pytest.mark.repository
    @pytest.mark.integration
    async def test_message_lifecycle_with_real_dynamodb(
        self, mock_app_table, dynamodb_client, test_settings
    ):
        """Test complete message lifecycle with real DynamoDB operations."""
        from app.clients.dynamodb.client import DynamoDBClient

        # Create repository with real DynamoDB client
        real_dynamodb_client = DynamoDBClient(settings=test_settings)
        # Set the client directly after initialization
        real_dynamodb_client._client = dynamodb_client
        await real_dynamodb_client.initialize()

        message_repository = MessageRepository(dynamodb_client=real_dynamodb_client)

        # Create a complex message
        test_message = ModelRequest(
            message_id='integration_msg_123',
            chat_id='integration_chat_456',
            parts=[
                TextPart(content='Integration test message'),
                ToolCallPart(
                    tool_name='test_tool',
                    tool_args={'param': 'value'},
                    tool_id='tool_integration_123',
                ),
            ],
            metadata={'integration_test': True},
        )

        # Create message
        await message_repository.create_message(test_message)

        # Retrieve message
        retrieved = await message_repository.get_message(
            'integration_chat_456', 'integration_msg_123'
        )

        # Verify round-trip integrity
        assert retrieved is not None
        assert retrieved.message_id == test_message.message_id
        assert len(retrieved.parts) == 2
        assert isinstance(retrieved.parts[0], TextPart)
        assert isinstance(retrieved.parts[1], ToolCallPart)
        assert retrieved.parts[1].tool_name == 'test_tool'

        # Update message status
        success = await message_repository.update_message_status(
            'integration_chat_456', 'integration_msg_123', 'completed'
        )
        assert success is True

        # Retrieve all messages for chat
        all_messages = await message_repository.get_chat_messages(
            'integration_chat_456'
        )
        assert len(all_messages) == 1
        assert all_messages[0].message_id == 'integration_msg_123'
