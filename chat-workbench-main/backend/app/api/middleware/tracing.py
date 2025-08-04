# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tracing middleware."""

import uuid
from collections.abc import Callable

from fastapi import Request, Response  # type: ignore
from starlette.middleware.base import BaseHTTPMiddleware  # type: ignore


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware for distributed tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and add tracing headers."""
        # In a real implementation, this would integrate with a tracing system
        # like AWS X-Ray, Jaeger, or Zipkin

        # For now, we'll just add a trace ID header
        trace_id = request.headers.get('X-Trace-ID', str(uuid.uuid4()))

        # Process request
        response = await call_next(request)

        # Add trace ID to response
        response.headers['X-Trace-ID'] = trace_id

        return response
