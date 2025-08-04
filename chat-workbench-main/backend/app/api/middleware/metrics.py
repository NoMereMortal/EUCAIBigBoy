# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Metrics middleware."""

import time
from collections.abc import Callable
from contextlib import suppress

import prometheus_client as prom  # type: ignore
from fastapi import Request, Response  # type: ignore
from starlette.middleware.base import BaseHTTPMiddleware  # type: ignore

# Prometheus metrics
REQUEST_COUNT = prom.Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code', 'route'],
)

REQUEST_LATENCY = prom.Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint', 'route'],
    buckets=[
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        7.5,
        10.0,
        30.0,
        60.0,
        float('inf'),
    ],
)

REQUEST_SIZE = prom.Histogram(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
    buckets=[100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000, float('inf')],
)

RESPONSE_SIZE = prom.Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint', 'status_code'],
    buckets=[100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000, float('inf')],
)

REQUEST_IN_PROGRESS = prom.Gauge(
    'http_requests_in_progress',
    'HTTP requests currently in progress',
    ['method', 'endpoint'],
)

# Status code metrics
STATUS_4XX_COUNT = prom.Counter(
    'http_4xx_errors_total',
    'Total HTTP 4xx errors',
    ['method', 'endpoint', 'status_code'],
)

STATUS_5XX_COUNT = prom.Counter(
    'http_5xx_errors_total',
    'Total HTTP 5xx errors',
    ['method', 'endpoint', 'status_code'],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting request metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and collect metrics."""
        method = request.method
        endpoint = request.url.path

        # Get route name if available (more stable than raw path)
        route = getattr(request.scope.get('route'), 'name', None) or 'unknown'

        # Track in-progress requests
        REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()

        # Track request size if content-length is available
        content_length = request.headers.get('content-length')
        if content_length:
            with suppress(ValueError, TypeError):
                REQUEST_SIZE.labels(method=method, endpoint=endpoint).observe(
                    int(content_length)
                )

        # Track request latency
        start_time = time.time()
        response = None

        try:
            # Get response
            response = await call_next(request)

            # Record metrics
            duration = time.time() - start_time
            status_code = response.status_code

            # Track basic request metrics
            REQUEST_COUNT.labels(
                method=method, endpoint=endpoint, status_code=status_code, route=route
            ).inc()

            REQUEST_LATENCY.labels(
                method=method, endpoint=endpoint, route=route
            ).observe(duration)

            # Track response size if content-length is available
            resp_content_length = response.headers.get('content-length')
            if resp_content_length:
                with suppress(ValueError, TypeError):
                    RESPONSE_SIZE.labels(
                        method=method, endpoint=endpoint, status_code=status_code
                    ).observe(int(resp_content_length))

            # Track error status codes
            if 400 <= status_code < 500:
                STATUS_4XX_COUNT.labels(
                    method=method, endpoint=endpoint, status_code=status_code
                ).inc()
            elif status_code >= 500:
                STATUS_5XX_COUNT.labels(
                    method=method, endpoint=endpoint, status_code=status_code
                ).inc()

        except Exception as e:
            # Re-raise the exception after cleanup
            raise e
        finally:
            # Ensure we always decrement in-progress counter
            REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()

        # Ensure we always return a response or re-raise any exception
        if response is not None:
            return response

        # This line should never be reached but is here to satisfy the type checker
        # that all code paths return a Response
        raise RuntimeError('Unexpected code path: No response was generated')
