# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from typing import Any

import boto3
from aiobotocore.session import AioSession
from loguru import logger

from app.clients.base import BaseClient, CircuitOpenError
from app.utils import get_function_name


class BedrockRuntimeClient(BaseClient):
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
                'bedrock-runtime',
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
                    'bedrock-runtime',
                    region_name=self.settings.aws.region,
                    endpoint_url=self.settings.aws.endpoint_url,
                    config=self.settings.aws.get_boto_config('bedrock'),
                )
                logger.info('Bedrock runtime sync client initialized')
        return self._sync_client
