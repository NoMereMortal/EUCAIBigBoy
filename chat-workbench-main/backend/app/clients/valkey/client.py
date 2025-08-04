# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Valkey client implementation."""

from collections.abc import Awaitable
from typing import Any, cast

import valkey.asyncio as valkey  # type: ignore
from loguru import logger  # type: ignore

from app.clients.base import BaseClient, CircuitOpenError
from app.utils import get_function_name


class ValkeyClient(BaseClient):
    """Valkey client with async operations."""

    _client: valkey.Valkey | None = None
    _pool: valkey.ConnectionPool | None = None
    _binary_pool: valkey.ConnectionPool | None = None
    _binary_client: valkey.Valkey | None = None

    async def initialize(self) -> None:
        """Initialize Valkey client."""
        if not self.circuit_breaker.can_execute():
            self.circuit_breaker.record_failure()
            raise CircuitOpenError('Circuit breaker is open')

        with self.monitor_operation(get_function_name()):
            try:
                # Get configuration
                host = self.settings.get_valkey_config().host
                port = self.settings.get_valkey_config().port
                db = self.settings.get_valkey_config().db
                use_tls = self.settings.get_valkey_config().use_tls

                # Choose scheme based on TLS setting
                scheme = 'valkeys' if use_tls else 'valkey'
                url = f'{scheme}://{host}:{port}/{db}'
                self._pool = valkey.ConnectionPool.from_url(
                    url,
                    decode_responses=True,  # Auto-decode responses to strings
                    protocol=3,  # Use RESP3 protocol
                    max_connections=100,  # Increased from 50 to handle more concurrent requests
                    socket_timeout=30.0,  # Increased from 15s to 30s for cloud-based Redis
                    socket_connect_timeout=20.0,  # Increased from 10s to 20s
                    socket_keepalive=True,  # Keep connections alive
                    retry_on_timeout=True,  # Retry operations on timeout
                    health_check_interval=30,  # Perform health checks every 30 seconds
                )

                self._binary_pool = valkey.ConnectionPool.from_url(
                    url,
                    decode_responses=False,  # Do NOT decode binary responses
                    protocol=3,  # Use RESP3 protocol
                    max_connections=100,  # Increased from 50
                    socket_timeout=30.0,  # Increased from 15s to 30s
                    socket_connect_timeout=20.0,  # Increased from 10s to 20s
                    socket_keepalive=True,  # Keep connections alive
                    retry_on_timeout=True,  # Retry operations on timeout
                    health_check_interval=30,  # Perform health checks
                )

                # Create clients from pools
                self._client = valkey.Valkey.from_pool(self._pool)
                self._binary_client = valkey.Valkey.from_pool(self._binary_pool)

                # Test connection
                try:
                    await self._client.ping()
                    logger.info('Successfully connected to Valkey/Redis')
                except Exception as e:
                    logger.error(f'Ping failed. Connection error details: {e}')
                    logger.error(
                        f'Host: {self.settings.get_valkey_config().host}, '
                        f'Port: {self.settings.get_valkey_config().port}'
                    )
                    raise

                logger.info('Valkey client initialized')
                # Success will be recorded by OperationMonitor.__exit__
            except Exception as e:
                logger.error(f'Failed to initialize Valkey client: {e}')
                # Failure will be recorded by OperationMonitor.__exit__
                raise

    async def cleanup(self) -> None:
        """Cleanup Valkey client."""
        with self.monitor_operation(get_function_name()):
            try:
                if self._client:
                    await self._client.aclose()
                if self._binary_client:
                    await self._binary_client.aclose()
                logger.info('Valkey clients closed')
            except Exception as e:
                logger.error(f'Error closing Valkey clients: {e}')

    async def get(self, key: str) -> str | None:
        """Get a value by key."""
        if not self._client:
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                value = await self._client.get(key)
                return value
            except Exception as e:
                logger.error(f'Failed to get key {key}: {e}')
                raise

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """Set a key-value pair with optional expiration."""
        if not self._client:
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                # Use default TTL from settings if not specified
                if ex is None and self.settings.get_valkey_config().ttl > 0:
                    ex = self.settings.get_valkey_config().ttl

                result = await self._client.set(
                    key,
                    value,
                    ex=ex,
                    nx=nx,
                    xx=xx,
                )
                return result == 'OK'
            except Exception as e:
                logger.error(f'Failed to set key {key}: {e}')
                raise

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        if not self._client:
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                result = await self._client.delete(*keys)
                return result
            except Exception as e:
                logger.error(f'Failed to delete keys {keys}: {e}')
                raise

    async def exists(self, *keys: str) -> int:
        """Check if keys exist."""
        if not self._client:
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                result = await self._client.exists(*keys)
                return result
            except Exception as e:
                logger.error(f'Failed to check existence of keys {keys}: {e}')
                raise

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key."""
        if not self._client:
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                result = await self._client.expire(key, seconds)
                return bool(result)
            except Exception as e:
                logger.error(f'Failed to set expiration for key {key}: {e}')
                raise

    async def ttl(self, key: str) -> int:
        """Get time to live for a key."""
        if not self._client:
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                result = await self._client.ttl(key)
                return int(result)
            except Exception as e:
                logger.error(f'Failed to get TTL for key {key}: {e}')
                raise

    async def hset(self, name: str, mapping: dict[str, Any]) -> int:
        """Set multiple hash fields to multiple values."""
        if not self._client:
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                result = self._client.hset(name, mapping=mapping)
                if hasattr(result, '__await__'):
                    result = await cast(Awaitable[int], result)
                else:
                    result = cast(int, result)
                return int(result)
            except Exception as e:
                logger.error(f'Failed to set hash fields for {name}: {e}')
                raise

    async def hget(self, name: str, key: str) -> str | None:
        """Get the value of a hash field."""
        if not self._client:
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                result = self._client.hget(name, key)
                if hasattr(result, '__await__'):
                    result = await cast(Awaitable[str | None], result)
                else:
                    result = cast(str | None, result)
                return result
            except Exception as e:
                logger.error(f'Failed to get hash field {key} from {name}: {e}')
                raise

    async def hgetall(self, name: str) -> dict[str, str]:
        """Get all fields and values in a hash."""
        if not self._client:
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                result = self._client.hgetall(name)
                if hasattr(result, '__await__'):
                    result = await cast(Awaitable[dict[str, str]], result)
                else:
                    result = cast(dict[str, str], result)
                return dict(result)
            except Exception as e:
                logger.error(f'Failed to get all hash fields from {name}: {e}')
                raise

    def pipeline(self, transaction: bool = True) -> 'valkey.client.Pipeline':
        """Create a pipeline for executing multiple commands atomically."""
        if not self._client:
            raise ValueError('Valkey client not initialized')

        return self._client.pipeline(transaction=transaction)

    async def pubsub(self) -> valkey.client.PubSub:
        """Create a pubsub object for subscribing to channels."""
        if not self._client:
            raise ValueError('Valkey client not initialized')

        return self._client.pubsub()

    async def get_binary(self, key: str) -> bytes | None:
        """Get a binary value by key without UTF-8 decoding."""
        if not self._binary_client:
            raise ValueError('Binary Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                value = await self._binary_client.get(key)
                return value
            except Exception as e:
                logger.error(f'Failed to get binary key {key}: {e}')
                raise

    async def set_binary(
        self,
        key: str,
        value: bytes,
        ex: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """Set a binary key-value pair with optional expiration."""
        if not self._binary_client:
            raise ValueError('Binary Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                # Use default TTL from settings if not specified
                if ex is None and self.settings.get_valkey_config().ttl > 0:
                    ex = self.settings.get_valkey_config().ttl

                result = await self._binary_client.set(
                    key,
                    value,
                    ex=ex,
                    nx=nx,
                    xx=xx,
                )
                return result == b'OK'
            except Exception as e:
                logger.error(f'Failed to set binary key {key}: {e}')
                raise
