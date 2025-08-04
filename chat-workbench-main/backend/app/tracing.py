# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tracing utilities for the application using OpenTelemetry."""

import contextlib
import os
from collections.abc import AsyncGenerator, Generator
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, cast

from fastapi import FastAPI
from loguru import logger
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Span, SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from strands.telemetry import StrandsTelemetry

# Type variables for generic function decorators
F = TypeVar('F', bound=Callable[..., Any])
T = TypeVar('T')

# Constants
SERVICE_NAME = os.environ.get('OTEL_SERVICE_NAME', 'chat-workbench')
OTLP_ENDPOINT = os.environ.get(
    'OTEL_EXPORTER_OTLP_TRACES_ENDPOINT', 'http://jaeger:4318/v1/traces'
)


class TracingManager:
    """Manager for OpenTelemetry tracing setup and utilities."""

    _instance: Optional['TracingManager'] = None
    _initialized = False

    def __new__(cls) -> 'TracingManager':
        """Create a singleton instance."""
        if cls._instance is None:
            # Use type ignore to bypass the type check for the assignment
            cls._instance = super().__new__(cls)  # type: ignore
        # Use cast to ensure the return type is correct
        return cast('TracingManager', cls._instance)

    def __init__(self) -> None:
        """Initialize the tracing manager."""
        if not self._initialized:
            self._tracer_provider: Optional[TracerProvider] = None
            self._strands_telemetry: Optional[StrandsTelemetry] = None
            self._initialized = True

    def setup_tracing(
        self,
        service_name: str = SERVICE_NAME,
        otlp_endpoint: str = OTLP_ENDPOINT,
        console_export: bool = False,
    ) -> None:
        """
        Set up OpenTelemetry tracing with OTLP exporter.

        Args:
            service_name: Name of the service
            otlp_endpoint: OTLP endpoint URL
            console_export: Whether to enable console export for debugging
        """
        # Create a resource with service info
        resource = Resource.create({'service.name': service_name})

        # Create a tracer provider
        tracer_provider = TracerProvider(resource=resource)

        # Add OTLP exporter
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Optionally add console exporter for debugging
        if console_export:
            console_exporter = ConsoleSpanExporter()
            tracer_provider.add_span_processor(SimpleSpanProcessor(console_exporter))

        # Set the tracer provider as the global default
        trace.set_tracer_provider(tracer_provider)

        # Store the tracer provider for later use
        self._tracer_provider = tracer_provider

        # Set up Strands telemetry
        self._setup_strands_telemetry(tracer_provider)

        # Set up instrumentation for common libraries
        self._setup_instrumentations()

        logger.info(
            f'OpenTelemetry tracing initialized with service name: {service_name}'
        )
        logger.info(f'OTLP endpoint: {otlp_endpoint}')

    def _setup_strands_telemetry(self, tracer_provider: TracerProvider) -> None:
        """
        Set up Strands telemetry with the tracer provider.

        Args:
            tracer_provider: The tracer provider to use
        """
        try:
            # Initialize StrandsTelemetry with our tracer provider
            strands_telemetry = StrandsTelemetry(tracer_provider=tracer_provider)

            # Set up OTLP exporter for Strands
            strands_telemetry.setup_otlp_exporter()

            # Optionally set up console exporter for debugging
            if os.environ.get('OTEL_DEBUG', 'false').lower() == 'true':
                strands_telemetry.setup_console_exporter()

            # Store the telemetry instance
            self._strands_telemetry = strands_telemetry

            logger.info('Strands telemetry initialized with OpenTelemetry')
        except Exception as e:
            logger.error(f'Failed to initialize Strands telemetry: {e}')

    def _setup_instrumentations(self) -> None:
        """Set up auto-instrumentation for common libraries."""
        # Instrument HTTPX for HTTP client tracing
        try:
            instrumentor = HTTPXClientInstrumentor()
            if instrumentor is not None:
                instrumentor.instrument()
                logger.debug('HTTPX instrumentation enabled')
            else:
                logger.warning(
                    'HTTPXClientInstrumentor returned None, skipping instrumentation'
                )
        except Exception as e:
            logger.error(f'Failed to set up HTTPX instrumentation: {e}')

    def instrument_fastapi(self, app: FastAPI) -> None:
        """
        Instrument a FastAPI application.

        Args:
            app: The FastAPI application to instrument
        """
        FastAPIInstrumentor.instrument_app(app)
        logger.debug(f'FastAPI instrumentation enabled for app: {app}')

    def get_tracer(self, name: str) -> trace.Tracer:
        """
        Get a tracer for the given name.

        Args:
            name: Name of the tracer

        Returns:
            A tracer instance
        """
        return trace.get_tracer(name)

    @contextlib.contextmanager
    def create_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Generator[Span, None, None]:
        """
        Create a new span as a context manager.

        Args:
            name: Name of the span
            kind: Kind of span (default: INTERNAL)
            attributes: Optional attributes to add to the span

        Yields:
            The created span
        """
        tracer = self.get_tracer(__name__)
        with tracer.start_as_current_span(name, kind=kind) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise

    def trace_function(
        self,
        name: Optional[str] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Callable[[F], F]:
        """
        Decorator to trace a function.

        Args:
            name: Optional name for the span (defaults to function name)
            kind: Kind of span (default: INTERNAL)
            attributes: Optional attributes to add to the span

        Returns:
            Decorated function
        """

        def decorator(func: F) -> F:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                span_name = name or f'{func.__module__}.{func.__qualname__}'
                span_attributes = attributes or {}

                with self.create_span(span_name, kind, span_attributes):
                    return func(*args, **kwargs)

            return cast(F, wrapper)

        return decorator

    def trace_async_function(
        self,
        name: Optional[str] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Callable[[F], F]:
        """
        Decorator to trace an async function.

        Args:
            name: Optional name for the span (defaults to function name)
            kind: Kind of span (default: INTERNAL)
            attributes: Optional attributes to add to the span

        Returns:
            Decorated async function
        """

        def decorator(func: F) -> F:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                span_name = name or f'{func.__module__}.{func.__qualname__}'
                span_attributes = attributes or {}

                with self.create_span(span_name, kind, span_attributes):
                    return await func(*args, **kwargs)

            return cast(F, wrapper)

        return decorator

    def trace_async_generator_function(
        self,
        name: Optional[str] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Callable[[F], F]:
        """
        Decorator to trace an async generator function.

        Args:
            name: Optional name for the span (defaults to function name)
            kind: Kind of span (default: INTERNAL)
            attributes: Optional attributes to add to the span

        Returns:
            Decorated async generator function
        """

        def decorator(func: F) -> F:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
                span_name = name or f'{func.__module__}.{func.__qualname__}'
                span_attributes = attributes or {}

                # Create the generator outside the span context
                gen = func(*args, **kwargs)

                # Create a span for each yielded value instead of the entire generator
                # This avoids context detachment issues when the generator is exited unexpectedly
                try:
                    async for value in gen:
                        # Create a new span for each yielded value
                        with self.create_span(
                            f'{span_name}.yield', kind, span_attributes
                        ) as span:
                            yield value
                except GeneratorExit:
                    # Handle generator exit gracefully without trying to detach context
                    logger.debug(f'Generator {span_name} exited')
                    # We don't need to re-raise GeneratorExit as it's handled by Python
                except Exception as e:
                    # For other exceptions, create a span to record the error
                    with self.create_span(
                        f'{span_name}.error', kind, span_attributes
                    ) as span:
                        span.set_status(Status(StatusCode.ERROR))
                        span.record_exception(e)
                    raise

            return cast(F, wrapper)

        return decorator

    def extract_context_from_headers(self, headers: dict[str, str]) -> None:
        """
        Extract trace context from headers.

        Args:
            headers: HTTP headers containing trace context
        """
        propagator = TraceContextTextMapPropagator()
        # Use type casting to satisfy the type checker
        context = propagator.extract(cast(Any, headers))
        trace.set_span_in_context(trace.get_current_span(), context)

    def inject_context_into_headers(self, headers: dict[str, str]) -> None:
        """
        Inject current trace context into headers.

        Args:
            headers: HTTP headers to inject trace context into
        """
        propagator = TraceContextTextMapPropagator()
        # Use type casting to satisfy the type checker
        propagator.inject(cast(Any, headers))


# Create a singleton instance
tracing_manager = TracingManager()


def setup_tracing(
    service_name: str = SERVICE_NAME,
    otlp_endpoint: str = OTLP_ENDPOINT,
    console_export: bool = False,
) -> None:
    """
    Set up OpenTelemetry tracing.

    Args:
        service_name: Name of the service
        otlp_endpoint: OTLP endpoint URL
        console_export: Whether to enable console export for debugging
    """
    tracing_manager.setup_tracing(service_name, otlp_endpoint, console_export)


def instrument_fastapi(app: FastAPI) -> None:
    """
    Instrument a FastAPI application.

    Args:
        app: The FastAPI application to instrument
    """
    tracing_manager.instrument_fastapi(app)


def get_tracer(name: str) -> trace.Tracer:
    """
    Get a tracer for the given name.

    Args:
        name: Name of the tracer

    Returns:
        A tracer instance
    """
    return tracing_manager.get_tracer(name)


@contextlib.contextmanager
def create_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[dict[str, Any]] = None,
) -> Generator[Span, None, None]:
    """
    Create a new span as a context manager.

    Args:
        name: Name of the span
        kind: Kind of span (default: INTERNAL)
        attributes: Optional attributes to add to the span

    Yields:
        The created span
    """
    with tracing_manager.create_span(name, kind, attributes) as span:
        yield span


def trace_function(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[dict[str, Any]] = None,
) -> Callable[[F], F]:
    """
    Decorator to trace a function.

    Args:
        name: Optional name for the span (defaults to function name)
        kind: Kind of span (default: INTERNAL)
        attributes: Optional attributes to add to the span

    Returns:
        Decorated function
    """
    return tracing_manager.trace_function(name, kind, attributes)


def trace_async_function(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[dict[str, Any]] = None,
) -> Callable[[F], F]:
    """
    Decorator to trace an async function.

    Args:
        name: Optional name for the span (defaults to function name)
        kind: Kind of span (default: INTERNAL)
        attributes: Optional attributes to add to the span

    Returns:
        Decorated async function
    """
    return tracing_manager.trace_async_function(name, kind, attributes)


def trace_async_generator_function(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[dict[str, Any]] = None,
) -> Callable[[F], F]:
    """
    Decorator to trace an async generator function.

    Args:
        name: Optional name for the span (defaults to function name)
        kind: Kind of span (default: INTERNAL)
        attributes: Optional attributes to add to the span

    Returns:
        Decorated async generator function
    """
    return tracing_manager.trace_async_generator_function(name, kind, attributes)
