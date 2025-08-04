# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Middleware setup utilities."""

from typing import Any, TypeVar, cast

from fastapi import FastAPI
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

# For app.config, use absolute import since it's outside the middleware package
from app.config import Settings  # type: ignore

# Use relative imports for middleware components to avoid import issues
from .error_handling import ErrorHandlingMiddleware
from .logging import LoggingMiddleware
from .metrics import MetricsMiddleware
from .request_context import RequestContextMiddleware
from .tracing import TracingMiddleware

# Define a type variable for middleware classes
M = TypeVar('M', bound=BaseHTTPMiddleware)

# Define middleware configuration with explicit priorities and dependencies
MIDDLEWARE_CONFIG = [
    {
        'class': ErrorHandlingMiddleware,
        'priority': 100,
        'requires_client': False,
        'depends_on': [],
    },
    {
        'class': LoggingMiddleware,
        'priority': 90,
        'requires_client': False,
        'depends_on': [],
    },
    {
        'class': TracingMiddleware,
        'priority': 80,
        'requires_client': False,
        'depends_on': ['LoggingMiddleware'],
    },
    {
        'class': MetricsMiddleware,
        'priority': 70,
        'requires_client': False,
        'depends_on': ['TracingMiddleware'],
    },
    {
        'class': RequestContextMiddleware,
        'priority': 60,
        'requires_client': False,
        'depends_on': [],
    },
]


def topological_sort(graph: dict[str, list[str]]) -> list[str]:
    """Perform topological sort on middleware dependencies."""
    # Convert class names to strings in graph if they aren't already
    string_graph = {
        k if isinstance(k, str) else getattr(k, '__name__', str(k)): v
        for k, v in graph.items()
    }

    # Find all nodes
    nodes = set(string_graph.keys())
    for dependencies in string_graph.values():
        nodes.update(dependencies)

    # Track visited and temp nodes for cycle detection
    visited: set[str] = set()
    temp: set[str] = set()
    result: list[str] = []

    def visit(node: str) -> None:
        if node in temp:
            raise ValueError(f'Circular dependency detected involving {node}')
        if node in visited:
            return

        temp.add(node)

        # Visit dependencies
        for dep in string_graph.get(node, []):
            visit(dep)

        temp.remove(node)
        visited.add(node)
        result.append(node)

    # Visit all nodes
    for node in nodes:
        if node not in visited:
            visit(node)

    # Reverse to get correct order (dependencies first)
    return list(reversed(result))


def add_middleware_safely(
    app: FastAPI, middleware_class: type[Any], **options: Any
) -> None:
    """
    Add middleware with proper type handling.

    This wrapper function ensures type safety when adding middleware to FastAPI.
    """
    # Cast the app to ASGIApp to satisfy the type checker
    cast(ASGIApp, app)

    # Add the middleware using the cast app
    app.add_middleware(middleware_class, **options)


def setup_basic_middleware(app: FastAPI, settings: Settings) -> None:
    """Set up basic middleware that doesn't require initialized clients."""
    # CORS middleware
    if settings.api.cors_origins:
        add_middleware_safely(
            app,
            CORSMiddleware,
            allow_origins=settings.api.cors_origins,
            allow_credentials=True,
            allow_methods=['*'],
            allow_headers=['*'],
        )

    # Add logging middleware
    add_middleware_safely(app, LoggingMiddleware)
    logger.debug('Added middleware: LoggingMiddleware')

    # Add error handling middleware
    add_middleware_safely(app, ErrorHandlingMiddleware)
    logger.debug('Added middleware: ErrorHandlingMiddleware')

    # Add metrics middleware
    add_middleware_safely(app, MetricsMiddleware)
    logger.debug('Added middleware: MetricsMiddleware')

    # Add request context middleware
    add_middleware_safely(app, RequestContextMiddleware)
    logger.debug('Added middleware: RequestContextMiddleware')
