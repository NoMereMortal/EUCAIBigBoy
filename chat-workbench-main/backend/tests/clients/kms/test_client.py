# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for app/clients/kms/client.py - AWS KMS encryption/decryption functionality."""

import base64
from unittest.mock import MagicMock, patch

import pytest
from app.clients.kms.client import KMSClient
from app.config import Settings
from botocore.exceptions import ClientError


class TestKMSClient:
    """Tests for KMSClient class in app/clients/kms/client.py."""

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
    def kms_client(self, mock_settings):
        """Create KMSClient instance with mocked settings."""
        return KMSClient(mock_settings)

    @pytest.fixture
    def mock_boto_client(self):
        """Mock boto3 KMS client."""
        mock_client = MagicMock()
        mock_client.encrypt.return_value = {'CiphertextBlob': b'encrypted_data_blob'}
        mock_client.decrypt.return_value = {'Plaintext': b'decrypted_plaintext'}
        mock_client.generate_data_key.return_value = {
            'Plaintext': b'plaintext_key',
            'CiphertextBlob': b'encrypted_key',
            'KeyId': 'arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012',
        }
        mock_client.create_key.return_value = {
            'KeyMetadata': {
                'KeyId': '12345678-1234-1234-1234-123456789012',
                'Arn': 'arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012',
                'Description': 'Test key',
            }
        }
        return mock_client

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_kms_client_initialization_success(
        self, kms_client, mock_boto_client
    ):
        """Test successful KMS client initialization."""
        with patch('boto3.client', return_value=mock_boto_client):
            await kms_client.initialize()

            assert kms_client._client is not None
            assert kms_client._client == mock_boto_client

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_kms_client_cleanup(self, kms_client, mock_boto_client):
        """Test KMS client cleanup."""
        with patch('boto3.client', return_value=mock_boto_client):
            await kms_client.initialize()
            assert kms_client._client is not None

            await kms_client.cleanup()
            assert kms_client._client is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_encrypt_string_success(self, kms_client, mock_boto_client):
        """Test successful string encryption."""
        key_id = 'arn:aws:kms:us-east-1:123456789012:key/test-key'
        plaintext = 'sensitive data'

        with patch('boto3.client', return_value=mock_boto_client):
            result = await kms_client.encrypt(key_id, plaintext)

            assert result == b'encrypted_data_blob'
            mock_boto_client.encrypt.assert_called_once_with(
                KeyId=key_id, Plaintext=plaintext.encode('utf-8')
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_encrypt_bytes_success(self, kms_client, mock_boto_client):
        """Test successful bytes encryption."""
        key_id = 'test-key-id'
        plaintext_bytes = b'binary sensitive data'

        with patch('boto3.client', return_value=mock_boto_client):
            result = await kms_client.encrypt(key_id, plaintext_bytes)

            assert result == b'encrypted_data_blob'
            mock_boto_client.encrypt.assert_called_once_with(
                KeyId=key_id, Plaintext=plaintext_bytes
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_encrypt_with_encryption_context(self, kms_client, mock_boto_client):
        """Test encryption with encryption context."""
        key_id = 'test-key'
        plaintext = 'secret'
        encryption_context = {'purpose': 'testing', 'environment': 'dev'}

        with patch('boto3.client', return_value=mock_boto_client):
            result = await kms_client.encrypt(key_id, plaintext, encryption_context)

            assert result == b'encrypted_data_blob'
            mock_boto_client.encrypt.assert_called_once_with(
                KeyId=key_id,
                Plaintext=plaintext.encode('utf-8'),
                EncryptionContext=encryption_context,
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_encrypt_client_error_handling(self, kms_client):
        """Test encrypt method handles client errors gracefully."""
        key_id = 'invalid-key'
        plaintext = 'data'

        mock_client = MagicMock()
        mock_client.encrypt.side_effect = ClientError(
            {'Error': {'Code': 'InvalidKeyId.NotFound', 'Message': 'Key not found'}},
            'Encrypt',
        )

        with patch('boto3.client', return_value=mock_client):
            result = await kms_client.encrypt(key_id, plaintext)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_encrypt_circuit_breaker_open(self, kms_client):
        """Test encrypt method respects circuit breaker state."""
        key_id = 'test-key'
        plaintext = 'data'

        # Mock circuit breaker as open
        kms_client.circuit_breaker.can_execute = MagicMock(return_value=False)

        result = await kms_client.encrypt(key_id, plaintext)

        assert result is None
        kms_client.circuit_breaker.can_execute.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_decrypt_success(self, kms_client, mock_boto_client):
        """Test successful decryption."""
        ciphertext = b'encrypted_data_blob'

        with patch('boto3.client', return_value=mock_boto_client):
            result = await kms_client.decrypt(ciphertext)

            assert result == b'decrypted_plaintext'
            mock_boto_client.decrypt.assert_called_once_with(CiphertextBlob=ciphertext)

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_decrypt_with_encryption_context(self, kms_client, mock_boto_client):
        """Test decryption with encryption context."""
        ciphertext = b'encrypted_data'
        encryption_context = {'purpose': 'testing'}
        key_id = 'test-key'

        with patch('boto3.client', return_value=mock_boto_client):
            result = await kms_client.decrypt(ciphertext, encryption_context, key_id)

            assert result == b'decrypted_plaintext'
            mock_boto_client.decrypt.assert_called_once_with(
                CiphertextBlob=ciphertext,
                EncryptionContext=encryption_context,
                KeyId=key_id,
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_decrypt_client_error_handling(self, kms_client):
        """Test decrypt method handles client errors gracefully."""
        ciphertext = b'invalid_ciphertext'

        mock_client = MagicMock()
        mock_client.decrypt.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'InvalidCiphertextException',
                    'Message': 'Invalid ciphertext',
                }
            },
            'Decrypt',
        )

        with patch('boto3.client', return_value=mock_client):
            result = await kms_client.decrypt(ciphertext)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_encrypt_string_failure(self, kms_client):
        """Test encrypt_string returns None when encryption fails."""
        key_id = 'invalid-key'
        plaintext = 'data'

        mock_client = MagicMock()
        mock_client.encrypt.side_effect = Exception('Encryption failed')

        with patch('boto3.client', return_value=mock_client):
            result = await kms_client.encrypt_string(key_id, plaintext)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_decrypt_string_success(self, kms_client, mock_boto_client):
        """Test successful string decryption from base64."""
        ciphertext_blob = b'encrypted_data_blob'
        ciphertext_base64 = base64.b64encode(ciphertext_blob).decode('utf-8')

        mock_boto_client.decrypt.return_value = {'Plaintext': b'decrypted string data'}

        with patch('boto3.client', return_value=mock_boto_client):
            result = await kms_client.decrypt_string(ciphertext_base64)

            assert result == 'decrypted string data'
            mock_boto_client.decrypt.assert_called_once_with(
                CiphertextBlob=ciphertext_blob
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_decrypt_string_invalid_base64(self, kms_client):
        """Test decrypt_string handles invalid base64 input."""
        invalid_base64 = 'not_valid_base64!@#'

        result = await kms_client.decrypt_string(invalid_base64)

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_decrypt_string_decryption_failure(
        self, kms_client, mock_boto_client
    ):
        """Test decrypt_string handles decryption failure."""
        ciphertext_blob = b'invalid_encrypted_data'
        ciphertext_base64 = base64.b64encode(ciphertext_blob).decode('utf-8')

        mock_boto_client.decrypt.side_effect = Exception('Decryption failed')

        with patch('boto3.client', return_value=mock_boto_client):
            result = await kms_client.decrypt_string(ciphertext_base64)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_generate_data_key_success(self, kms_client, mock_boto_client):
        """Test successful data key generation."""
        key_id = 'test-master-key'
        key_spec = 'AES_256'

        with patch('boto3.client', return_value=mock_boto_client):
            result = await kms_client.generate_data_key(key_id, key_spec)

            assert result is not None
            assert 'plaintext' in result
            assert 'ciphertext' in result
            assert 'key_id' in result
            assert result['plaintext'] == b'plaintext_key'
            assert result['ciphertext'] == b'encrypted_key'

            mock_boto_client.generate_data_key.assert_called_once_with(
                KeyId=key_id, KeySpec=key_spec
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_generate_data_key_with_encryption_context(
        self, kms_client, mock_boto_client
    ):
        """Test data key generation with encryption context."""
        key_id = 'test-key'
        encryption_context = {'purpose': 'data-encryption'}

        with patch('boto3.client', return_value=mock_boto_client):
            result = await kms_client.generate_data_key(
                key_id, encryption_context=encryption_context
            )

            assert result is not None
            mock_boto_client.generate_data_key.assert_called_once_with(
                KeyId=key_id, KeySpec='AES_256', EncryptionContext=encryption_context
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_generate_data_key_client_error(self, kms_client):
        """Test generate_data_key handles client errors."""
        key_id = 'invalid-key'

        mock_client = MagicMock()
        mock_client.generate_data_key.side_effect = ClientError(
            {'Error': {'Code': 'InvalidKeyId.NotFound', 'Message': 'Key not found'}},
            'GenerateDataKey',
        )

        with patch('boto3.client', return_value=mock_client):
            result = await kms_client.generate_data_key(key_id)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_create_key_success(self, kms_client, mock_boto_client):
        """Test successful key creation."""
        description = 'Test encryption key'
        tags = {'Environment': 'test', 'Purpose': 'encryption'}

        with patch('boto3.client', return_value=mock_boto_client):
            result = await kms_client.create_key(description, tags)

            assert result is not None
            assert 'KeyId' in result
            assert result['Description'] == 'Test key'

            expected_tags = [
                {'TagKey': 'Environment', 'TagValue': 'test'},
                {'TagKey': 'Purpose', 'TagValue': 'encryption'},
            ]
            mock_boto_client.create_key.assert_called_once_with(
                Description=description, Tags=expected_tags
            )

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_create_key_without_tags(self, kms_client, mock_boto_client):
        """Test key creation without tags."""
        description = 'Simple test key'

        with patch('boto3.client', return_value=mock_boto_client):
            result = await kms_client.create_key(description)

            assert result is not None
            mock_boto_client.create_key.assert_called_once_with(Description=description)

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_create_key_client_error(self, kms_client):
        """Test create_key handles client errors."""
        description = 'Test key'

        mock_client = MagicMock()
        mock_client.create_key.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'LimitExceededException',
                    'Message': 'Key limit exceeded',
                }
            },
            'CreateKey',
        )

        with patch('boto3.client', return_value=mock_client):
            result = await kms_client.create_key(description)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_auto_initialization_on_method_calls(
        self, kms_client, mock_boto_client
    ):
        """Test that methods auto-initialize the client if not already initialized."""
        key_id = 'test-key'
        plaintext = 'test data'

        # Ensure client is not initialized
        assert kms_client._client is None

        with patch('boto3.client', return_value=mock_boto_client):
            # Call encrypt, which should auto-initialize
            result = await kms_client.encrypt(key_id, plaintext)

            assert result == b'encrypted_data_blob'
            assert kms_client._client == mock_boto_client

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_client_not_initialized_error_handling(self, kms_client):
        """Test handling when client fails to initialize."""
        key_id = 'test-key'
        plaintext = 'data'

        with patch('boto3.client', side_effect=Exception('AWS credentials not found')):
            result = await kms_client.encrypt(key_id, plaintext)

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.aws
    async def test_monitor_operation_context_manager(
        self, kms_client, mock_boto_client
    ):
        """Test that operations use monitor_operation context manager."""
        key_id = 'test-key'
        plaintext = 'data'

        with patch('boto3.client', return_value=mock_boto_client) and patch.object(
            kms_client, 'monitor_operation'
        ) as mock_monitor:
            mock_monitor.return_value.__enter__ = MagicMock()
            mock_monitor.return_value.__exit__ = MagicMock()

            await kms_client.encrypt(key_id, plaintext)

            mock_monitor.assert_called_with('encrypt')


class TestKMSClientIntegration:
    """Integration tests for KMS client operations."""

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
    def kms_client(self, mock_settings):
        """Create KMS client for integration testing."""
        return KMSClient(mock_settings)

    @pytest.mark.asyncio
    @pytest.mark.aws
    @pytest.mark.integration
    async def test_encrypt_decrypt_round_trip(self, kms_client):
        """Test encryption/decryption round trip with mocked AWS services."""
        # This test would use moto to mock AWS services
        # For now, we'll skip it as it requires more complex setup
        pytest.skip('Integration test requires moto AWS mocking setup')

    @pytest.mark.asyncio
    @pytest.mark.aws
    @pytest.mark.integration
    async def test_data_key_generation_workflow(self, kms_client):
        """Test complete data key generation workflow."""
        # This would test the full workflow of generating, using, and discarding data keys
        pytest.skip('Integration test requires moto AWS mocking setup')
