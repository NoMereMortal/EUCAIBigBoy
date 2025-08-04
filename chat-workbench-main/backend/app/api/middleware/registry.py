# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Middleware registry for managing middleware instances."""

from starlette.middleware.base import BaseHTTPMiddleware


class MiddlewareRegistry:
    """Registry for middleware instances.

    This registry allows middleware instances to be registered and retrieved
    by name, making it easier to configure middleware after initialization.
    """

    def __init__(self) -> None:
        """Initialize the middleware registry."""
        self._middleware: dict[str, BaseHTTPMiddleware] = {}

    def register(self, name: str, middleware: BaseHTTPMiddleware) -> None:
        """Register a middleware instance.

        Args:
            name: The name to register the middleware under
            middleware: The middleware instance to register
        """
        self._middleware[name] = middleware

    def get(self, name: str) -> BaseHTTPMiddleware | None:
        """Get a middleware instance by name.

        Args:
            name: The name of the middleware to retrieve

        Returns:
            The middleware instance, or None if not found
        """
        return self._middleware.get(name)
