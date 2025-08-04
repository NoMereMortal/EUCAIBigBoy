# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for app/clients/secrets_manager/client.py - AWS Secrets Manager functionality."""

import json
from unittest.mock import MagicMock, patch

import pytest
from app.clients.secrets_manager.client import SecretsManagerClient
from app.config import Settings
from botocore.exceptions import ClientError


class TestSecretsManagerClient:
    """Tests for SecretsManagerClient class in app/clients/secrets_manager/client.py."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with AWS configuration."""
        mock_settings = MagicMock(spec=Settings)
        mock_aws_config = MagicMock()
        mock_aws_config.region = 'us-east-1'
        mock_aws_config.endpoint_url = None
        mock_aws_config.get_boto_config.return_value = MagicMock()
        mock_settings.get_aws_config.return_value = mock_aws_config
        return mock_settings

    @pytest.fixture
    def secrets_client(self, mock_settings):
        """Create SecretsManagerClient instance with mocked settings."""
        return SecretsManagerClient(mock_settings)

    @pytest.fixture
    def mock_boto_client(self):
        """Mock boto3 Secrets Manager client."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(
                {
                    'username': 'testuser',
                    'password': 'testpassword',
                    'database': 'testdb',
                }
            )
        }
        mock_client.create_secret.return_value = {
            'ARN': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret-AbCdEf'
        }
        return mock_client

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_secrets_manager_client_initialization_success(
        self, secrets_client, mock_boto_client
    ):
        """Test successful Secrets Manager client initialization."""
        with patch('boto3.client', return_value=mock_boto_client):
            await secrets_client.initialize()

            assert secrets_client._client is not None
            assert secrets_client._client == mock_boto_client
            assert isinstance(secrets_client._cache, dict)

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_secrets_manager_client_cleanup(
        self, secrets_client, mock_boto_client
    ):
        """Test Secrets Manager client cleanup."""
        with patch('boto3.client', return_value=mock_boto_client):
            await secrets_client.initialize()
            secrets_client._cache['test'] = {'cached': 'value'}

            assert secrets_client._client is not None
            assert len(secrets_client._cache) == 1

            await secrets_client.cleanup()

            assert secrets_client._client is None
            assert len(secrets_client._cache) == 0

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_get_secret_value_success_json(
        self, secrets_client, mock_boto_client
    ):
        """Test successful secret retrieval with JSON value."""
        secret_id = 'test-database-credentials'
        expected_secret = {
            'username': 'testuser',
            'password': 'testpassword',
            'database': 'testdb',
        }

        with patch('boto3.client', return_value=mock_boto_client):
            result = await secrets_client.get_secret_value(secret_id)

            assert result == expected_secret
            mock_boto_client.get_secret_value.assert_called_once_with(
                SecretId=secret_id
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_get_secret_value_success_plain_string(self, secrets_client):
        """Test successful secret retrieval with plain string value."""
        secret_id = 'test-api-key'
        secret_string = 'plain-text-api-key-12345'

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {'SecretString': secret_string}

        with patch('boto3.client', return_value=mock_client):
            result = await secrets_client.get_secret_value(secret_id)

            assert result == {'value': secret_string}
            mock_client.get_secret_value.assert_called_once_with(SecretId=secret_id)

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_get_secret_value_with_caching(
        self, secrets_client, mock_boto_client
    ):
        """Test secret retrieval with caching enabled."""
        secret_id = 'cached-secret'

        with patch('boto3.client', return_value=mock_boto_client):
            # First call - should hit the service
            result1 = await secrets_client.get_secret_value(secret_id, cache=True)
            assert result1 is not None

            # Second call - should use cache
            result2 = await secrets_client.get_secret_value(secret_id, cache=True)
            assert result2 == result1

            # Should only call the service once due to caching
            assert mock_boto_client.get_secret_value.call_count == 1

            # Verify secret is in cache
            assert secret_id in secrets_client._cache

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_get_secret_value_without_caching(
        self, secrets_client, mock_boto_client
    ):
        """Test secret retrieval with caching disabled."""
        secret_id = 'non-cached-secret'

        with patch('boto3.client', return_value=mock_boto_client):
            # First call
            result1 = await secrets_client.get_secret_value(secret_id, cache=False)
            assert result1 is not None

            # Second call
            result2 = await secrets_client.get_secret_value(secret_id, cache=False)
            assert result2 is not None

            # Should call the service twice since caching is disabled
            assert mock_boto_client.get_secret_value.call_count == 2

            # Verify secret is not in cache
            assert secret_id not in secrets_client._cache

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_get_secret_value_not_found_error(self, secrets_client):
        """Test handling of secret not found error."""
        secret_id = 'non-existent-secret'

        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'ResourceNotFoundException',
                    'Message': 'Secret not found',
                }
            },
            'GetSecretValue',
        )

        with patch('boto3.client', return_value=mock_client):
            result = await secrets_client.get_secret_value(secret_id)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_get_secret_value_access_denied_error(self, secrets_client):
        """Test handling of access denied error."""
        secret_id = 'restricted-secret'

        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'GetSecretValue',
        )

        with patch('boto3.client', return_value=mock_client):
            result = await secrets_client.get_secret_value(secret_id)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_get_secret_value_circuit_breaker_open(self, secrets_client):
        """Test get_secret_value respects circuit breaker state."""
        secret_id = 'test-secret'

        # Mock circuit breaker as open
        secrets_client.circuit_breaker.can_execute = MagicMock(return_value=False)

        result = await secrets_client.get_secret_value(secret_id)

        assert result is None
        secrets_client.circuit_breaker.can_execute.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_get_secret_value_no_secret_string(self, secrets_client):
        """Test handling when response has no SecretString."""
        secret_id = 'binary-secret'

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            # No SecretString in response
            'SecretBinary': b'binary_data'
        }

        with patch('boto3.client', return_value=mock_client):
            result = await secrets_client.get_secret_value(secret_id)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_create_secret_success(self, secrets_client, mock_boto_client):
        """Test successful secret creation."""
        secret_name = 'new-test-secret'
        secret_value = {
            'api_key': 'new-api-key-12345',
            'database_url': 'postgresql://user:pass@host:5432/db',
        }

        with patch('boto3.client', return_value=mock_boto_client):
            result = await secrets_client.create_secret(secret_name, secret_value)

            assert (
                result
                == 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret-AbCdEf'
            )

            expected_secret_string = json.dumps(secret_value)
            mock_boto_client.create_secret.assert_called_once_with(
                Name=secret_name, SecretString=expected_secret_string
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_create_secret_already_exists_error(self, secrets_client):
        """Test handling of secret already exists error."""
        secret_name = 'existing-secret'
        secret_value = {'key': 'value'}

        mock_client = MagicMock()
        mock_client.create_secret.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'ResourceExistsException',
                    'Message': 'Secret already exists',
                }
            },
            'CreateSecret',
        )

        with patch('boto3.client', return_value=mock_client):
            result = await secrets_client.create_secret(secret_name, secret_value)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_create_secret_clears_cache(self, secrets_client, mock_boto_client):
        """Test that creating a secret clears its cache entry."""
        secret_name = 'cached-secret-to-update'
        secret_value = {'new': 'value'}

        # Pre-populate cache
        secrets_client._cache[secret_name] = {'old': 'cached_value'}

        with patch('boto3.client', return_value=mock_boto_client):
            result = await secrets_client.create_secret(secret_name, secret_value)

            assert result is not None
            assert secret_name not in secrets_client._cache

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_update_secret_success(self, secrets_client, mock_boto_client):
        """Test successful secret update."""
        secret_id = 'existing-secret'
        new_value = {
            'updated_key': 'updated_value',
            'timestamp': '2025-01-01T00:00:00Z',
        }

        with patch('boto3.client', return_value=mock_boto_client):
            result = await secrets_client.update_secret(secret_id, new_value)

            assert result is True

            expected_secret_string = json.dumps(new_value)
            mock_boto_client.update_secret.assert_called_once_with(
                SecretId=secret_id, SecretString=expected_secret_string
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_update_secret_not_found_error(self, secrets_client):
        """Test handling of secret not found during update."""
        secret_id = 'non-existent-secret'
        new_value = {'key': 'value'}

        mock_client = MagicMock()
        mock_client.update_secret.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'ResourceNotFoundException',
                    'Message': 'Secret not found',
                }
            },
            'UpdateSecret',
        )

        with patch('boto3.client', return_value=mock_client):
            result = await secrets_client.update_secret(secret_id, new_value)

            assert result is False

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_update_secret_clears_cache(self, secrets_client, mock_boto_client):
        """Test that updating a secret clears its cache entry."""
        secret_id = 'cached-secret'
        new_value = {'updated': 'value'}

        # Pre-populate cache
        secrets_client._cache[secret_id] = {'old': 'cached_value'}

        with patch('boto3.client', return_value=mock_boto_client):
            result = await secrets_client.update_secret(secret_id, new_value)

            assert result is True
            assert secret_id not in secrets_client._cache

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_delete_secret_success(self, secrets_client, mock_boto_client):
        """Test successful secret deletion."""
        secret_id = 'secret-to-delete'
        recovery_window = 7

        with patch('boto3.client', return_value=mock_boto_client):
            result = await secrets_client.delete_secret(secret_id, recovery_window)

            assert result is True

            mock_boto_client.delete_secret.assert_called_once_with(
                SecretId=secret_id, RecoveryWindowInDays=recovery_window
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_delete_secret_default_recovery_window(
        self, secrets_client, mock_boto_client
    ):
        """Test secret deletion with default recovery window."""
        secret_id = 'secret-to-delete'

        with patch('boto3.client', return_value=mock_boto_client):
            result = await secrets_client.delete_secret(secret_id)

            assert result is True

            mock_boto_client.delete_secret.assert_called_once_with(
                SecretId=secret_id,
                RecoveryWindowInDays=30,  # Default value
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_delete_secret_not_found_error(self, secrets_client):
        """Test handling of secret not found during deletion."""
        secret_id = 'non-existent-secret'

        mock_client = MagicMock()
        mock_client.delete_secret.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'ResourceNotFoundException',
                    'Message': 'Secret not found',
                }
            },
            'DeleteSecret',
        )

        with patch('boto3.client', return_value=mock_client):
            result = await secrets_client.delete_secret(secret_id)

            assert result is False

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_delete_secret_clears_cache(self, secrets_client, mock_boto_client):
        """Test that deleting a secret clears its cache entry."""
        secret_id = 'cached-secret-to-delete'

        # Pre-populate cache
        secrets_client._cache[secret_id] = {'cached': 'value'}

        with patch('boto3.client', return_value=mock_boto_client):
            result = await secrets_client.delete_secret(secret_id)

            assert result is True
            assert secret_id not in secrets_client._cache

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_auto_initialization_on_method_calls(
        self, secrets_client, mock_boto_client
    ):
        """Test that methods auto-initialize the client if not already initialized."""
        secret_id = 'test-secret'

        # Ensure client is not initialized
        assert secrets_client._client is None

        with patch('boto3.client', return_value=mock_boto_client):
            # Call get_secret_value, which should auto-initialize
            result = await secrets_client.get_secret_value(secret_id)

            assert result is not None
            assert secrets_client._client == mock_boto_client

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_client_not_initialized_error_handling(self, secrets_client):
        """Test handling when client fails to initialize."""
        secret_id = 'test-secret'

        with patch('boto3.client', side_effect=Exception('AWS credentials not found')):
            result = await secrets_client.get_secret_value(secret_id)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_monitor_operation_context_manager(
        self, secrets_client, mock_boto_client
    ):
        """Test that operations use monitor_operation context manager."""
        secret_id = 'test-secret'

        with patch('boto3.client', return_value=mock_boto_client) and patch.object(
            secrets_client, 'monitor_operation'
        ) as mock_monitor:
            mock_monitor.return_value.__enter__ = MagicMock()
            mock_monitor.return_value.__exit__ = MagicMock()

            await secrets_client.get_secret_value(secret_id)

            mock_monitor.assert_called_with('get_secret_value')


class TestSecretsManagerClientCacheManagement:
    """Tests for cache management in SecretsManagerClient."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for cache tests."""
        mock_settings = MagicMock(spec=Settings)
        mock_aws_config = MagicMock()
        mock_aws_config.region = 'us-west-2'
        mock_aws_config.endpoint_url = None
        mock_aws_config.get_boto_config.return_value = MagicMock()
        mock_settings.get_aws_config.return_value = mock_aws_config
        return mock_settings

    @pytest.fixture
    def secrets_client(self, mock_settings):
        """Create SecretsManagerClient for cache testing."""
        return SecretsManagerClient(mock_settings)

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_cache_behavior_with_multiple_secrets(self, secrets_client):
        """Test cache behavior with multiple different secrets."""
        secrets = {
            'secret1': {'key1': 'value1'},
            'secret2': {'key2': 'value2'},
            'secret3': {'key3': 'value3'},
        }

        mock_client = MagicMock()

        def mock_get_secret_value(SecretId):
            return {'SecretString': json.dumps(secrets[SecretId])}

        mock_client.get_secret_value.side_effect = mock_get_secret_value

        with patch('boto3.client', return_value=mock_client):
            # Retrieve all secrets with caching
            results = {}
            for secret_id in secrets:
                results[secret_id] = await secrets_client.get_secret_value(
                    secret_id, cache=True
                )

            # Verify all are cached
            assert len(secrets_client._cache) == 3
            for secret_id, expected_value in secrets.items():
                assert secret_id in secrets_client._cache
                assert secrets_client._cache[secret_id] == expected_value
                assert results[secret_id] == expected_value

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_cache_invalidation_on_operations(self, secrets_client):
        """Test that cache is properly invalidated on create/update/delete operations."""
        secret_id = 'test-secret'
        original_value = {'original': 'value'}
        updated_value = {'updated': 'value'}

        # Setup mock client
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(original_value)
        }
        mock_client.create_secret.return_value = {'ARN': 'test-arn'}

        with patch('boto3.client', return_value=mock_client):
            # Get secret to populate cache
            result = await secrets_client.get_secret_value(secret_id, cache=True)
            assert result == original_value
            assert secret_id in secrets_client._cache

            # Create operation should clear cache
            await secrets_client.create_secret(secret_id, updated_value)
            assert secret_id not in secrets_client._cache

            # Re-populate cache
            await secrets_client.get_secret_value(secret_id, cache=True)
            assert secret_id in secrets_client._cache

            # Update operation should clear cache
            await secrets_client.update_secret(secret_id, updated_value)
            assert secret_id not in secrets_client._cache

            # Re-populate cache
            await secrets_client.get_secret_value(secret_id, cache=True)
            assert secret_id in secrets_client._cache

            # Delete operation should clear cache
            await secrets_client.delete_secret(secret_id)
            assert secret_id not in secrets_client._cache


class TestSecretsManagerClientIntegration:
    """Integration tests for Secrets Manager client operations."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for integration tests."""
        mock_settings = MagicMock(spec=Settings)
        mock_aws_config = MagicMock()
        mock_aws_config.region = 'us-west-2'
        mock_aws_config.endpoint_url = 'http://localhost:4566'  # LocalStack
        mock_aws_config.get_boto_config.return_value = MagicMock()
        mock_settings.get_aws_config.return_value = mock_aws_config
        return mock_settings

    @pytest.fixture
    def secrets_client(self, mock_settings):
        """Create Secrets Manager client for integration testing."""
        return SecretsManagerClient(mock_settings)

    @pytest.mark.asyncio
    @pytest.mark.aws
    @pytest.mark.integration
    async def test_secrets_lifecycle_management(self, secrets_client):
        """Test complete secrets lifecycle: create, read, update, delete."""
        # This test would use moto to mock AWS services
        # For now, we'll skip it as it requires more complex setup
        pytest.skip('Integration test requires moto AWS mocking setup')

    @pytest.mark.asyncio
    @pytest.mark.aws
    @pytest.mark.integration
    async def test_concurrent_secret_access(self, secrets_client):
        """Test concurrent access to the same secret with caching."""
        # This would test concurrent access patterns and cache consistency
        pytest.skip('Integration test requires moto AWS mocking setup')
