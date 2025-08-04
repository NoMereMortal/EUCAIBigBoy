# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Client registry implementation."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable
from contextlib import asynccontextmanager
from typing import Any, Callable, TypeVar, cast

from loguru import logger

from app.clients.base import BaseClient
from app.clients.container import ClientContainer
from app.config import Settings

T = TypeVar('T', bound=BaseClient)


class ClientRegistry:
    """Registry for managing service clients."""

    def __init__(self, settings: Settings) -> None:
        """Initialize client registry."""
        self.settings = settings
        self._clients: dict[str, BaseClient] = {}
        self._initialized = False
        self._client_status: dict[
            str, bool
        ] = {}  # Track initialization status per client
        self._containers: dict[
            str, ClientContainer
        ] = {}  # Container-based client management

    async def setup(self) -> None:
        """Set up all client containers."""
        # Import here to avoid circular imports
        from app.clients.bedrock.client import BedrockClient
        from app.clients.bedrock_runtime.client import BedrockRuntimeClient
        from app.clients.dynamodb.client import DynamoDBClient
        from app.clients.kms.client import KMSClient
        from app.clients.neptune.client import NeptuneClient
        from app.clients.s3.client import S3Client
        from app.clients.secrets_manager.client import SecretsManagerClient
        from app.clients.valkey.client import ValkeyClient

        # Register core clients
        self.register_container(
            'dynamodb', lambda: self._create_client(DynamoDBClient, self.settings)
        )
        self.register_container(
            'valkey', lambda: self._create_client(ValkeyClient, self.settings)
        )
        self.register_container(
            's3', lambda: self._create_client(S3Client, self.settings)
        )
        self.register_container(
            'bedrock', lambda: self._create_client(BedrockClient, self.settings)
        )
        self.register_container(
            'bedrock_runtime',
            lambda: self._create_client(BedrockRuntimeClient, self.settings),
        )
        self.register_container(
            'kms', lambda: self._create_client(KMSClient, self.settings)
        )
        self.register_container(
            'secrets_manager',
            lambda: self._create_client(SecretsManagerClient, self.settings),
        )

        # Conditional clients
        if self.settings.aws.neptune.enabled and self.settings.aws.neptune.endpoint_url:
            self.register_container(
                'neptune', lambda: self._create_client(NeptuneClient, self.settings)
            )

        # Optional clients based on settings
        if self.settings.opensearch.enabled:
            try:
                from app.clients.opensearch.client import OpenSearchClient

                self.register_container(
                    'opensearch',
                    lambda: self._create_client(OpenSearchClient, self.settings),
                )
            except ImportError:
                logger.warning(
                    'OpenSearch client enabled but module not found - skipping'
                )

    def register_container(
        self, name: str, factory: Callable[[], Awaitable[T]]
    ) -> None:
        """Register a new client container."""
        self._containers[name] = ClientContainer(factory, name)

    async def _create_client(self, client_class: type[T], settings: Settings) -> T:
        """Create and initialize a client instance."""
        client = client_class(settings)
        await client.initialize()
        return client

    async def _init_existing_client(self, client: BaseClient) -> BaseClient:
        """Initialize an existing client."""
        await client.initialize()
        return client

    async def register(self, name: str, client: BaseClient) -> None:
        """Register a client with the registry."""
        if name in self._clients:
            logger.warning(f'Client {name} already registered, replacing')

        self._clients[name] = client
        self._client_status[name] = False  # Mark as not initialized
        logger.debug(f'Registered client: {name}')

        # Also register in container system for unified management
        self.register_container(name, lambda: self._init_existing_client(client))

    def add_client_sync(self, name: str, client: BaseClient) -> None:
        """Synchronously add a client to the registry without async register."""
        if name in self._clients:
            logger.warning(f'Client {name} already registered, replacing')

        self._clients[name] = client
        self._client_status[name] = False  # Mark as not initialized
        logger.debug(f'Added client synchronously: {name}')

        # Also register in container system for unified management
        self.register_container(name, lambda: self._init_existing_client(client))

    async def get_client(self, name: str) -> tuple[BaseClient | None, bool]:
        """
        Get a client by name with availability status.

        Returns:
            A tuple containing (client, is_available)
        """
        # Try container-based approach first
        container = self._containers.get(name)
        if container:
            client = await container.get()
            return client, container.is_available

        # Fallback to legacy system
        client = self._clients.get(name)
        is_initialized = self._client_status.get(name, False)

        if not client:
            logger.warning(f'Client {name} not found in registry')

        return client, is_initialized

    def get_client_sync(self, name: str) -> BaseClient | None:
        """
        Get a client by name synchronously (legacy method).

        Note: This doesn't check initialization status.
        """
        client = self._clients.get(name)
        if not client:
            logger.warning(f'Client {name} not found in registry')
        return client

    async def get_typed_client(
        self, name: str, client_type: type[T]
    ) -> tuple[T | None, bool]:
        """
        Get a client by name with type checking and availability status.

        Returns:
            A tuple containing (client, is_available)
        """
        client, available = await self.get_client(name)

        if client is None:
            return None, False

        if not isinstance(client, client_type):
            logger.error(f'Client {name} is not of type {client_type.__name__}')
            return None, False

        return cast(T, client), available

    def get_typed_client_sync(self, name: str, client_type: type[T]) -> T | None:
        """
        Get a client by name with type checking synchronously (legacy method).

        Note: This doesn't check initialization status.
        """
        client = self.get_client_sync(name)
        if client is None:
            return None

        if not isinstance(client, client_type):
            logger.error(f'Client {name} is not of type {client_type.__name__}')
            return None

        return cast(T, client)

    def get_clients(self) -> dict[str, BaseClient]:
        """Get all registered clients."""
        return self._clients.copy()

    def get_client_names(self) -> list[str]:
        """Get names of all registered clients."""
        # Combine legacy and container-based client names
        names = set(self._clients.keys())
        names.update(self._containers.keys())
        return list(names)

    def client_info(self) -> list[dict[str, Any]]:
        """Get information about all registered clients."""
        results: list[dict[str, Any]] = []

        # Add container-based clients
        for name, container in self._containers.items():
            info: dict[str, Any] = {
                'name': name,
                'type': container._client.__class__.__name__
                if container._client
                else 'Unknown',
                'initialized': container.is_available,
                'error': str(container.error) if container.error else None,
            }
            results.append(info)

        # Add any legacy clients not in containers
        for name, client in self._clients.items():
            if name not in self._containers:
                info: dict[str, Any] = {
                    'name': name,
                    'type': client.__class__.__name__,
                }

                # Check if the client has a _client attribute to determine initialization
                if hasattr(client, '_client'):
                    info['initialized'] = getattr(client, '_client', None) is not None
                else:
                    # If _client attribute doesn't exist, assume initialized based on the registry state
                    info['initialized'] = self._client_status.get(name, False)

                results.append(info)

        return results

    async def initialize_client(self, name: str) -> bool:
        """Initialize a specific client by name."""
        # Try container-based approach first
        container = self._containers.get(name)
        if container:
            await container.initialize()
            success = container.is_available
            if success:
                logger.info(f'Client {name} initialized successfully via container')
            return success

        # Fallback to legacy approach
        client = self._clients.get(name)
        if client is None:
            logger.warning(f'Cannot initialize non-existent client: {name}')
            return False

        if self._client_status.get(name, False):
            logger.debug(f'Client {name} already initialized')
            return True

        try:
            await client.initialize()
            self._client_status[name] = True
            logger.info(f'Client {name} initialized successfully')
            return True
        except Exception as e:
            logger.error(f'Failed to initialize client {name}: {e}')
            self._client_status[name] = False
            return False

    def is_client_initialized(self, name: str) -> bool:
        """Check if a specific client is initialized."""
        # Try container-based approach first
        container = self._containers.get(name)
        if container:
            return container.is_available

        # Fallback to legacy approach
        if name not in self._clients:
            return False
        return self._client_status.get(name, False)

    async def initialize_all(self) -> None:
        """Initialize all registered clients."""
        if self._initialized:
            logger.debug('Clients already initialized')
            return

        logger.info('Initializing all clients')

        # Initialize container-based clients concurrently
        init_tasks = []
        for _name, container in self._containers.items():
            init_tasks.append(container.initialize())

        # Run initialization tasks concurrently with exception handling
        if init_tasks:
            results = await asyncio.gather(*init_tasks, return_exceptions=True)
            for name, result in zip(self._containers.keys(), results):
                if isinstance(result, Exception):
                    logger.error(
                        f'Failed to initialize container client {name}: {result}'
                    )

        # Initialize any remaining legacy clients
        all_succeeded = True
        for name, client in self._clients.items():
            # Skip if already handled by container system
            if name in self._containers:
                continue

            try:
                logger.debug(f'Initializing client: {name}')
                await client.initialize()
                self._client_status[name] = True
                logger.debug(f'Client initialized: {name}')
            except Exception as e:
                logger.error(f'Failed to initialize client {name}: {e}')
                self._client_status[name] = False
                all_succeeded = False

        self._initialized = all_succeeded
        logger.info('All clients initialized')

    async def cleanup_all(self) -> None:
        """Clean up all registered clients."""
        logger.info('Cleaning up all clients')

        # Clean up container-based clients
        cleanup_tasks = []
        for _name, container in self._containers.items():
            cleanup_tasks.append(container.shutdown())

        # Run cleanup tasks concurrently with exception handling
        if cleanup_tasks:
            results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            for name, result in zip(self._containers.keys(), results):
                if isinstance(result, Exception):
                    logger.error(
                        f'Failed to clean up container client {name}: {result}'
                    )

        # Clean up any remaining legacy clients
        for name, client in self._clients.items():
            # Skip if already handled by container system
            if name in self._containers:
                continue

            try:
                logger.debug(f'Cleaning up client: {name}')
                await client.cleanup()
                logger.debug(f'Client cleaned up: {name}')
            except Exception as e:
                logger.error(f'Failed to clean up client {name}: {e}')

        self._initialized = False
        logger.info('All clients cleaned up')

    @asynccontextmanager
    async def initialize_context(self) -> AsyncGenerator['ClientRegistry', None]:
        """Context manager for initializing and cleaning up clients."""
        try:
            await self.initialize_all()
            yield self
        finally:
            await self.cleanup_all()


async def initialize_clients(
    settings: Settings, registry: ClientRegistry
) -> ClientRegistry:
    """Initialize and register clients."""
    # Create clients
    from loguru import logger

    from app.clients.bedrock.client import BedrockClient
    from app.clients.bedrock_runtime.client import BedrockRuntimeClient
    from app.clients.dynamodb.client import DynamoDBClient
    from app.clients.kms.client import KMSClient
    from app.clients.neptune.client import NeptuneClient
    from app.clients.s3.client import S3Client
    from app.clients.secrets_manager.client import SecretsManagerClient
    from app.clients.valkey.client import ValkeyClient

    # Register core clients
    await registry.register('dynamodb', DynamoDBClient(settings))

    # Register Neptune client only if enabled
    if settings.aws.neptune.enabled:
        if not settings.aws.neptune.endpoint_url:
            logger.error('Neptune client enabled but no endpoint URL configured')
        else:
            await registry.register('neptune', NeptuneClient(settings))
            logger.info('Neptune client registered - enabled and configured')
    else:
        logger.info('Neptune client skipped - disabled')

    await registry.register('valkey', ValkeyClient(settings))

    # Create S3 client with additional logging
    s3_client = S3Client(settings)
    logger.info(f'Created S3 client: {s3_client}, type={type(s3_client).__name__}')

    # Register S3 client
    await registry.register('s3', s3_client)
    logger.info(
        f'Registered S3 client in registry. Client initialized: {hasattr(s3_client, "_client") and s3_client._client is not None}'
    )

    # Register remaining clients
    await registry.register('bedrock', BedrockClient(settings))
    await registry.register('bedrock_runtime', BedrockRuntimeClient(settings))
    await registry.register('kms', KMSClient(settings))
    await registry.register('secrets_manager', SecretsManagerClient(settings))

    # Register optional clients based on settings
    if settings.opensearch.enabled:
        try:
            from app.clients.opensearch.client import OpenSearchClient

            await registry.register('opensearch', OpenSearchClient(settings))
            logger.info('OpenSearch client registered - enabled and module available')
        except ImportError:
            logger.warning('OpenSearch client enabled but module not found - skipping')
        except Exception as e:
            logger.error(f'Failed to register OpenSearch client: {e}')
    else:
        logger.info('OpenSearch client skipped - disabled')

    # Bedrock Knowledge Base client is commented out - not implemented
    # if settings.bedrock.knowledge_base.enabled:
    #     # Import only if enabled
    #     try:
    #         from app.clients.bedrock_knowledge_base.client import BedrockKnowledgeBaseClient
    #         await registry.register("bedrock_kb", BedrockKnowledgeBaseClient(settings))
    #     except ImportError:
    #         logger.warning("BedrockKnowledgeBaseClient module not found")

    return registry


async def create_registry(settings: Settings) -> ClientRegistry:
    """Create and initialize the client registry."""
    registry = ClientRegistry(settings)
    await initialize_clients(settings, registry)
    return registry
