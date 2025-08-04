# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""AWS KMS client."""

import base64
from typing import Any, Union

import boto3
from loguru import logger

from app.clients.base import BaseClient
from app.config import Settings
from app.utils import get_function_name


class KMSClient(BaseClient):
    """AWS KMS (Key Management Service) client."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the KMS client."""
        super().__init__()
        self._client = None

    async def initialize(self) -> None:
        """Initialize the KMS client."""
        aws_config = self.settings.get_aws_config()

        self._client = boto3.client(
            'kms',
            region_name=aws_config.region,
            endpoint_url=aws_config.endpoint_url,
            config=aws_config.get_boto_config('kms'),
        )
        logger.info('KMS client initialized')

    async def cleanup(self) -> None:
        """Clean up the KMS client."""
        self._client = None
        logger.info('KMS client cleaned up')

    async def encrypt(
        self,
        key_id: str,
        plaintext: Union[str, bytes],
        encryption_context: dict[str, str] | None = None,
    ) -> bytes | None:
        """
        Encrypt data using a KMS key.

        Args:
            key_id: The ID or ARN of the KMS key to use
            plaintext: The data to encrypt, either as string or bytes
            encryption_context: Optional encryption context

        Returns:
            The encrypted ciphertext as bytes, or None if encryption failed
        """
        with self.monitor_operation(get_function_name()):
            # Check if circuit is open
            if not self.circuit_breaker.can_execute():
                logger.warning('Circuit breaker open for KMS')
                return None

            try:
                if self._client is None:
                    await self.initialize()

                if not self._client:
                    raise ValueError('KMS client not initialized')

                # Convert string to bytes if needed
                if isinstance(plaintext, str):
                    plaintext_bytes = plaintext.encode('utf-8')
                else:
                    plaintext_bytes = plaintext

                # Encrypt the data
                kwargs: dict[str, Any] = {'KeyId': key_id, 'Plaintext': plaintext_bytes}
                if encryption_context:
                    kwargs['EncryptionContext'] = encryption_context

                response = self._client.encrypt(**kwargs)

                return response.get('CiphertextBlob')

            except Exception as e:
                logger.error(f'Failed to encrypt data with KMS key {key_id}: {e}')
                return None

    async def decrypt(
        self,
        ciphertext: bytes,
        encryption_context: dict[str, str] | None = None,
        key_id: str | None = None,
    ) -> bytes | None:
        """
        Decrypt data that was encrypted with a KMS key.

        Args:
            ciphertext: The encrypted data as bytes
            encryption_context: Optional encryption context (must match the one used for encryption)
            key_id: Optional key ID or ARN to verify the data was encrypted with this specific key

        Returns:
            The decrypted plaintext as bytes, or None if decryption failed
        """
        with self.monitor_operation(get_function_name()):
            # Check if circuit is open
            if not self.circuit_breaker.can_execute():
                logger.warning('Circuit breaker open for KMS')
                return None

            try:
                if self._client is None:
                    await self.initialize()

                if not self._client:
                    raise ValueError('KMS client not initialized')

                # Decrypt the data
                kwargs: dict[str, Any] = {'CiphertextBlob': ciphertext}
                if encryption_context:
                    kwargs['EncryptionContext'] = encryption_context
                if key_id:
                    kwargs['KeyId'] = key_id

                response = self._client.decrypt(**kwargs)

                return response.get('Plaintext')

            except Exception as e:
                logger.error(f'Failed to decrypt data: {e}')
                return None

    async def encrypt_string(
        self,
        key_id: str,
        plaintext: str,
        encryption_context: dict[str, str] | None = None,
    ) -> str | None:
        """
        Encrypt a string using a KMS key and return a base64-encoded string.

        Args:
            key_id: The ID or ARN of the KMS key to use
            plaintext: The string to encrypt
            encryption_context: Optional encryption context

        Returns:
            Base64-encoded ciphertext as a string, or None if encryption failed
        """
        ciphertext_blob = await self.encrypt(key_id, plaintext, encryption_context)
        if ciphertext_blob is None:
            return None

        # Convert bytes to base64-encoded string for easy storage/transmission
        return base64.b64encode(ciphertext_blob).decode('utf-8')

    async def decrypt_string(
        self,
        ciphertext_base64: str,
        encryption_context: dict[str, str] | None = None,
        key_id: str | None = None,
    ) -> str | None:
        """
        Decrypt a base64-encoded string that was encrypted with a KMS key.

        Args:
            ciphertext_base64: The encrypted data as a base64-encoded string
            encryption_context: Optional encryption context (must match the one used for encryption)
            key_id: Optional key ID or ARN to verify the data was encrypted with this specific key

        Returns:
            The decrypted plaintext as a string, or None if decryption failed
        """
        try:
            # Convert base64 string to bytes
            ciphertext_blob = base64.b64decode(ciphertext_base64)

            plaintext_bytes = await self.decrypt(
                ciphertext_blob, encryption_context, key_id
            )
            if plaintext_bytes is None:
                return None

            # Convert bytes to string
            return plaintext_bytes.decode('utf-8')

        except Exception as e:
            logger.error(f'Failed to decode base64 or decrypt string: {e}')
            return None

    async def generate_data_key(
        self,
        key_id: str,
        key_spec: str = 'AES_256',
        encryption_context: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        """
        Generate a data key for client-side encryption.

        Args:
            key_id: The ID or ARN of the KMS key to use
            key_spec: The type of data key to generate (AES_256 or AES_128)
            encryption_context: Optional encryption context

        Returns:
            Dict containing both the encrypted and plaintext data key, or None if generation failed
        """
        with self.monitor_operation(get_function_name()):
            # Check if circuit is open
            if not self.circuit_breaker.can_execute():
                logger.warning('Circuit breaker open for KMS')
                return None

            try:
                if self._client is None:
                    await self.initialize()

                if not self._client:
                    raise ValueError('KMS client not initialized')

                # Generate the data key
                kwargs: dict[str, Any] = {'KeyId': key_id, 'KeySpec': key_spec}
                if encryption_context:
                    kwargs['EncryptionContext'] = encryption_context

                response = self._client.generate_data_key(**kwargs)

                return {
                    'plaintext': response.get(
                        'Plaintext'
                    ),  # Use this for encryption, then discard
                    'ciphertext': response.get('CiphertextBlob'),  # Store this securely
                    'key_id': response.get('KeyId'),  # The KMS key ID used
                }

            except Exception as e:
                logger.error(f'Failed to generate data key with KMS key {key_id}: {e}')
                return None

    async def create_key(
        self, description: str, tags: dict[str, str] | None = None
    ) -> dict[str, Any] | None:
        """
        Create a new KMS key.

        Args:
            description: Description of the key
            tags: Optional tags to attach to the key

        Returns:
            Dict with key metadata, or None if creation failed
        """
        with self.monitor_operation(get_function_name()):
            # Check if circuit is open
            if not self.circuit_breaker.can_execute():
                logger.warning('Circuit breaker open for KMS')
                return None

            try:
                if self._client is None:
                    await self.initialize()

                if not self._client:
                    raise ValueError('KMS client not initialized')

                # Create the key
                kwargs: dict[str, Any] = {'Description': description}

                if tags:
                    tag_list = [{'TagKey': k, 'TagValue': v} for k, v in tags.items()]
                    kwargs['Tags'] = tag_list

                response = self._client.create_key(**kwargs)

                return response.get('KeyMetadata')

            except Exception as e:
                logger.error(f'Failed to create KMS key: {e}')
                return None
