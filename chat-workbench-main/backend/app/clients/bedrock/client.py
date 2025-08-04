# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from typing import Any

import boto3
from aiobotocore.session import AioSession
from app.clients.base import BaseClient, CircuitOpenError
from app.utils import get_function_name
from loguru import logger


class BedrockClient(BaseClient):
    """Bedrock runtime client with async operations."""

    _client: Any | None = None
    _sync_client: Any | None = None

    async def initialize(self) -> None:
        """Initialize Bedrock runtime client."""
        if not self.circuit_breaker.can_execute():
            self.circuit_breaker.record_failure()
            raise CircuitOpenError('Circuit breaker is open')

        with self.monitor_operation(get_function_name()):
            # Initialize async client
            session = AioSession()
            self._client = await session.create_client(
                'bedrock',
                region_name=self.settings.aws.region,
                endpoint_url=self.settings.aws.endpoint_url,
                config=self.settings.aws.get_boto_config('bedrock'),
            ).__aenter__()

            logger.info('Bedrock runtime client initialized')

    async def cleanup(self) -> None:
        """Cleanup Bedrock runtime client."""
        if self._client:
            with self.monitor_operation(get_function_name()):
                await self._client.__aexit__(None, None, None)
                logger.info('Bedrock runtime client closed')

    async def get_sync_client(self) -> Any:
        """Get synchronous client for libraries that don't support async."""
        if not self._sync_client:
            with self.monitor_operation(get_function_name()):
                self._sync_client = boto3.client(
                    'bedrock',
                    region_name=self.settings.aws.region,
                    endpoint_url=self.settings.aws.endpoint_url,
                    config=self.settings.aws.get_boto_config('bedrock'),
                )
                logger.info('Bedrock runtime sync client initialized')
        return self._sync_client

    async def list_guardrails(self) -> list[dict[str, Any]]:
        """List all guardrails.

        Returns:
            List of guardrail metadata objects.
        """
        with self.monitor_operation(get_function_name()):
            try:
                if self._client is None:
                    logger.error('Bedrock client not initialized')
                    return []
                response = await self._client.list_guardrails()
                # According to AWS docs, the response field is 'guardrails' not 'guardrailSummaries'
                return response.get('guardrails', [])
            except Exception as e:
                logger.error(f'Error listing guardrails: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def get_guardrail(
        self, guardrail_id: str, guardrail_version: str | None = None
    ) -> dict[str, Any]:
        """Get guardrail details.

        Args:
            guardrail_id: The ID of the guardrail to retrieve.
            guardrail_version: The version of the guardrail to retrieve. If not specified, returns DRAFT version.

        Returns:
            Guardrail details.
        """
        with self.monitor_operation(get_function_name()):
            try:
                if self._client is None:
                    logger.error('Bedrock client not initialized')
                    return {}

                params = {'guardrailIdentifier': guardrail_id}

                if guardrail_version is not None:
                    params['guardrailVersion'] = guardrail_version

                response = await self._client.get_guardrail(**params)
                return response
            except Exception as e:
                logger.error(f'Error getting guardrail {guardrail_id}: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def create_guardrail(self, config: dict[str, Any]) -> dict[str, Any]:
        """Create a new guardrail.

        Args:
            config: Guardrail configuration.

        Returns:
            Created guardrail details.
        """
        with self.monitor_operation(get_function_name()):
            try:
                if self._client is None:
                    logger.error('Bedrock client not initialized')
                    return {}

                response = await self._client.create_guardrail(**config)
                return {
                    'guardrailId': response.get('guardrailId'),
                    'guardrailArn': response.get('guardrailArn'),
                    'version': response.get('version'),
                    'createdAt': response.get('createdAt'),
                }
            except Exception as e:
                logger.error(f'Error creating guardrail: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def update_guardrail(
        self, guardrail_id: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing guardrail.

        Args:
            guardrail_id: The ID of the guardrail to update.
            config: Updated guardrail configuration including name, description, policy configs, etc.

        Returns:
            Updated guardrail details.
        """
        with self.monitor_operation(get_function_name()):
            try:
                if self._client is None:
                    logger.error('Bedrock client not initialized')
                    return {}

                params = {'guardrailIdentifier': guardrail_id}
                params.update(config)

                response = await self._client.update_guardrail(**params)
                return {
                    'guardrailId': response.get('guardrailId'),
                    'guardrailArn': response.get('guardrailArn'),
                    'version': response.get('version'),
                    'updatedAt': response.get('updatedAt'),
                }
            except Exception as e:
                logger.error(f'Error updating guardrail {guardrail_id}: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def delete_guardrail(self, guardrail_id: str) -> None:
        """Delete a guardrail.

        Args:
            guardrail_id: The ID of the guardrail to delete.
        """
        with self.monitor_operation(get_function_name()):
            try:
                if self._client is None:
                    logger.error('Bedrock client not initialized')
                    return

                await self._client.delete_guardrail(guardrailIdentifier=guardrail_id)
            except Exception as e:
                logger.error(f'Error deleting guardrail {guardrail_id}: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def list_guardrail_versions(self, guardrail_id: str) -> list[dict[str, Any]]:
        """List all versions of a guardrail.

        Args:
            guardrail_id: The ID of the guardrail.

        Returns:
            List of guardrail version metadata.
        """
        with self.monitor_operation(get_function_name()):
            try:
                if self._client is None:
                    logger.error('Bedrock client not initialized')
                    return []

                # According to AWS docs, to list versions we use list_guardrails with the guardrailIdentifier
                response = await self._client.list_guardrails(
                    guardrailIdentifier=guardrail_id
                )
                # Format the response to match expected output
                return [
                    {
                        'version': guardrail.get('version'),
                        'createdAt': guardrail.get('createdAt'),
                    }
                    for guardrail in response.get('guardrails', [])
                ]
            except Exception as e:
                logger.error(
                    f'Error listing guardrail versions for {guardrail_id}: {e}'
                )
                self.circuit_breaker.record_failure()
                raise

    async def publish_guardrail(
        self, guardrail_id: str, description: str | None = None
    ) -> dict[str, Any]:
        """Publish a guardrail draft as a new version.

        Args:
            guardrail_id: The ID of the guardrail to publish.
            description: Optional description for the version.

        Returns:
            Published guardrail version details.
        """
        with self.monitor_operation(get_function_name()):
            try:
                if self._client is None:
                    logger.error('Bedrock client not initialized')
                    return {}

                params = {'guardrailIdentifier': guardrail_id}

                if description is not None:
                    params['description'] = description

                response = await self._client.create_guardrail_version(**params)
                # The response from create_guardrail_version only has guardrailId and version
                return {
                    'guardrailId': response.get('guardrailId'),
                    'version': response.get('version'),
                }
            except Exception as e:
                logger.error(f'Error publishing guardrail {guardrail_id}: {e}')
                self.circuit_breaker.record_failure()
                raise
