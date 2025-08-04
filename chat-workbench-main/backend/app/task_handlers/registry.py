# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from typing import Any, cast

from loguru import logger

from app.clients.bedrock_runtime.client import BedrockRuntimeClient
from app.clients.dynamodb.client import DynamoDBClient
from app.clients.opensearch.client import OpenSearchClient
from app.clients.registry import ClientRegistry
from app.clients.s3.client import S3Client
from app.config import Settings
from app.services.content_storage import ContentStorageService
from app.task_handlers.base import BaseTaskHandler


class TaskHandlerRegistry:
    """Registry for task handlers - simplified version with no Valkey dependency."""

    def __init__(self) -> None:
        """Initialize task handler registry."""
        self._handlers: dict[str, BaseTaskHandler] = {}

    async def register(self, handler: BaseTaskHandler) -> None:
        """Register a task handler."""
        if not isinstance(handler, BaseTaskHandler):
            raise TypeError(
                f'Handler must be an instance of BaseTaskHandler, got {type(handler)}'
            )

        self._handlers[handler.name] = handler
        logger.info(f'Registered task handler: {handler.name}')

    async def get_handler(self, name: str) -> BaseTaskHandler:
        """Get a handler by name."""
        if name not in self._handlers:
            raise ValueError(f'No handler found for task: {name}')

        return self._handlers[name]

    async def get_handlers(self) -> dict[str, BaseTaskHandler]:
        """Get all registered handlers."""
        return self._handlers.copy()

    async def get_handler_names(self) -> list[str]:
        """Get names of all registered handlers."""
        return list(self._handlers.keys())

    async def handler_info(self) -> list[dict[str, Any]]:
        """Get information about all registered handlers."""
        return [
            {
                'name': handler.name,
                'description': handler.description,
            }
            for handler in self._handlers.values()
        ]


async def initialize_task_handlers(
    settings: Settings,
    registry: TaskHandlerRegistry,
    client_registry: ClientRegistry | None = None,
) -> TaskHandlerRegistry:
    """Initialize and register task handlers with dependency injection."""

    # Initialize all client variables with None by default
    bedrock_runtime_client = None
    dynamodb_client = None
    s3_client = None
    opensearch_client = None

    if client_registry:
        # Retrieve clients with availability checking
        bedrock_runtime_result = await client_registry.get_typed_client(
            'bedrock_runtime', BedrockRuntimeClient
        )
        dynamodb_result = await client_registry.get_typed_client(
            'dynamodb', DynamoDBClient
        )
        s3_result = await client_registry.get_typed_client('s3', S3Client)
        opensearch_result = await client_registry.get_typed_client(
            'opensearch', OpenSearchClient
        )

        # Extract clients if available
        bedrock_runtime_client, bedrock_runtime_available = bedrock_runtime_result
        dynamodb_client, dynamodb_available = dynamodb_result
        s3_client, s3_available = s3_result
        opensearch_client, opensearch_available = opensearch_result

        # Log availability status
        if not bedrock_runtime_available and bedrock_runtime_client:
            logger.warning('Bedrock Runtime client is not fully initialized')
        if not dynamodb_available and dynamodb_client:
            logger.warning('DynamoDB client is not fully initialized')
        if not opensearch_available and opensearch_client:
            logger.warning('OpenSearch client is not fully initialized')
        if s3_client and s3_available:
            ContentStorageService(settings, s3_client)

    # Import handlers
    from app.task_handlers.chat.handler import ChatHandler
    from app.task_handlers.rag_oss.handler import RagOssHandler

    if opensearch_client and bedrock_runtime_client:
        # Use these clients to create handlers
        await registry.register(
            ChatHandler(
                cast(
                    OpenSearchClient, opensearch_client
                ),  # Cast to satisfy type checker
                cast(BedrockRuntimeClient, bedrock_runtime_client),
                settings.aws.get_boto_config('bedrock'),
            )
        )
        logger.info('Registered ChatHandler')

        await registry.register(
            RagOssHandler(
                opensearch_client,
                cast(BedrockRuntimeClient, bedrock_runtime_client),
                settings.aws.get_boto_config('bedrock'),
            )
        )
        logger.info('Registered RagOssHandler')
    else:
        logger.error(
            'Handler clients failed to register, missing opensearch client or bedrock runtime client'
        )

    # Register task handler configurations in DynamoDB
    if dynamodb_client:
        from app.repositories.task_handler_metadata import (
            TaskHandlerConfigRepository,
        )

        # Cast to satisfy type checker
        typed_dynamodb_client = cast(DynamoDBClient, dynamodb_client)
        config_repo = TaskHandlerConfigRepository(typed_dynamodb_client)

        # Create default config for each handler if it doesn't exist
        handlers = await registry.get_handlers()
        for handler in handlers.values():
            await config_repo.create_metadata(handler, default=handler.name == 'chat')

    return registry


async def create_registry(
    settings: Settings, client_registry: ClientRegistry | None = None
) -> TaskHandlerRegistry:
    """Create and initialize the task handler registry."""

    # Create registry without Valkey client
    registry = TaskHandlerRegistry()

    # Initialize task handlers
    await initialize_task_handlers(settings, registry, client_registry)

    return registry
