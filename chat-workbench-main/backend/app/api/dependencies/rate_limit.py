# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Rate limiting dependencies for FastAPI routes."""

import time
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from loguru import logger


async def get_rate_limiter(request: Request) -> dict[str, Any] | None:
    """Get rate limiter configuration from app state."""
    app = request.app
    registry = app.state.client_registry

    valkey_client = registry.get_client('valkey')
    if (
        not valkey_client
        or not hasattr(valkey_client, '_client')
        or not valkey_client._client
    ):
        return None

    return {
        'client': valkey_client,
        'rate_limit': getattr(app.state, 'rate_limit', 100),
        'window_size': getattr(app.state, 'rate_limit_window', 60),
    }


async def check_rate_limit(
    request: Request,
    rate_limiter: dict[str, Any] | None = Depends(get_rate_limiter),
) -> None:
    """
    Check if the request exceeds rate limits.

    This dependency can be used in route handlers to implement rate limiting.
    """
    if (
        not rate_limiter
        or not rate_limiter['client']
        or not rate_limiter['client']._client
    ):
        return

    valkey_client = rate_limiter['client']
    rate_limit = rate_limiter['rate_limit']
    window_size = rate_limiter['window_size']

    # Get client identifier (IP address or API key)
    client_id = request.client.host if request.client else 'unknown'

    # Use API key from header if available
    api_key = request.headers.get('X-API-Key')
    if api_key:
        client_id = f'api:{api_key}'

    # Create rate limit key
    rate_limit_key = f'rate_limit:{client_id}'

    try:
        # Get current time
        current_time = int(time.time())
        window_start = current_time - window_size

        # Use pipeline for atomic operations
        async with valkey_client._client.pipeline(transaction=True) as pipe:
            # Remove old timestamps
            await pipe.zremrangebyscore(rate_limit_key, 0, window_start)
            # Count requests in current window
            await pipe.zcard(rate_limit_key)
            # Add current timestamp
            await pipe.zadd(rate_limit_key, {str(current_time): current_time})
            # Set expiration
            await pipe.expire(rate_limit_key, window_size * 2)
            # Execute pipeline
            results = await pipe.execute()

        # Get count from results
        count = results[1]

        # Check if rate limit exceeded
        if count > rate_limit:
            logger.warning(f'Rate limit exceeded for {client_id}: {count} requests')
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail='Rate limit exceeded',
                headers={'Retry-After': str(window_size)},
            )
    except Exception as e:
        if not isinstance(e, HTTPException):
            logger.error(f'Error checking rate limit: {e}')
            # Allow the request if there's an error checking the rate limit
