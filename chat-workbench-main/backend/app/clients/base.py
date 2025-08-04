# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Base client for all clients."""

import abc
import time
from typing import Any, Callable

from loguru import logger  # type: ignore

from app.api.middleware.context import RequestContext
from app.config import Settings
from app.monitoring import (
    set_circuit_breaker_state,
    track_client_error,
    track_client_request,
)


class CircuitOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """Circuit breaker for client operations."""

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: int = 30,
        half_open_max_calls: int = 1,
    ) -> None:
        """Initialize circuit breaker."""
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls
        self.failures = 0
        self.last_failure_time: float = 0.0
        self.state = 'closed'
        self.half_open_calls = 0
        self.client_name: str | None = None  # Will be set by BaseClient
        self.metrics: dict[str, Any] = {
            'open_count': 0,
            'half_open_count': 0,
            'success_count': 0,
            'failure_count': 0,
            'last_state_change': time.time(),
        }

    def record_failure(self) -> None:
        """Record a failure."""
        self.failures += 1
        self.last_failure_time = time.time()
        self.metrics['failure_count'] += 1

        if self.state == 'half-open':
            # Immediate open on failure in half-open state
            self.state = 'open'
            self.metrics['open_count'] += 1
            self.metrics['last_state_change'] = time.time()
            logger.warning('Circuit breaker reopened after test request failure')
        elif self.failures >= self.failure_threshold:
            self.state = 'open'
            self.metrics['open_count'] += 1
            self.metrics['last_state_change'] = time.time()
            logger.warning(f'Circuit breaker opened after {self.failures} failures')

        # Update Prometheus metric if client name is set
        if self.client_name:
            set_circuit_breaker_state(self.client_name, False)

    def record_success(self) -> None:
        """Record a success."""
        self.metrics['success_count'] += 1

        if self.state == 'half-open':
            # Reset after successful test request
            self.state = 'closed'
            self.failures = 0
            self.half_open_calls = 0
            self.metrics['last_state_change'] = time.time()
            logger.info('Circuit breaker closed after successful test request')
        elif self.state == 'closed':
            # Reset failures on success
            self.failures = 0

        # Update Prometheus metric if client name is set
        if self.client_name:
            set_circuit_breaker_state(self.client_name, True)

    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        if self.state == 'open':
            # Check if reset timeout has passed
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = 'half-open'
                self.half_open_calls = 0
                self.metrics['half_open_count'] += 1
                self.metrics['last_state_change'] = time.time()
                logger.info('Circuit breaker half-open')
                return True
            return False
        elif self.state == 'half-open':
            # Limit requests in half-open state
            if self.half_open_calls < self.half_open_max_calls:
                self.half_open_calls += 1
                return True
            return False
        return True

    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics."""
        return {
            **self.metrics,
            'current_state': self.state,
            'current_failures': self.failures,
            'uptime_since_last_open': time.time() - self.metrics['last_state_change']
            if self.state == 'closed'
            else 0,
        }


class BaseClient(abc.ABC):
    """Base client for all clients."""

    def __init__(self, settings: Settings):
        """Initialize base client."""
        self.settings = settings
        self.circuit_breaker = CircuitBreaker()
        self.circuit_breaker.client_name = self._get_client_name()
        set_circuit_breaker_state(self._get_client_name(), True)

    @abc.abstractmethod
    async def initialize(self) -> None:
        """Initialize client."""
        pass

    @abc.abstractmethod
    async def cleanup(self) -> None:
        """Clean up client."""
        pass

    def monitor_operation(self, operation_name: str) -> 'OperationMonitor':
        """Context manager for monitoring operations."""
        return OperationMonitor(self, operation_name)

    def _get_client_name(self) -> str:
        """Get client name for metrics."""
        return self.__class__.__name__.replace('Client', '').lower()

    def get_circuit_breaker_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics."""
        return self.circuit_breaker.get_metrics()

    def check_client_ttl_and_recreate(
        self,
        client: Any,
        creation_time: float,
        ttl_seconds: float,
        recreate_func: Callable[[], Any],
        client_name: str = 'client',
    ) -> tuple[Any, float]:
        """
        Helper method to check client TTL and recreate if expired.

        Args:
            client: Current client instance (None if not initialized)
            creation_time: Timestamp when client was created
            ttl_seconds: TTL in seconds
            recreate_func: Function to call to recreate the client
            client_name: Name for logging purposes

        Returns:
            Tuple of (client, creation_time) - either existing or newly created
        """
        current_time = time.time()

        # Check if client needs refresh due to TTL expiration
        if not client or (current_time - creation_time) > ttl_seconds:
            logger.info(f'{client_name} TTL expired, recreating with fresh credentials')
            try:
                client = recreate_func()
                creation_time = current_time
                logger.info(f'{client_name} recreated successfully')
            except Exception as e:
                logger.error(f'Failed to recreate {client_name}: {e}')
                self.circuit_breaker.record_failure()
                raise

        return client, creation_time


class OperationMonitor:
    """Context manager for monitoring operations."""

    def __init__(self, client: BaseClient, operation_name: str) -> None:
        """Initialize operation monitor."""
        self.client = client
        self.operation_name = operation_name
        self.start_time: float | None = None
        self.client_name = client._get_client_name()

        # Get current request state
        state = RequestContext.get_state()
        self.request_id = state.request_id
        self.chat_id = state.chat_id
        self.user_id = state.user_id

    def __enter__(self) -> 'OperationMonitor':
        """Enter context manager."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        duration = time.time() - self.start_time if self.start_time is not None else 0.0

        # Build context dict
        context = {
            'operation': self.operation_name,
            'duration': duration,
        }

        if self.request_id:
            context['request_id'] = self.request_id

        if self.chat_id:
            context['chat_id'] = self.chat_id

        if self.user_id:
            context['user_id'] = self.user_id

        if exc_type:
            # Log error
            logger.error(
                f'Operation {self.operation_name} failed: {exc_val}', **context
            )
            # Track client error in Prometheus
            error_type = exc_type.__name__
            track_client_error(self.client_name, self.operation_name, error_type)

            # Record failure in circuit breaker
            self.client.circuit_breaker.record_failure()
        else:
            # Log success
            logger.debug(
                f'Operation {self.operation_name} completed in {duration:.3f}s',
                **context,
            )
            # Track client request in Prometheus
            track_client_request(
                self.client_name, self.operation_name, 'success', duration
            )

            # Record success in circuit breaker
            self.client.circuit_breaker.record_success()
