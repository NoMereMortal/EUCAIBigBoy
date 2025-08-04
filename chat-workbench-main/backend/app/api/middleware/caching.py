# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Caching middleware."""

import hashlib
import json
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from app.clients.valkey.cache import ValkeyCache  # type: ignore


class CachingMiddleware(BaseHTTPMiddleware):
    """Middleware for caching responses."""

    def __init__(
        self,
        app: Any,
        cache: ValkeyCache,
        ttl: int = 300,
        cache_methods: list[str] | None = None,
        exclude_paths: list[str] | None = None,
    ):
        """Initialize caching middleware."""
        super().__init__(app)
        self.cache = cache
        self.ttl = ttl
        self.cache_methods = cache_methods or ['GET']
        self.exclude_paths = exclude_paths or ['/api/health', '/api/metrics']

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and apply caching."""
        # Skip caching for non-cacheable methods or excluded paths
        if request.method not in self.cache_methods:
            return await call_next(request)

        for path in self.exclude_paths:
            if request.url.path.startswith(path):
                return await call_next(request)

        # Generate cache key
        cache_key = self._generate_cache_key(request)

        # Try to get from cache
        cached_response = await self.cache.get(cache_key)
        if cached_response:
            try:
                cached_data = json.loads(cached_response)
                return Response(
                    content=cached_data['content'],
                    status_code=cached_data['status_code'],
                    headers=cached_data['headers'],
                    media_type=cached_data['media_type'],
                )
            except Exception as e:
                logger.error(f'Failed to parse cached response: {e}')

        # Get fresh response
        response = await call_next(request)

        # Cache the response if it's successful
        if 200 <= response.status_code < 400:
            try:
                # Get response content
                response_body = [section async for section in response.body_iterator]
                response.body_iterator = iter(response_body)
                content = b''.join(response_body)

                # Prepare data for caching
                cache_data = {
                    'content': content.decode('utf-8'),
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'media_type': response.media_type,
                }

                # Store in cache
                await self.cache.set(cache_key, json.dumps(cache_data), ttl=self.ttl)
            except Exception as e:
                logger.error(f'Failed to cache response: {e}')

        return response

    def _generate_cache_key(self, request: Request) -> str:
        """Generate a cache key for the request."""
        # Create a unique key based on path, query params, and headers
        key_parts = [
            request.url.path,
            str(sorted(request.query_params.items())),
        ]

        # Add selected headers that might affect the response
        for header in ['accept', 'accept-encoding', 'accept-language']:
            if header in request.headers:
                key_parts.append(f'{header}:{request.headers[header]}')

        # Create a hash of the key parts
        key_string = ':'.join(key_parts)
        # Use SHA-256 instead of MD5 for better security
        return f'cache:{hashlib.sha256(key_string.encode()).hexdigest()}'
