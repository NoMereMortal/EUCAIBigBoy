# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Logging middleware."""

import time
from collections.abc import Callable

from fastapi import Request, Response  # type: ignore
from loguru import logger  # type: ignore
from starlette.middleware.base import BaseHTTPMiddleware  # type: ignore

from .context import RequestContext


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log details."""
        start_time = time.time()

        # Extract request details
        method = request.method
        url = str(request.url)
        client_host = request.client.host if request.client else 'unknown'
        state = RequestContext.get_state()
        request_id = state.request_id or 'unknown'

        # Skip logging for metrics endpoint to avoid duplicate logs
        # Prometheus scrapes metrics frequently, causing log spam
        if not url.endswith('/api/metrics'):
            logger.info(
                f'Request started: {method} {url} from {client_host} [request_id={request_id}]'
            )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Skip logging for metrics endpoint to avoid duplicate logs
        if not url.endswith('/api/metrics'):
            logger.info(
                f'Request completed: {method} {url} from {client_host} '
                f'[request_id={request_id}, status={response.status_code}, duration={duration:.3f}s]'
            )

        return response
