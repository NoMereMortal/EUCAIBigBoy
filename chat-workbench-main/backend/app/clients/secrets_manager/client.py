# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""AWS Secrets Manager client."""

import json
from typing import Any, cast

import boto3
from loguru import logger

from app.clients.base import BaseClient
from app.config import Settings
from app.utils import get_function_name


class SecretsManagerClient(BaseClient):
    """AWS Secrets Manager client."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the Secrets Manager client."""
        super().__init__()
        self._client = None
        self._cache: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize the Secrets Manager client."""
        aws_config = self.settings.get_aws_config()

        self._client = boto3.client(
            'secretsmanager',
            region_name=aws_config.region,
            endpoint_url=aws_config.endpoint_url,
            config=aws_config.get_boto_config('secretsmanager'),
        )
        logger.info('Secrets Manager client initialized')

    async def cleanup(self) -> None:
        """Clean up the Secrets Manager client."""
        self._client = None
        self._cache.clear()
        logger.info('Secrets Manager client cleaned up')

    async def get_secret_value(
        self, secret_id: str, cache: bool = True
    ) -> dict[str, Any] | None:
        """
        Get a secret value from Secrets Manager.

        Args:
            secret_id: The ARN or name of the secret to retrieve
            cache: Whether to cache the secret value locally

        Returns:
            The secret value as a dictionary, or None if not found
        """
        with self.monitor_operation(get_function_name()):
            # Check if circuit is open
            if not self.circuit_breaker.can_execute():
                logger.warning('Circuit breaker open for Secrets Manager')
                return None

            # Check cache first if caching is enabled
            if cache and secret_id in self._cache:
                logger.debug(f'Using cached secret value for {secret_id}')
                return self._cache[secret_id]

            try:
                if self._client is None:
                    await self.initialize()

                if not self._client:
                    raise ValueError('Secrets Manager client not initialized')

                # Get the secret value
                response = self._client.get_secret_value(SecretId=secret_id)

                # Parse the secret value
                if 'SecretString' in response:
                    secret_value = response['SecretString']
                    # Try to parse as JSON, fallback to string if not valid JSON
                    try:
                        secret_data = json.loads(secret_value)
                    except json.JSONDecodeError:
                        secret_data = {'value': secret_value}

                    # Cache the secret value if caching is enabled
                    if cache:
                        self._cache[secret_id] = secret_data

                    return cast(dict[str, Any], secret_data)
                else:
                    logger.warning(f'No SecretString in response for {secret_id}')
                    return None

            except Exception as e:
                logger.error(f'Failed to get secret value for {secret_id}: {e}')
                return None

    async def create_secret(self, name: str, value: dict[str, Any]) -> str | None:
        """
        Create a new secret.

        Args:
            name: The name of the secret
            value: The secret value as a dictionary

        Returns:
            The ARN of the created secret, or None if creation failed
        """
        with self.monitor_operation(get_function_name()):
            # Check if circuit is open
            if not self.circuit_breaker.can_execute():
                logger.warning('Circuit breaker open for Secrets Manager')
                return None

            try:
                if self._client is None:
                    await self.initialize()

                if not self._client:
                    raise ValueError('Secrets Manager client not initialized')

                # Convert dict to JSON string
                secret_string = json.dumps(value)

                # Create the secret
                response = self._client.create_secret(
                    Name=name, SecretString=secret_string
                )

                # Clear cache for this secret if it exists
                if name in self._cache:
                    del self._cache[name]

                return response.get('ARN')

            except Exception as e:
                logger.error(f'Failed to create secret {name}: {e}')
                return None

    async def update_secret(self, secret_id: str, value: dict[str, Any]) -> bool:
        """
        Update an existing secret.

        Args:
            secret_id: The ARN or name of the secret to update
            value: The new secret value as a dictionary

        Returns:
            True if the update was successful, False otherwise
        """
        with self.monitor_operation(get_function_name()):
            # Check if circuit is open
            if not self.circuit_breaker.can_execute():
                logger.warning('Circuit breaker open for Secrets Manager')
                return False

            try:
                if self._client is None:
                    await self.initialize()

                if not self._client:
                    raise ValueError('Secrets Manager client not initialized')

                # Convert dict to JSON string
                secret_string = json.dumps(value)

                # Update the secret
                self._client.update_secret(
                    SecretId=secret_id, SecretString=secret_string
                )

                # Clear cache for this secret if it exists
                if secret_id in self._cache:
                    del self._cache[secret_id]

                return True

            except Exception as e:
                logger.error(f'Failed to update secret {secret_id}: {e}')
                return False

    async def delete_secret(
        self, secret_id: str, recovery_window_in_days: int = 30
    ) -> bool:
        """
        Delete a secret.

        Args:
            secret_id: The ARN or name of the secret to delete
            recovery_window_in_days: The number of days to wait before permanently deleting the secret

        Returns:
            True if the deletion was successful, False otherwise
        """
        with self.monitor_operation(get_function_name()):
            # Check if circuit is open
            if not self.circuit_breaker.can_execute():
                logger.warning('Circuit breaker open for Secrets Manager')
                return False

            try:
                if self._client is None:
                    await self.initialize()

                if not self._client:
                    raise ValueError('Secrets Manager client not initialized')

                # Delete the secret
                self._client.delete_secret(
                    SecretId=secret_id, RecoveryWindowInDays=recovery_window_in_days
                )

                # Clear cache for this secret if it exists
                if secret_id in self._cache:
                    del self._cache[secret_id]

                return True

            except Exception as e:
                logger.error(f'Failed to delete secret {secret_id}: {e}')
                return False
