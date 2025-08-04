# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for app/repositories/base.py - Base repository for single-table DynamoDB design."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.clients.dynamodb.client import DynamoDBClient
from app.config import Settings
from app.repositories.base import BaseRepository


@dataclass
class TestModel:
    """Test model for repository testing."""

    test_id: str
    name: str
    description: str
    is_active: bool = True


class TestBaseRepository:
    """Tests for BaseRepository class in app/repositories/base.py."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Mock DynamoDB client."""
        mock_client = AsyncMock(spec=DynamoDBClient)
        mock_client.put_item = AsyncMock()
        mock_client.get_item = AsyncMock()
        mock_client.update_item = AsyncMock()
        mock_client.delete_item = AsyncMock()
        mock_client.query = AsyncMock()
        return mock_client

    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        mock_settings = MagicMock(spec=Settings)
        mock_dynamodb = MagicMock()
        mock_dynamodb.table_name = 'test-table'
        mock_settings.dynamodb = mock_dynamodb
        return mock_settings

    @pytest.fixture
    def base_repository(self, mock_dynamodb_client, mock_settings):
        """Create BaseRepository instance with test configuration."""
        with patch('app.repositories.base.get_settings', return_value=mock_settings):
            return BaseRepository(
                dynamodb_client=mock_dynamodb_client,
                entity_type='TEST',
                model_class=TestModel,
            )

    @pytest.fixture
    def sample_model(self):
        """Sample test model."""
        return TestModel(
            test_id='test-123',
            name='Test Item',
            description='A test item for repository testing',
            is_active=True,
        )

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_repository_initialization(self, mock_dynamodb_client, mock_settings):
        """Test BaseRepository initialization."""
        with patch('app.repositories.base.get_settings', return_value=mock_settings):
            repo = BaseRepository(
                dynamodb_client=mock_dynamodb_client,
                entity_type='TEST',
                model_class=TestModel,
            )

            assert repo.dynamodb == mock_dynamodb_client
            assert repo.entity_type == 'TEST'
            assert repo.model_class == TestModel
            assert repo.table_name == 'test-table'

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_format_pk(self, base_repository):
        """Test partition key formatting."""
        result = base_repository._format_pk('test-123')
        assert result == 'TEST#test-123'

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_format_sk_with_id(self, base_repository):
        """Test sort key formatting with ID."""
        result = base_repository._format_sk('METADATA', 'version-1')
        assert result == 'METADATA#version-1'

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_format_sk_without_id(self, base_repository):
        """Test sort key formatting without ID."""
        result = base_repository._format_sk('METADATA')
        assert result == 'METADATA'

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_format_gsi_keys_basic(self, base_repository):
        """Test basic GSI key formatting."""
        item = {'test_field': 'value'}
        entity_id = 'test-123'

        with patch('app.repositories.base.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = (
                '2025-01-01T12:00:00'
            )

            result = base_repository._format_gsi_keys(item, entity_id)

            assert result['entity_type'] == 'TEST'
            assert result['created_at'] == '2025-01-01T12:00:00'
            assert result['updated_at'] == '2025-01-01T12:00:00'
            assert result['GlobalPK'] == 'RESOURCE_TYPE#TEST'
            assert result['GlobalSK'] == 'CREATED_AT#2025-01-01T12:00:00#test-123'

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_format_gsi_keys_with_user_id(self, base_repository):
        """Test GSI key formatting with user ID."""
        item = {'test_field': 'value'}
        entity_id = 'test-123'
        user_id = 'user-456'

        with patch('app.repositories.base.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = (
                '2025-01-01T12:00:00'
            )

            result = base_repository._format_gsi_keys(item, entity_id, user_id=user_id)

            assert result['UserPK'] == 'USER#user-456'
            assert result['UserSK'] == 'TEST#2025-01-01T12:00:00#test-123'

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_format_gsi_keys_with_custom_timestamp(self, base_repository):
        """Test GSI key formatting with custom timestamp."""
        item = {'created_at': '2024-12-01T10:00:00'}
        entity_id = 'test-123'
        custom_timestamp = '2025-01-15T15:30:00'

        result = base_repository._format_gsi_keys(
            item, entity_id, timestamp=custom_timestamp
        )

        # Should preserve existing created_at but update updated_at
        assert result['created_at'] == '2024-12-01T10:00:00'
        assert result['updated_at'] == '2025-01-15T15:30:00'
        assert result['GlobalSK'] == 'CREATED_AT#2025-01-15T15:30:00#test-123'

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_get_key(self, base_repository):
        """Test primary key generation."""
        result = base_repository._get_key('test-123')
        expected = {'PK': 'TEST#test-123', 'SK': 'METADATA'}
        assert result == expected

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_get_key_custom_sort_key(self, base_repository):
        """Test primary key generation with custom sort key."""
        result = base_repository._get_key('test-123', 'CONFIG')
        expected = {'PK': 'TEST#test-123', 'SK': 'CONFIG'}
        assert result == expected

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_create_dataclass_model_success(
        self, base_repository, sample_model, mock_dynamodb_client
    ):
        """Test successful creation of dataclass model."""
        mock_dynamodb_client.put_item.return_value = None

        with patch('app.repositories.base.make_json_serializable') as mock_serialize:
            mock_serialize.return_value = {'serialized': 'item'}

            result = await base_repository.create(sample_model)

            assert result == sample_model
            mock_dynamodb_client.put_item.assert_called_once()

            # Verify the item was properly formatted for DynamoDB
            call_args = mock_dynamodb_client.put_item.call_args
            assert call_args[0][0] == 'test-table'  # table_name
            mock_serialize.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_create_with_pydantic_model(
        self, base_repository, mock_dynamodb_client
    ):
        """Test creation with Pydantic model."""
        # Mock a Pydantic-like model
        mock_model = MagicMock()
        mock_model.model_dump.return_value = {
            'test_id': 'test-456',
            'name': 'Pydantic Test',
            'description': 'Test with Pydantic',
            'is_active': True,
        }

        mock_dynamodb_client.put_item.return_value = None

        with patch('app.repositories.base.make_json_serializable') as mock_serialize:
            mock_serialize.return_value = {'serialized': 'item'}

            result = await base_repository.create(mock_model)

            assert result == mock_model
            mock_model.model_dump.assert_called_once()
            mock_dynamodb_client.put_item.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_create_missing_entity_id_field(
        self, base_repository, mock_dynamodb_client
    ):
        """Test creation with missing entity ID field."""
        # Create model without the required field by direct dict manipulation

        # Create a valid model first
        TestModel(test_id='test-123', name='Test', description='Test')

        # Create a mock model that will fail asdict conversion
        invalid_model = MagicMock()
        invalid_model.__dict__ = {
            'name': 'Test',
            'description': 'Test',
        }  # Missing test_id

        # Make it look like a dataclass

        # Patch is_dataclass to return True for our mock
        with (
            patch('dataclasses.is_dataclass', return_value=True)
            and patch('dataclasses.asdict', side_effect=lambda x: x.__dict__)
            and pytest.raises(ValueError, match='Missing test_id in model')
        ):
            await base_repository.create(invalid_model)

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_create_with_user_id_gsi(
        self, base_repository, sample_model, mock_dynamodb_client
    ):
        """Test creation with user ID for GSI."""
        mock_dynamodb_client.put_item.return_value = None

        with patch('app.repositories.base.make_json_serializable') as mock_serialize:
            mock_serialize.return_value = {'serialized': 'item'}

            result = await base_repository.create(sample_model, user_id='user-789')

            assert result == sample_model

            # Verify GSI keys were added correctly
            serialize_call_args = mock_serialize.call_args[0][0]
            assert serialize_call_args['UserPK'] == 'USER#user-789'
            assert 'UserSK' in serialize_call_args

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_get_existing_item(self, base_repository, mock_dynamodb_client):
        """Test getting an existing item."""
        mock_item = {
            'test_id': 'test-123',
            'name': 'Retrieved Item',
            'description': 'Retrieved from DynamoDB',
            'is_active': True,
        }
        mock_dynamodb_client.get_item.return_value = mock_item

        result = await base_repository.get('test-123')

        assert result is not None
        assert result.test_id == 'test-123'
        assert result.name == 'Retrieved Item'

        mock_dynamodb_client.get_item.assert_called_once_with(
            'test-table', {'PK': 'TEST#test-123', 'SK': 'METADATA'}
        )

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_get_nonexistent_item(self, base_repository, mock_dynamodb_client):
        """Test getting a nonexistent item."""
        mock_dynamodb_client.get_item.return_value = None

        result = await base_repository.get('nonexistent')

        assert result is None
        mock_dynamodb_client.get_item.assert_called_once_with(
            'test-table', {'PK': 'TEST#nonexistent', 'SK': 'METADATA'}
        )

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_get_with_custom_sort_key(
        self, base_repository, mock_dynamodb_client
    ):
        """Test getting an item with custom sort key."""
        mock_item = {
            'test_id': 'test-123',
            'name': 'Config Item',
            'description': 'Configuration data',
            'is_active': True,
        }
        mock_dynamodb_client.get_item.return_value = mock_item

        result = await base_repository.get('test-123', 'CONFIG')

        assert result is not None
        mock_dynamodb_client.get_item.assert_called_once_with(
            'test-table', {'PK': 'TEST#test-123', 'SK': 'CONFIG'}
        )

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_update_success(self, base_repository, mock_dynamodb_client):
        """Test successful item update."""
        mock_dynamodb_client.update_item.return_value = None
        updates = {
            'name': 'Updated Name',
            'description': 'Updated Description',
            'is_active': False,
        }

        with patch('app.repositories.base.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = (
                '2025-01-01T15:30:00'
            )

            result = await base_repository.update('test-123', updates)

            assert result is True
            mock_dynamodb_client.update_item.assert_called_once()

            call_kwargs = mock_dynamodb_client.update_item.call_args.kwargs
            assert call_kwargs['table_name'] == 'test-table'
            assert call_kwargs['key'] == {'PK': 'TEST#test-123', 'SK': 'METADATA'}

            # Verify update expression includes all fields plus updated_at
            update_expr = call_kwargs['update_expression']
            assert 'SET' in update_expr
            assert '#name = :name' in update_expr
            assert '#description = :description' in update_expr
            assert '#is_active = :is_active' in update_expr
            assert '#updated_at = :updated_at' in update_expr

            # Verify expression attribute values
            expr_values = call_kwargs['expression_attribute_values']
            assert expr_values[':name'] == 'Updated Name'
            assert expr_values[':description'] == 'Updated Description'
            assert expr_values[':is_active'] is False
            assert expr_values[':updated_at'] == '2025-01-01T15:30:00'

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_update_with_exception(self, base_repository, mock_dynamodb_client):
        """Test update with exception handling."""
        mock_dynamodb_client.update_item.side_effect = Exception('DynamoDB error')
        updates = {'name': 'Updated Name'}

        result = await base_repository.update('test-123', updates)

        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_delete_success(self, base_repository, mock_dynamodb_client):
        """Test successful item deletion."""
        mock_dynamodb_client.delete_item.return_value = None

        result = await base_repository.delete('test-123')

        assert result is True
        mock_dynamodb_client.delete_item.assert_called_once_with(
            'test-table', {'PK': 'TEST#test-123', 'SK': 'METADATA'}
        )

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_delete_with_exception(self, base_repository, mock_dynamodb_client):
        """Test deletion with exception handling."""
        mock_dynamodb_client.delete_item.side_effect = Exception('DynamoDB error')

        result = await base_repository.delete('test-123')

        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_delete_with_custom_sort_key(
        self, base_repository, mock_dynamodb_client
    ):
        """Test deletion with custom sort key."""
        mock_dynamodb_client.delete_item.return_value = None

        result = await base_repository.delete('test-123', 'CONFIG')

        assert result is True
        mock_dynamodb_client.delete_item.assert_called_once_with(
            'test-table', {'PK': 'TEST#test-123', 'SK': 'CONFIG'}
        )

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_list_by_user_success(self, base_repository, mock_dynamodb_client):
        """Test listing items by user."""
        mock_items = [
            {
                'test_id': 'test-1',
                'name': 'User Item 1',
                'description': 'First item',
                'is_active': True,
            },
            {
                'test_id': 'test-2',
                'name': 'User Item 2',
                'description': 'Second item',
                'is_active': True,
            },
        ]
        mock_last_key = {'PK': 'USER#user-123', 'SK': 'TEST#2025-01-01T12:00:00#test-2'}

        mock_dynamodb_client.query.return_value = {
            'Items': mock_items,
            'LastEvaluatedKey': mock_last_key,
        }

        items, last_key = await base_repository.list_by_user('user-123', limit=10)

        assert len(items) == 2
        assert items[0].test_id == 'test-1'
        assert items[1].test_id == 'test-2'
        assert last_key == mock_last_key

        # Verify query parameters
        mock_dynamodb_client.query.assert_called_once()
        call_kwargs = mock_dynamodb_client.query.call_args.kwargs
        assert call_kwargs['TableName'] == 'test-table'
        assert call_kwargs['IndexName'] == 'UserDataIndex'
        assert (
            call_kwargs['KeyConditionExpression']
            == 'UserPK = :upk AND begins_with(UserSK, :prefix)'
        )
        assert call_kwargs['ExpressionAttributeValues'][':upk'] == 'USER#user-123'
        assert call_kwargs['ExpressionAttributeValues'][':prefix'] == 'TEST#'
        assert call_kwargs['ScanIndexForward'] is False
        assert call_kwargs['Limit'] == 10

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_list_by_user_with_pagination(
        self, base_repository, mock_dynamodb_client
    ):
        """Test listing items by user with pagination."""
        mock_items = [
            {
                'test_id': 'test-1',
                'name': 'Item',
                'description': 'Desc',
                'is_active': True,
            }
        ]
        start_key = {'PK': 'USER#user-123', 'SK': 'TEST#2025-01-01T10:00:00#test-0'}

        mock_dynamodb_client.query.return_value = {
            'Items': mock_items,
            'LastEvaluatedKey': None,
        }

        items, last_key = await base_repository.list_by_user(
            'user-123', limit=5, last_key=start_key
        )

        assert len(items) == 1
        assert last_key is None

        call_kwargs = mock_dynamodb_client.query.call_args.kwargs
        assert call_kwargs['ExclusiveStartKey'] == start_key

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_list_by_global_type_success(
        self, base_repository, mock_dynamodb_client
    ):
        """Test listing items by global resource type."""
        mock_items = [
            {
                'test_id': 'test-1',
                'name': 'Global Item 1',
                'description': 'First',
                'is_active': True,
            },
            {
                'test_id': 'test-2',
                'name': 'Global Item 2',
                'description': 'Second',
                'is_active': True,
            },
        ]

        mock_dynamodb_client.query.return_value = {
            'Items': mock_items,
            'LastEvaluatedKey': None,
        }

        items, last_key = await base_repository.list_by_global_type(limit=15)

        assert len(items) == 2
        assert items[0].test_id == 'test-1'
        assert last_key is None

        call_kwargs = mock_dynamodb_client.query.call_args.kwargs
        assert call_kwargs['TableName'] == 'test-table'
        assert call_kwargs['IndexName'] == 'GlobalResourceIndex'
        assert call_kwargs['KeyConditionExpression'] == 'GlobalPK = :gpk'
        assert call_kwargs['ExpressionAttributeValues'][':gpk'] == 'RESOURCE_TYPE#TEST'
        assert call_kwargs['ScanIndexForward'] is False
        assert call_kwargs['Limit'] == 15

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_list_by_global_type_admin_only(
        self, base_repository, mock_dynamodb_client
    ):
        """Test listing items by global type with admin filter."""
        mock_items = [
            {
                'test_id': 'admin-1',
                'name': 'Admin Item',
                'description': 'Admin only',
                'is_active': True,
            }
        ]

        mock_dynamodb_client.query.return_value = {
            'Items': mock_items,
            'LastEvaluatedKey': None,
        }

        items, last_key = await base_repository.list_by_global_type(
            limit=20, is_admin_only=True
        )

        assert len(items) == 1
        assert items[0].test_id == 'admin-1'

        call_kwargs = mock_dynamodb_client.query.call_args.kwargs
        assert call_kwargs['FilterExpression'] == 'is_admin = :is_admin'
        assert call_kwargs['ExpressionAttributeValues'][':is_admin'] == 'true'

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_list_by_global_type_with_pagination(
        self, base_repository, mock_dynamodb_client
    ):
        """Test listing items by global type with pagination."""
        mock_items = [
            {
                'test_id': 'test-1',
                'name': 'Item',
                'description': 'Desc',
                'is_active': True,
            }
        ]
        start_key = {
            'GlobalPK': 'RESOURCE_TYPE#TEST',
            'GlobalSK': 'CREATED_AT#2025-01-01T10:00:00#test-0',
        }

        mock_dynamodb_client.query.return_value = {
            'Items': mock_items,
            'LastEvaluatedKey': None,
        }

        items, last_key = await base_repository.list_by_global_type(
            limit=10, last_key=start_key
        )

        assert len(items) == 1

        call_kwargs = mock_dynamodb_client.query.call_args.kwargs
        assert call_kwargs['ExclusiveStartKey'] == start_key


class TestBaseRepositoryErrorHandling:
    """Tests for error handling in BaseRepository."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Mock DynamoDB client for error testing."""
        return AsyncMock(spec=DynamoDBClient)

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for error testing."""
        mock_settings = MagicMock(spec=Settings)
        mock_dynamodb = MagicMock()
        mock_dynamodb.table_name = 'test-table'
        mock_settings.dynamodb = mock_dynamodb
        return mock_settings

    @pytest.fixture
    def base_repository(self, mock_dynamodb_client, mock_settings):
        """Create BaseRepository for error testing."""
        with patch('app.repositories.base.get_settings', return_value=mock_settings):
            return BaseRepository(
                dynamodb_client=mock_dynamodb_client,
                entity_type='TEST',
                model_class=TestModel,
            )

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_create_dynamodb_error_handling(
        self, base_repository, mock_dynamodb_client
    ):
        """Test create method handles DynamoDB errors."""
        sample_model = TestModel(
            test_id='test-error', name='Error Test', description='This will fail'
        )

        mock_dynamodb_client.put_item.side_effect = Exception(
            'DynamoDB connection failed'
        )

        with patch('app.repositories.base.make_json_serializable') as mock_serialize:
            mock_serialize.return_value = {'serialized': 'item'}

            with pytest.raises(Exception, match='DynamoDB connection failed'):
                await base_repository.create(sample_model)

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_get_dynamodb_error_handling(
        self, base_repository, mock_dynamodb_client
    ):
        """Test get method handles DynamoDB errors."""
        mock_dynamodb_client.get_item.side_effect = Exception('DynamoDB read error')

        with pytest.raises(Exception, match='DynamoDB read error'):
            await base_repository.get('test-error')

    @pytest.mark.asyncio
    @pytest.mark.data
    async def test_query_operations_error_handling(
        self, base_repository, mock_dynamodb_client
    ):
        """Test query operations handle DynamoDB errors."""
        mock_dynamodb_client.query.side_effect = Exception('DynamoDB query error')

        with pytest.raises(Exception, match='DynamoDB query error'):
            await base_repository.list_by_user('user-error')

        with pytest.raises(Exception, match='DynamoDB query error'):
            await base_repository.list_by_global_type()


class TestBaseRepositoryIntegration:
    """Integration tests for BaseRepository with different model types."""

    @pytest.mark.asyncio
    @pytest.mark.data
    @pytest.mark.integration
    async def test_repository_with_different_entity_types(self):
        """Test repository works with different entity types."""
        # This would test with actual DynamoDB mocking (moto)
        pytest.skip('Integration test requires moto DynamoDB setup')

    @pytest.mark.asyncio
    @pytest.mark.data
    @pytest.mark.integration
    async def test_gsi_query_performance(self):
        """Test GSI query performance with large datasets."""
        # This would test query performance patterns
        pytest.skip('Performance test requires complex setup')
