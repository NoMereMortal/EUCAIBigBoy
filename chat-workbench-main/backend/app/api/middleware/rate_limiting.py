# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Rate limiting middleware using Valkey."""

from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests using Valkey."""

    def __init__(
        self,
        app: Any,
        rate_limit: int = 100,  # requests per minute
        window_size: int = 60,  # seconds
        prefix: str = 'rate_limit:',
        fail_closed: bool = False,  # Whether to fail closed (reject requests) on errors
        enabled: bool = True,  # Whether rate limiting is enabled
        exclude_paths: list[str] | None = None,  # Paths to exclude from rate limiting
    ) -> None:
        """Initialize rate limiting middleware."""
        super().__init__(app)
        # Only store configuration values, not client references
        self.rate_limit = rate_limit
        self.window_size = window_size
        self.prefix = prefix
        self.fail_closed = fail_closed
        self.enabled = enabled
        # Default excluded paths for operational endpoints
        self.exclude_paths = exclude_paths or [
            '/api/health',
            '/api/metrics',
            '/api/docs',
            '/api/redoc',
            '/api/openapi.json',
        ]

        # Log initialization state for debugging
        if self.enabled:
            logger.info('Rate limiting middleware registered with configuration')

    def _should_exclude_path(self, request_path: str) -> bool:
        """Check if request path should be excluded from rate limiting."""
        for excluded_path in self.exclude_paths:
            if request_path == excluded_path or request_path.startswith(excluded_path):
                return True
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and apply rate limiting."""
        # Get configuration directly from the instance (never from cached config)
        enabled = self.enabled
        rate_limit = self.rate_limit
        window_size = self.window_size

        # Skip rate limiting if not enabled at the middleware level
        if not enabled:
            logger.debug('Rate limiting disabled in middleware configuration')
            return await call_next(request)

        # ALWAYS get the client directly from app state - never from config dictionary
        valkey_client = getattr(request.app.state, 'valkey_client', None)

        # Skip rate limiting if client not available - log a clear error
        if valkey_client is None:
            logger.error(
                'Rate limiting disabled: Valkey client not available in app state'
            )
            return await call_next(request)

        # Validate client has the required methods before attempting to use it
        if not hasattr(valkey_client, 'pipeline'):
            logger.error(
                'Rate limiting disabled: Valkey client found but missing pipeline method'
            )
            return await call_next(request)

        # Check if this path should be excluded from rate limiting
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else 'unknown'

        # Get user ID from request state if available, or use anonymous
        user_id = getattr(request.state, 'user_id', 'anonymous')
        # Generate a request ID if not available
        request_id = getattr(request.state, 'request_id', 'req_' + str(id(request)))

        # Create rate limit keys with hash tags to ensure they hash to the same slot
        # The portion inside {curly braces} will be used for hash calculation
        common_id = f'{client_ip}:{user_id}'
        ip_key = f'{self.prefix}{{rate_limit}}:ip:{common_id}'
        user_key = f'{self.prefix}{{rate_limit}}:user:{common_id}'

        try:
            # Check rate limits using pipeline for efficiency
            # Use pipeline same as content_storage.py - no context manager needed
            pipe = valkey_client.pipeline()

            # Increment counters
            await pipe.incr(ip_key)
            await pipe.incr(user_key)

            # Set expiration if not already set
            await pipe.expire(ip_key, window_size)
            await pipe.expire(user_key, window_size)

            # Get current counts
            results = await pipe.execute()
            ip_count, user_count = results[0], results[1]

            # Check if either limit is exceeded
            if ip_count > rate_limit or user_count > rate_limit:
                logger.warning(
                    f'Rate limit exceeded: IP={client_ip} ({ip_count}/{rate_limit}), '
                    f'User={user_id} ({user_count}/{rate_limit})'
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        'detail': 'Too many requests',
                        'request_id': request_id,
                    },
                )
        except ConnectionError as e:
            # Handle connection errors
            logger.warning(f'Rate limiting service unavailable: {e}')
            # Continue processing the request
            if self.fail_closed:
                return JSONResponse(
                    status_code=503,
                    content={
                        'detail': 'Rate limiting service unavailable',
                        'request_id': request_id,
                    },
                )
            return await call_next(request)
        except Exception as e:
            # Log unexpected errors
            logger.error(f'Unexpected rate limiting error: {e}', exc_info=True)
            # Continue processing the request despite errors or fail based on configuration
            if self.fail_closed:
                return JSONResponse(
                    status_code=500,
                    content={
                        'detail': 'Rate limiting error',
                        'request_id': request_id,
                    },
                )
            return await call_next(request)

        # Process request
        return await call_next(request)
