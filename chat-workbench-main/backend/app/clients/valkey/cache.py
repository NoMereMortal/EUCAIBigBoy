# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Valkey cache client implementation."""

import json
from typing import Any, Optional

import valkey.asyncio as valkey
from loguru import logger

from app.clients.base import BaseClient, CircuitOpenError
from app.utils import get_function_name


class ValkeyCache(BaseClient):
    """Valkey cache client with async operations."""

    _client: Optional[valkey.Valkey] = None

    async def initialize(self) -> None:
        """Initialize Valkey cache client."""
        if not self.circuit_breaker.can_execute():
            self.circuit_breaker.record_failure()
            logger.error('Cannot initialize Valkey client: Circuit breaker is open')
            raise CircuitOpenError('Circuit breaker is open')

        with self.monitor_operation(get_function_name()):
            try:
                # Get Redis/Valkey config from settings
                redis_config = self.settings.valkey

                logger.info(
                    f'Initializing Valkey client with host: {redis_config.host}:{redis_config.port}'
                )

                # Connect to Valkey server with explicit parameters
                host = redis_config.host
                port = redis_config.port
                db = getattr(redis_config, 'db', 0)

                # Initialize with required parameters only
                self._client = valkey.Valkey(
                    host=host, port=port, db=db, decode_responses=False
                )

                logger.info(f'Connected to Valkey at {host}:{port}, db={db}')

                # Test connection
                await self._client.ping()
                logger.info('Valkey client successfully initialized')
            except Exception as e:
                logger.error(f'Failed to initialize Valkey client: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def cleanup(self) -> None:
        """Cleanup Valkey client."""
        if self._client:
            with self.monitor_operation(get_function_name()):
                if self._client:
                    await self._client.aclose()
                logger.info('Valkey client closed')

    async def get(self, key: str) -> Optional[str]:
        """Get a value from the cache."""
        if not self._client:
            logger.error('Cannot get from cache: Valkey client not initialized')
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                value = None
                if self._client:
                    value = await self._client.get(key)
                if value is not None and isinstance(value, bytes):
                    return value.decode('utf-8')
                return None
            except Exception as e:
                logger.error(f'Failed to get from cache: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set a value in the cache."""
        if not self._client:
            logger.error('Cannot set in cache: Valkey client not initialized')
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                if self._client:
                    if ttl:
                        return await self._client.setex(key, ttl, value)
                    else:
                        return await self._client.set(key, value)
                return False
            except Exception as e:
                logger.error(f'Failed to set in cache: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def delete(self, key: str) -> int:
        """Delete a value from the cache."""
        if not self._client:
            logger.error('Cannot delete from cache: Valkey client not initialized')
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                if self._client:
                    return await self._client.delete(key)
                return 0
            except Exception as e:
                logger.error('Failed to delete from cache: {}', str(e))
                self.circuit_breaker.record_failure()
                raise

    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        if not self._client:
            logger.error(
                'Cannot check existence in cache: Valkey client not initialized'
            )
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                if self._client:
                    return bool(await self._client.exists(key))
                return False
            except Exception as e:
                logger.error(f'Failed to check existence in cache: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for a key."""
        if not self._client:
            logger.error('Cannot set expiry: Valkey client not initialized')
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                if self._client:
                    return bool(await self._client.expire(key, ttl))
                return False
            except Exception as e:
                logger.error(f'Failed to set expiry: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def flush(self) -> bool:
        """Clear all cache entries."""
        if not self._client:
            logger.error('Cannot flush cache: Valkey client not initialized')
            raise ValueError('Valkey client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                if self._client:
                    return bool(await self._client.flushdb())
                return False
            except Exception as e:
                logger.error(f'Failed to flush cache: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def cache_object(self, key: str, obj: Any, ttl: Optional[int] = None) -> bool:
        """Cache an object as JSON."""
        try:
            json_str = json.dumps(obj)
            return await self.set(key, json_str, ttl)
        except (TypeError, ValueError) as e:
            logger.error(f'Failed to serialize object for cache: {e}')
            return False

    async def get_cached_object(self, key: str) -> Optional[Any]:
        """Get a cached object from JSON."""
        json_str = await self.get(key)
        if not json_str:
            return None

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse cached JSON: {e}')
            return None
