# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Client container implementation for enhanced lifecycle management."""

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Generic, Optional, Protocol, TypeVar, cast

from loguru import logger


# Define a protocol for cleanable clients
class CleanableClient(Protocol):
    """Protocol for clients with cleanup method."""

    async def cleanup(self) -> None:
        """Clean up resources."""
        ...


T = TypeVar('T')


class ClientContainer(Generic[T]):
    """Container for managing client lifecycles with proper async context management."""

    def __init__(self, client_factory: Callable[[], Awaitable[T]], name: str):
        """
        Initialize a client container.

        Args:
            client_factory: Factory function that creates and initializes the client
            name: Name of the client for logging and reference
        """
        self.client_factory = client_factory
        self.name = name
        self._client: Optional[T] = None
        self._initialized: bool = False
        self._initialization_error: Optional[Exception] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the client safely."""
        async with self._lock:
            if self._initialized:
                return

            try:
                logger.debug(f'Initializing client container: {self.name}')
                self._client = await self.client_factory()
                self._initialized = True
                self._initialization_error = None
                logger.info(f'Successfully initialized client: {self.name}')
            except Exception as e:
                self._initialization_error = e
                logger.error(f'Failed to initialize client {self.name}: {e}')

    async def get(self) -> Optional[T]:
        """Get the client, initializing if needed."""
        if not self._initialized:
            await self.initialize()
        return self._client

    @property
    def is_available(self) -> bool:
        """Check if client is available."""
        return self._initialized and self._client is not None

    @property
    def error(self) -> Optional[Exception]:
        """Get initialization error if any."""
        return self._initialization_error

    async def shutdown(self) -> None:
        """Shutdown the client properly."""
        if not self._client:
            return

        # Handle cleanup in a type-safe way
        try:
            if hasattr(self._client, 'cleanup'):
                cleanup_attr = self._client.cleanup  # type: ignore[attr-defined]

                # Check if it's callable
                if callable(cleanup_attr):
                    # Check if it's a coroutine function
                    if inspect.iscoroutinefunction(cleanup_attr):
                        # It's an async function
                        client_with_async_cleanup = cast(CleanableClient, self._client)
                        await client_with_async_cleanup.cleanup()
                    else:
                        # It's a regular function - call it directly
                        cleanup_attr()

                    logger.debug(f'Client {self.name} cleaned up successfully')
            else:
                logger.debug(f'Client {self.name} has no cleanup method')

        except Exception as e:
            logger.error(f'Error during client {self.name} cleanup: {e}')

        # Reset container state
        self._client = None
        self._initialized = False
        logger.debug(f'Client container {self.name} shutdown complete')
