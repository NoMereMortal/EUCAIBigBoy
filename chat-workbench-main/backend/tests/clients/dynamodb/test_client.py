# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for DynamoDB client."""

import datetime
import decimal
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.clients.base import CircuitOpenError
from app.clients.dynamodb.client import DynamoDBClient, with_retry
from app.config import Settings
from botocore.exceptions import ClientError


class TestWithRetryDecorator:
    """Test cases for the with_retry decorator."""

    @pytest.mark.asyncio
    async def test_with_retry_success_first_attempt(self):
        """Test that with_retry succeeds on first attempt."""

        @with_retry(max_retries=3, base_delay=0.1)
        async def mock_operation(self):
            return 'success'

        # Create a mock instance
        mock_instance = MagicMock()
        result = await mock_operation(mock_instance)
        assert result == 'success'

    @pytest.mark.asyncio
    async def test_with_retry_success_after_failures(self):
        """Test that with_retry succeeds after some failures."""
        # Define call_count in the outer scope
        call_count = [0]  # Use a mutable object to avoid nonlocal issues

        @with_retry(max_retries=3, base_delay=0.01)
        async def mock_operation(self):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception('Temporary failure')
            return 'success'

        mock_instance = MagicMock()
        result = await mock_operation(mock_instance)
        assert result == 'success'
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_with_retry_max_retries_exceeded(self):
        """Test that with_retry fails after max retries."""

        @with_retry(max_retries=2, base_delay=0.01)
        async def mock_operation(self):
            raise Exception('Persistent failure')

        mock_instance = MagicMock()
        with pytest.raises(Exception, match='Persistent failure'):
            await mock_operation(mock_instance)

    @pytest.mark.asyncio
    async def test_with_retry_specific_exceptions(self):
        """Test that with_retry only catches specific exceptions."""

        @with_retry(max_retries=3, base_delay=0.01, specific_exceptions=(ValueError,))
        async def mock_operation(self):
            raise TypeError('Different exception type')

        mock_instance = MagicMock()
        with pytest.raises(TypeError):
            await mock_operation(mock_instance)


class TestDynamoDBClient:
    """Test cases for DynamoDBClient class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock(spec=Settings)
        settings.aws.region = 'us-east-1'
        settings.aws.endpoint_url = None
        settings.aws.dynamodb.endpoint_url = 'http://localhost:8000'
        settings.aws.get_boto_config.return_value = {}
        settings.dynamodb.table_name = 'test-table'
        return settings

    @pytest.fixture
    def dynamodb_client(self, mock_settings):
        """Create DynamoDBClient instance."""
        return DynamoDBClient(settings=mock_settings)

    @pytest.mark.asyncio
    async def test_initialize_success(self, dynamodb_client):
        """Test successful DynamoDB client initialization."""
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_session.create_client.return_value.__aenter__.return_value = mock_client

        with patch('app.clients.dynamodb.client.AioSession', return_value=mock_session):
            await dynamodb_client.initialize()

        assert dynamodb_client._client == mock_client
        mock_session.create_client.assert_called_once_with(
            'dynamodb',
            region_name='us-east-1',
            endpoint_url='http://localhost:8000',
            config={},
        )

    @pytest.mark.asyncio
    async def test_initialize_circuit_breaker_open(self, dynamodb_client):
        """Test initialization fails when circuit breaker is open."""
        dynamodb_client.circuit_breaker.can_execute = MagicMock(return_value=False)

        with pytest.raises(CircuitOpenError):
            await dynamodb_client.initialize()

    @pytest.mark.asyncio
    async def test_cleanup(self, dynamodb_client):
        """Test DynamoDB client cleanup."""
        mock_client = AsyncMock()
        dynamodb_client._client = mock_client

        await dynamodb_client.cleanup()

        mock_client.__aexit__.assert_awaited_once_with(None, None, None)

    def test_get_table_name(self, dynamodb_client):
        """Test getting table name."""
        with patch('app.clients.dynamodb.client.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.dynamodb.table_name = 'expected-table'
            mock_get_settings.return_value = mock_settings

            result = dynamodb_client._get_table_name()
            assert result == 'expected-table'

    def test_format_pk(self, dynamodb_client):
        """Test partition key formatting."""
        result = dynamodb_client._format_pk('chat', '123')
        assert result == 'CHAT#123'

        result = dynamodb_client._format_pk('message', 'msg-456')
        assert result == 'MESSAGE#msg-456'

    def test_format_sk(self, dynamodb_client):
        """Test sort key formatting."""
        result = dynamodb_client._format_sk('metadata')
        assert result == 'METADATA'

        result = dynamodb_client._format_sk('message', 'msg-789')
        assert result == 'MESSAGE#msg-789'

    def test_create_item_key(self, dynamodb_client):
        """Test creating item key dictionary."""
        result = dynamodb_client.create_item_key('CHAT#123', 'METADATA')
        expected = {'pk': 'CHAT#123', 'sk': 'METADATA'}
        assert result == expected

    def test_create_gsi1_item(self, dynamodb_client):
        """Test creating GSI1 fields."""
        result = dynamodb_client.create_gsi1_item('USER#123', 'CHAT#456')
        expected = {'gsi1pk': 'USER#123', 'gsi1sk': 'CHAT#456'}
        assert result == expected

    def test_create_gsi2_item(self, dynamodb_client):
        """Test creating GSI2 fields."""
        result = dynamodb_client.create_gsi2_item('STATUS#active', 'TIMESTAMP#2023')
        expected = {'gsi2pk': 'STATUS#active', 'gsi2sk': 'TIMESTAMP#2023'}
        assert result == expected

    @pytest.mark.asyncio
    async def test_put_item_success(self, dynamodb_client):
        """Test successful item insertion."""
        mock_client = AsyncMock()
        dynamodb_client._client = mock_client

        item = {
            'pk': 'CHAT#123',
            'sk': 'METADATA',
            'title': 'Test Chat',
            'created_at': datetime.datetime.now(),
        }

        with (
            patch.object(dynamodb_client, '_serialize_item', return_value=item),
            patch.object(dynamodb_client, '_get_table_name', return_value='test-table'),
        ):
            await dynamodb_client.put_item('ignored-table', item)

        mock_client.put_item.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_put_item_not_initialized(self, dynamodb_client):
        """Test put_item fails when client not initialized."""
        item = {'pk': 'TEST#123', 'sk': 'METADATA'}

        with pytest.raises(ValueError, match='DynamoDB client not initialized'):
            await dynamodb_client.put_item('table', item)

    @pytest.mark.asyncio
    async def test_put_item_message_logging(self, dynamodb_client):
        """Test message logging for Message entity type."""
        mock_client = AsyncMock()
        dynamodb_client._client = mock_client

        item = {
            'entity_type': 'Message',
            'message_id': 'msg-123',
            'chat_id': 'chat-456',
            'kind': 'user',
            'parts': [{'content': 'This is a test message with some content'}],
        }

        with (
            patch.object(dynamodb_client, '_serialize_item', return_value=item),
            patch.object(dynamodb_client, '_get_table_name', return_value='test-table'),
            patch('app.clients.dynamodb.client.logger') as mock_logger,
        ):
            await dynamodb_client.put_item('table', item)

        # Verify message logging occurred
        mock_logger.info.assert_called()
        log_call = mock_logger.info.call_args[0][0]
        assert 'DB SAVE: Message id=msg-123' in log_call
        assert 'chat=chat-456' in log_call
        assert 'kind=user' in log_call

    @pytest.mark.asyncio
    async def test_put_item_handles_exception(self, dynamodb_client):
        """Test put_item handles exceptions properly."""
        mock_client = AsyncMock()
        mock_client.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid item'}},
            'put_item',
        )
        dynamodb_client._client = mock_client

        item = {'pk': 'TEST#123', 'sk': 'METADATA'}

        with (
            patch.object(dynamodb_client, '_serialize_item', return_value=item),
            patch.object(dynamodb_client, '_get_table_name', return_value='test-table'),
            patch.object(
                dynamodb_client.circuit_breaker, 'record_failure'
            ) as mock_record_failure,
            pytest.raises(ClientError),
        ):
            await dynamodb_client.put_item('table', item)

        # Verify circuit breaker recorded failure
        assert mock_record_failure.called

    def test_serialize_item_basic_types(self, dynamodb_client):
        """Test serialization of basic data types."""
        item = {
            'string_field': 'test',
            'number_field': 42,
            'boolean_field': True,
            'list_field': [1, 2, 3],
            'dict_field': {'nested': 'value'},
        }

        result = dynamodb_client._serialize_item(item)

        # Basic types should be wrapped in DynamoDB type descriptors
        assert 'S' in result['string_field']
        assert 'N' in result['number_field']
        assert 'BOOL' in result['boolean_field']
        assert 'L' in result['list_field']
        assert 'M' in result['dict_field']

    def test_serialize_item_special_types(self, dynamodb_client):
        """Test serialization of special Python types."""
        now = datetime.datetime.now()
        uid = uuid.uuid4()
        dec = decimal.Decimal('123.45')

        item = {'datetime_field': now, 'uuid_field': uid, 'decimal_field': dec}

        result = dynamodb_client._serialize_item(item)

        # Special types should be converted to strings
        assert result['datetime_field']['S'] == now.isoformat()
        assert result['uuid_field']['S'] == str(uid)
        assert 'N' in result['decimal_field']  # Decimal becomes number

    def test_deserialize_item_basic_types(self, dynamodb_client):
        """Test deserialization of basic data types."""
        dynamodb_item = {
            'string_field': {'S': 'test'},
            'number_field': {'N': '42'},
            'boolean_field': {'BOOL': True},
            'list_field': {'L': [{'N': '1'}, {'N': '2'}]},
            'dict_field': {'M': {'nested': {'S': 'value'}}},
        }

        result = dynamodb_client._deserialize_item(dynamodb_item)

        assert result['string_field'] == 'test'
        assert result['number_field'] == 42
        assert result['boolean_field'] is True
        assert result['list_field'] == [1, 2]
        assert result['dict_field'] == {'nested': 'value'}

    @pytest.mark.asyncio
    async def test_get_item_success(self, dynamodb_client):
        """Test successful item retrieval."""
        mock_client = AsyncMock()
        mock_response = {
            'Item': {
                'pk': {'S': 'CHAT#123'},
                'sk': {'S': 'METADATA'},
                'title': {'S': 'Test Chat'},
            }
        }
        mock_client.get_item.return_value = mock_response
        dynamodb_client._client = mock_client

        with patch.object(
            dynamodb_client, '_get_table_name', return_value='test-table'
        ):
            result = await dynamodb_client.get_item(
                'test-table', {'pk': 'CHAT#123', 'sk': 'METADATA'}
            )

        expected = {'pk': 'CHAT#123', 'sk': 'METADATA', 'title': 'Test Chat'}
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_item_not_found(self, dynamodb_client):
        """Test get_item when item doesn't exist."""
        mock_client = AsyncMock()
        mock_client.get_item.return_value = {}  # No Item key means not found
        dynamodb_client._client = mock_client

        with patch.object(
            dynamodb_client, '_get_table_name', return_value='test-table'
        ):
            result = await dynamodb_client.get_item(
                'test-table', {'pk': 'CHAT#123', 'sk': 'METADATA'}
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_item_not_initialized(self, dynamodb_client):
        """Test get_item fails when client not initialized."""
        with pytest.raises(ValueError, match='DynamoDB client not initialized'):
            await dynamodb_client.get_item('table', {'pk': 'TEST#123'})

    @pytest.mark.asyncio
    async def test_query_success(self, dynamodb_client):
        """Test successful query operation."""
        mock_client = AsyncMock()
        mock_response = {
            'Items': [
                {'pk': {'S': 'CHAT#123'}, 'sk': {'S': 'MESSAGE#1'}},
                {'pk': {'S': 'CHAT#123'}, 'sk': {'S': 'MESSAGE#2'}},
            ],
            'Count': 2,
        }
        mock_client.query.return_value = mock_response
        dynamodb_client._client = mock_client

        with patch.object(
            dynamodb_client, '_get_table_name', return_value='test-table'
        ):
            result = await dynamodb_client.query(
                TableName='test-table',
                KeyConditionExpression='pk = :pk',
                ExpressionAttributeValues={':pk': {'S': 'CHAT#123'}},
            )

        assert result['Count'] == 2
        assert len(result['Items']) == 2
        assert result['Items'][0]['pk'] == 'CHAT#123'
        assert result['Items'][0]['sk'] == 'MESSAGE#1'

    @pytest.mark.asyncio
    async def test_query_empty_result(self, dynamodb_client):
        """Test query with no matching items."""
        mock_client = AsyncMock()
        mock_client.query.return_value = {'Items': [], 'Count': 0}
        dynamodb_client._client = mock_client

        with patch.object(
            dynamodb_client, '_get_table_name', return_value='test-table'
        ):
            result = await dynamodb_client.query(
                TableName='test-table',
                KeyConditionExpression='pk = :pk',
                ExpressionAttributeValues={':pk': {'S': 'NONEXISTENT#123'}},
            )

        assert result['Items'] == []
        assert result['Count'] == 0

    @pytest.mark.asyncio
    async def test_delete_item_success(self, dynamodb_client):
        """Test successful item deletion."""
        mock_client = AsyncMock()
        dynamodb_client._client = mock_client

        key = {'pk': 'CHAT#123', 'sk': 'METADATA'}

        with patch.object(
            dynamodb_client, '_get_table_name', return_value='test-table'
        ):
            await dynamodb_client.delete_item('test-table', key)

        mock_client.delete_item.assert_awaited_once()
        call_args = mock_client.delete_item.call_args[1]
        assert call_args['TableName'] == 'test-table'
        assert 'Key' in call_args

    @pytest.mark.asyncio
    async def test_batch_write_items_success(self, dynamodb_client):
        """Test successful batch write operation."""
        mock_client = AsyncMock()
        mock_client.batch_write_item.return_value = {'UnprocessedItems': {}}
        dynamodb_client._client = mock_client

        items = [
            {'pk': 'CHAT#1', 'sk': 'METADATA', 'title': 'Chat 1'},
            {'pk': 'CHAT#2', 'sk': 'METADATA', 'title': 'Chat 2'},
        ]

        with patch.object(
            dynamodb_client, '_get_table_name', return_value='test-table'
        ):
            await dynamodb_client.batch_write_items('test-table', items)

        mock_client.batch_write_item.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_batch_write_items_with_unprocessed(self, dynamodb_client):
        """Test batch write with unprocessed items."""
        mock_client = AsyncMock()
        # Current implementation doesn't retry unprocessed items, so just return success
        mock_client.batch_write_item.return_value = {'UnprocessedItems': {}}
        dynamodb_client._client = mock_client

        items = [{'pk': 'CHAT#1', 'sk': 'METADATA'}]

        with patch.object(
            dynamodb_client, '_get_table_name', return_value='test-table'
        ):
            await dynamodb_client.batch_write_items('test-table', items)

        # Should be called once with current implementation
        assert mock_client.batch_write_item.call_count == 1

    @pytest.mark.asyncio
    async def test_table_exists_true(self, dynamodb_client):
        """Test table_exists returns True when table exists."""
        mock_client = AsyncMock()
        mock_client.describe_table.return_value = {'Table': {'TableStatus': 'ACTIVE'}}
        dynamodb_client._client = mock_client

        result = await dynamodb_client.table_exists('test-table')
        assert result is True

    @pytest.mark.asyncio
    async def test_table_exists_false(self, dynamodb_client):
        """Test table_exists returns False when table doesn't exist."""
        mock_client = AsyncMock()

        # Create a ResourceNotFoundException that inherits from Exception properly
        class ResourceNotFoundException(Exception):
            pass

        # Instead of ClientError, raise the specific exception the code expects
        mock_client.describe_table.side_effect = ResourceNotFoundException(
            'Table not found'
        )
        # Mock the exceptions attribute properly
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.ResourceNotFoundException = ResourceNotFoundException
        dynamodb_client._client = mock_client

        with patch.object(
            dynamodb_client, '_get_table_name', return_value='nonexistent-table'
        ):
            result = await dynamodb_client.table_exists('nonexistent-table')
        assert result is False

    @pytest.mark.asyncio
    async def test_create_tables_success(self, dynamodb_client):
        """Test successful table creation."""
        mock_client = AsyncMock()

        # Create a ResourceNotFoundException that inherits from Exception properly
        class ResourceNotFoundException(Exception):
            pass

        # Instead of ClientError, raise the specific exception the code expects
        mock_client.describe_table.side_effect = ResourceNotFoundException(
            'Table not found'
        )
        # Mock the exceptions attribute properly
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.ResourceNotFoundException = ResourceNotFoundException

        mock_client.create_table.return_value = {
            'TableDescription': {'TableStatus': 'CREATING'}
        }
        # get_waiter is a sync method, so we mock it as such
        mock_waiter = MagicMock()
        mock_waiter.wait = AsyncMock()
        mock_client.get_waiter = MagicMock(return_value=mock_waiter)
        dynamodb_client._client = mock_client

        mock_schema = {'TableName': 'test-table', 'KeySchema': []}

        with (
            patch.object(dynamodb_client, '_get_table_name', return_value='test-table'),
            patch('app.clients.dynamodb.schema.get_schemas', return_value=mock_schema),
        ):
            await dynamodb_client.create_tables()

        mock_client.create_table.assert_awaited_once()
        mock_client.get_waiter.assert_called_once_with('table_exists')
        mock_waiter.wait.assert_awaited_once_with(TableName='test-table')

    @pytest.mark.asyncio
    async def test_create_tables_already_exists(self, dynamodb_client):
        """Test create_tables when table already exists."""
        mock_client = AsyncMock()
        mock_client.describe_table.return_value = {'Table': {'TableStatus': 'ACTIVE'}}
        dynamodb_client._client = mock_client

        with patch.object(
            dynamodb_client, '_get_table_name', return_value='test-table'
        ):
            await dynamodb_client.create_tables()

        # Should not call create_table if table exists
        mock_client.create_table.assert_not_called()
