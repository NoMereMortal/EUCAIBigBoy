# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Monitoring utilities for the application."""

import time
from contextlib import contextmanager
from typing import Any

import prometheus_client as prom  # type: ignore
from loguru import logger  # type: ignore

# Define Prometheus metrics
OPERATION_LATENCY = prom.Histogram(
    'operation_duration_seconds',
    'Operation duration in seconds',
    ['service', 'operation', 'success'],
)

OPERATION_COUNT = prom.Counter(
    'operation_total', 'Total operations', ['service', 'operation', 'success']
)

# Client metrics
CLIENT_REQUEST_COUNT = prom.Counter(
    'client_requests_total', 'Total client requests', ['client', 'operation', 'status']
)

CLIENT_REQUEST_LATENCY = prom.Histogram(
    'client_latency_seconds',
    'Client request latency in seconds',
    ['client', 'operation'],
)

CLIENT_ERRORS = prom.Counter(
    'client_errors_total', 'Total client errors', ['client', 'operation', 'error_type']
)

# Circuit breaker metrics
CIRCUIT_BREAKER_STATE = prom.Gauge(
    'circuit_breaker_state', 'Circuit breaker state (1=closed, 0=open)', ['client']
)

# Chat metrics
CHAT_MESSAGE_COUNT = prom.Counter(
    'chat_messages_total', 'Total chat messages', ['direction', 'model']
)

CHAT_TOKEN_COUNT = prom.Counter(
    'chat_tokens_total', 'Total tokens in chat messages', ['direction', 'model']
)

CHAT_LATENCY = prom.Histogram(
    'chat_response_seconds', 'Chat response time in seconds', ['model']
)

# LLM usage metrics
LLM_TOKEN_USAGE = prom.Counter(
    'llm_tokens_total',
    'Total tokens used by LLM models',
    ['model', 'token_type'],  # token_type: prompt, completion, total
)

LLM_REQUEST_COUNT = prom.Counter(
    'llm_requests_total',
    'Total LLM API requests',
    ['model', 'status'],  # status: success, error
)

LLM_REQUEST_LATENCY = prom.Histogram(
    'llm_request_duration_seconds',
    'LLM request duration in seconds',
    ['model'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, float('inf')],
)

LLM_ERROR_COUNT = prom.Counter(
    'llm_errors_total',
    'Total LLM API errors',
    ['model', 'error_type'],
)

# Cost metrics (if pricing data is available)
LLM_COST = prom.Counter(
    'llm_cost_total',
    'Estimated cost of LLM API usage in USD',
    ['model'],
)

# Rate limiting metrics
LLM_RATE_LIMIT_REMAINING = prom.Gauge(
    'llm_rate_limit_remaining',
    'Remaining requests before rate limit is hit',
    ['model'],
)

# Context server metrics
CONTEXT_SERVER_QUERY_COUNT = prom.Counter(
    'context_server_queries_total',
    'Total context server queries',
    ['server', 'operation'],
)

CONTEXT_SERVER_LATENCY = prom.Histogram(
    'context_server_latency_seconds',
    'Context server latency in seconds',
    ['server', 'operation'],
)

CONTEXT_SERVER_ERROR_COUNT = prom.Counter(
    'context_server_errors_total',
    'Total context server errors',
    ['server', 'operation', 'error_type'],
)


class OperationMonitor:
    """Monitor for tracking operation metrics."""

    def __init__(self, service_name: str) -> None:
        """Initialize operation monitor."""
        self.service_name = service_name

    @contextmanager
    def operation(
        self, operation_name: str, extra_labels: dict[str, str] | None = None
    ) -> Any:
        """Context manager for monitoring an operation."""
        start_time = time.time()
        success = False

        try:
            yield
            success = True
        finally:
            duration = time.time() - start_time
            self._record_metrics(operation_name, duration, success, extra_labels)

    def _record_metrics(
        self,
        operation_name: str,
        duration: float,
        success: bool,
        extra_labels: dict[str, str] | None = None,
    ) -> None:
        """Record metrics for the operation."""
        labels = {
            'service': self.service_name,
            'operation': operation_name,
            'success': str(success).lower(),
        }

        if extra_labels:
            labels.update(extra_labels)

        # Record metrics in Prometheus
        OPERATION_LATENCY.labels(
            service=self.service_name,
            operation=operation_name,
            success=str(success).lower(),
        ).observe(duration)

        OPERATION_COUNT.labels(
            service=self.service_name,
            operation=operation_name,
            success=str(success).lower(),
        ).inc()

        # Log the metrics for debugging
        label_str = ', '.join(f'{k}={v}' for k, v in labels.items())
        logger.debug(f'Operation metrics: {label_str}, duration={duration:.3f}s')


def track_client_request(
    client: str, operation: str, status: str, duration: float
) -> None:
    """Track a client request."""
    logger.debug(
        f'TRACKING CLIENT REQUEST: {client=}, {operation=}, {status=}, {duration=}'
    )
    CLIENT_REQUEST_COUNT.labels(client=client, operation=operation, status=status).inc()
    CLIENT_REQUEST_LATENCY.labels(client=client, operation=operation).observe(duration)


def track_client_error(client: str, operation: str, error_type: str) -> None:
    """Track a client error."""
    logger.debug(f'TRACKING CLIENT ERROR: {client=}, {operation=}, {error_type=}')
    CLIENT_ERRORS.labels(
        client=client, operation=operation, error_type=error_type
    ).inc()


def set_circuit_breaker_state(client: str, is_closed: bool) -> None:
    """Set the circuit breaker state."""
    logger.debug(f'SETTING CIRCUIT BREAKER STATE: {client=}, {is_closed=}')
    CIRCUIT_BREAKER_STATE.labels(client=client).set(1.0 if is_closed else 0.0)


def track_chat_message(direction: str, model: str, tokens: int) -> None:
    """Track a chat message."""
    CHAT_MESSAGE_COUNT.labels(direction=direction, model=model).inc()
    CHAT_TOKEN_COUNT.labels(direction=direction, model=model).inc(tokens)

    # Also track in the more detailed LLM metrics
    token_type = 'prompt' if direction == 'user' else 'completion'
    LLM_TOKEN_USAGE.labels(model=model, token_type=token_type).inc(tokens)


def track_model_request(model: str, status: str = 'success') -> None:
    """Track an LLM API request."""
    LLM_REQUEST_COUNT.labels(model=model, status=status).inc()

    # Also increment chat message count for the app_metrics dashboard
    # Only count successful requests as messages
    if status == 'success':
        CHAT_MESSAGE_COUNT.labels(direction='assistant', model=model).inc()


def track_llm_error(model: str, error_type: str) -> None:
    """Track an LLM API error."""
    LLM_ERROR_COUNT.labels(model=model, error_type=error_type).inc()
    LLM_REQUEST_COUNT.labels(model=model, status='error').inc()


def track_model_usage(
    model: str, usage_data: dict[str, Any], duration: float | None
) -> None:
    """Track LLM usage from usage data dictionary.

    Expected keys in usage_data:
    - request_tokens: int
    - response_tokens: int
    - total_tokens: int
    """
    logger.debug(f'Tracking LLM usage: {model=}, {usage_data=}')

    # Track token usage by type
    if 'request_tokens' in usage_data:
        LLM_TOKEN_USAGE.labels(model=model, token_type='prompt').inc(  # noqa: S106
            usage_data['request_tokens']
        )
        # Also track in the original chat metrics for app_metrics dashboard
        CHAT_TOKEN_COUNT.labels(direction='user', model=model).inc(
            usage_data['request_tokens']
        )

    if 'response_tokens' in usage_data:
        LLM_TOKEN_USAGE.labels(model=model, token_type='completion').inc(  # noqa: S106
            usage_data['response_tokens']
        )
        # Also track in the original chat metrics for app_metrics dashboard
        CHAT_TOKEN_COUNT.labels(direction='assistant', model=model).inc(
            usage_data['response_tokens']
        )

    if 'total_tokens' in usage_data:
        LLM_TOKEN_USAGE.labels(model=model, token_type='total').inc(  #  noqa: S106
            usage_data['total_tokens']
        )

    if duration:
        CHAT_LATENCY.labels(model=model).observe(duration)
        LLM_REQUEST_LATENCY.labels(model=model).observe(duration)

    track_model_request(model, status='success')


def track_context_server_query(server: str, operation: str) -> None:
    """Track a context server query."""
    CONTEXT_SERVER_QUERY_COUNT.labels(server=server, operation=operation).inc()


def track_context_server_latency(server: str, operation: str, duration: float) -> None:
    """Track context server latency."""
    CONTEXT_SERVER_LATENCY.labels(server=server, operation=operation).observe(duration)


def track_context_server_error(server: str, operation: str, error_type: str) -> None:
    """Track a context server error."""
    CONTEXT_SERVER_ERROR_COUNT.labels(
        server=server, operation=operation, error_type=error_type
    ).inc()
