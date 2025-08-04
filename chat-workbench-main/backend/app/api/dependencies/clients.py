# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Client dependencies for FastAPI routes."""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import Depends, HTTPException, Request, WebSocket

from app.clients.base import BaseClient
from app.clients.bedrock.client import BedrockClient
from app.clients.bedrock_runtime.client import BedrockRuntimeClient
from app.clients.dynamodb.client import DynamoDBClient
from app.clients.registry import ClientRegistry
from app.clients.s3.client import S3Client
from app.clients.valkey.client import ValkeyClient

# from app.clients.opensearch.client import OpenSearchClient
# from app.clients.bedrock_knowledge_base.client import BedrockKnowledgeBaseClient


T = TypeVar('T', bound=BaseClient)


def _get_client_registry_from_state(state) -> ClientRegistry:
    """
    Get client registry from state with improved diagnostics.

    The registry should be properly initialized by the lifespan context manager
    before any requests are processed. If it's not available, this indicates
    a serious application initialization problem.
    """
    from loguru import logger

    if not hasattr(state, 'client_registry'):
        # More detailed diagnostics
        available_attrs = dir(state)
        logger.critical(
            'Client registry attribute not found in application state. '
            'This indicates the application was not properly initialized. '
            f'Available state attributes: {available_attrs}'
        )
        raise RuntimeError(
            'Service unavailable: Application not properly initialized (missing client_registry attribute)'
        )

    registry = state.client_registry
    if registry is None:
        # More detailed diagnostics
        logger.critical(
            'Client registry is None in application state. '
            'This indicates the application was partially initialized but the registry was not set properly.'
        )
        raise RuntimeError(
            'Service unavailable: Application not properly initialized (client_registry is None)'
        )

    return registry


def get_client_registry(request: Request) -> ClientRegistry:
    """Get client registry from request state."""
    try:
        return _get_client_registry_from_state(request.app.state)
    except RuntimeError as e:
        from fastapi import HTTPException

        # Convert to HTTPException for HTTP routes
        raise HTTPException(status_code=503, detail=str(e)) from e


async def get_client_registry_ws(websocket: WebSocket) -> ClientRegistry:
    """Get client registry from websocket state."""
    # Just get the registry - the WebSocket handler will handle any exceptions
    from loguru import logger

    logger.debug('Getting client registry from WebSocket app state')
    registry = _get_client_registry_from_state(websocket.app.state)
    logger.debug(
        f'Successfully retrieved client registry with {len(registry.get_client_names())} clients'
    )
    return registry


def get_client(
    client_name: str, required: bool = True
) -> Callable[[ClientRegistry], Awaitable[tuple[BaseClient | None, bool]]]:
    """
    Create a dependency for accessing a specific client with availability status.

    Args:
        client_name: The name of the client to retrieve
        required: If True, will raise HTTP 503 when client is unavailable

    Returns:
        A callable that returns a tuple of (client, is_available)
    """

    async def _get_client(
        registry: ClientRegistry = Depends(get_client_registry),
    ) -> tuple[BaseClient | None, bool]:
        client, available = await registry.get_client(client_name)

        if required and (client is None or not available):
            raise HTTPException(
                status_code=503, detail=f'Required client {client_name} is unavailable'
            )

        return client, available

    return _get_client


def get_typed_client(
    client_name: str, client_type: type[T], required: bool = True
) -> Callable[[ClientRegistry], Awaitable[tuple[T | None, bool]]]:
    """
    Create a dependency for accessing a specific client with type checking and availability status.

    Args:
        client_name: The name of the client to retrieve
        client_type: The expected type of the client
        required: If True, will raise HTTP 503 when client is unavailable

    Returns:
        A callable that returns a tuple of (client, is_available)
    """

    async def _get_typed_client(
        registry: ClientRegistry = Depends(get_client_registry),
    ) -> tuple[T | None, bool]:
        client, available = await registry.get_typed_client(client_name, client_type)

        if required and (client is None or not available):
            raise HTTPException(
                status_code=503, detail=f'Required client {client_name} is unavailable'
            )

        return client, available

    return _get_typed_client


def get_client_required(
    client_name: str,
) -> Callable[[ClientRegistry], Awaitable[BaseClient]]:
    """
    Create a dependency for accessing a specific client, failing if unavailable.

    This is a convenience wrapper that only returns the client if available,
    raising HTTP 503 otherwise.
    """

    async def _get_client_required(
        registry: ClientRegistry = Depends(get_client_registry),
    ) -> BaseClient:
        client, available = await registry.get_client(client_name)

        if client is None or not available:
            raise HTTPException(
                status_code=503, detail=f'Required client {client_name} is unavailable'
            )

        return client

    return _get_client_required


def get_typed_client_required(
    client_name: str,
    client_type: type[T],
) -> Callable[[ClientRegistry], Awaitable[T]]:
    """
    Create a dependency for accessing a specific typed client, failing if unavailable.

    This is a convenience wrapper that only returns the client if available,
    raising HTTP 503 otherwise.
    """

    async def _get_typed_client_required(
        registry: ClientRegistry = Depends(get_client_registry),
    ) -> T:
        client, available = await registry.get_typed_client(client_name, client_type)

        if client is None or not available:
            raise HTTPException(
                status_code=503,
                detail=f'Required client {client_name} of type {client_type.__name__} is unavailable',
            )

        return client

    return _get_typed_client_required


def get_dynamodb_client(
    required: bool = True,
) -> Callable[[ClientRegistry], Awaitable[tuple[DynamoDBClient | None, bool]]]:
    """Get DynamoDB client with availability status."""
    from app.clients.dynamodb.client import DynamoDBClient

    return get_typed_client('dynamodb', DynamoDBClient, required)


def get_dynamodb_client_required() -> Callable[
    [ClientRegistry], Awaitable[DynamoDBClient]
]:
    """Get DynamoDB client, failing if unavailable."""
    from app.clients.dynamodb.client import DynamoDBClient

    return get_typed_client_required('dynamodb', DynamoDBClient)


def get_s3_client(
    required: bool = True,
) -> Callable[[ClientRegistry], Awaitable[tuple[S3Client | None, bool]]]:
    """Get S3 client with availability status."""
    from app.clients.s3.client import S3Client

    return get_typed_client('s3', S3Client, required)


def get_s3_client_required() -> Callable[[ClientRegistry], Awaitable[S3Client]]:
    """Get S3 client, failing if unavailable."""
    from app.clients.s3.client import S3Client

    return get_typed_client_required('s3', S3Client)


def get_valkey_client(
    required: bool = True,
) -> Callable[[ClientRegistry], Awaitable[tuple[ValkeyClient | None, bool]]]:
    """Get Valkey client with availability status."""
    from app.clients.valkey.client import ValkeyClient

    return get_typed_client('valkey', ValkeyClient, required)


def get_valkey_client_required() -> Callable[[ClientRegistry], Awaitable[ValkeyClient]]:
    """Get Valkey client, failing if unavailable."""
    from app.clients.valkey.client import ValkeyClient

    return get_typed_client_required('valkey', ValkeyClient)


def get_bedrock_client(
    required: bool = True,
) -> Callable[[ClientRegistry], Awaitable[tuple[BedrockClient | None, bool]]]:
    """Get Bedrock client with availability status."""
    from app.clients.bedrock.client import BedrockClient

    return get_typed_client('bedrock', BedrockClient, required)


def get_bedrock_client_required() -> Callable[
    [ClientRegistry], Awaitable[BedrockClient]
]:
    """Get Bedrock client, failing if unavailable."""
    from app.clients.bedrock.client import BedrockClient

    return get_typed_client_required('bedrock', BedrockClient)


def get_bedrock_runtime_client(
    required: bool = True,
) -> Callable[[ClientRegistry], Awaitable[tuple[BedrockRuntimeClient | None, bool]]]:
    """Get Bedrock runtime client with availability status."""
    from app.clients.bedrock_runtime.client import BedrockRuntimeClient

    return get_typed_client('bedrock_runtime', BedrockRuntimeClient, required)


def get_bedrock_runtime_client_required() -> Callable[
    [ClientRegistry], Awaitable[BedrockRuntimeClient]
]:
    """Get Bedrock runtime client, failing if unavailable."""
    from app.clients.bedrock_runtime.client import BedrockRuntimeClient

    return get_typed_client_required('bedrock_runtime', BedrockRuntimeClient)


# def get_opensearch_client() -> Annotated[OpenSearchClient, Depends]:
#     """Get OpenSearch client."""
#     from app.clients.opensearch.client import OpenSearchClient
#     return Depends(get_typed_client("opensearch", OpenSearchClient))


# def get_bedrock_kb_client() -> Annotated[BedrockKnowledgeBaseClient, Depends]:
#     """Get Bedrock Knowledge Base client."""
#     from app.clients.bedrock_knowledge_base.client import BedrockKnowledgeBaseClient
#     return Depends(get_typed_client("bedrock_kb", BedrockKnowledgeBaseClient))
