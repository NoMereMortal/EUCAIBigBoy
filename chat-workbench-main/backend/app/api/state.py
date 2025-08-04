# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Application state management."""

import os
import time
from typing import Any, Optional

from fastapi import FastAPI
from loguru import logger
from starlette.datastructures import State as StarletteState

from app.clients.dynamodb.client import DynamoDBClient
from app.clients.registry import ClientRegistry
from app.config import Settings, get_settings
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.services.chat import ChatService
from app.task_handlers.registry import TaskHandlerRegistry, initialize_task_handlers
from app.tracing import setup_tracing


class ApplicationState(StarletteState):
    """
    Extended State class with custom attributes for type checking and proper initialization.

    FastAPI's Starlette framework uses a dynamic approach for state attributes,
    allowing arbitrary attributes to be set on the state object. PyRefly's static
    type checker requires these attributes to be defined.

    This class defines the expected attributes as class attributes with initial values
    to satisfy the static type checker, and ensures they are properly initialized.
    """

    # Define all expected attributes with "Any" type to allow any value
    client_registry: Any = None
    valkey_client: Any = None
    # rate_limit_config removed - now using direct valkey_client access instead
    chat_service: Any = None
    task_handler_registry: Any = None
    # Additional attributes that might be used elsewhere
    websocket_manager: Any = None
    # Flag to indicate whether initialization is complete
    fully_initialized: bool = False

    def __init__(self):
        """Initialize internal state with properly typed values"""
        super().__init__()
        # Initialize all typed attributes explicitly
        # This ensures the state dictionary is properly set up
        object.__setattr__(self, 'client_registry', None)
        object.__setattr__(self, 'valkey_client', None)
        # rate_limit_config removed - now using direct valkey_client access
        object.__setattr__(self, 'chat_service', None)
        object.__setattr__(self, 'task_handler_registry', None)
        object.__setattr__(self, 'websocket_manager', None)
        object.__setattr__(self, 'fully_initialized', False)


class DynamoDBClientNotInitializedError(RuntimeError):
    """Error raised when DynamoDB client is not initialized."""

    def __init__(self) -> None:
        super().__init__('DynamoDB client not initialized')


class ClientRegistryInitializationError(RuntimeError):
    """Error raised when client registry failed to initialize."""

    def __init__(self, message: str = 'Client registry failed to initialize') -> None:
        super().__init__(message)


async def init_dependent_services(app: FastAPI, settings: Settings) -> None:
    """
    Initialize dependent services after clients are ready.

    This separates the client initialization from the service initialization
    to make the process more deterministic and avoid circular dependencies.
    """
    if not hasattr(app.state, 'client_registry'):
        logger.critical(
            'Cannot initialize services: client_registry attribute not in app.state'
        )
        # Instead of silently returning, raise an exception to prevent partial initialization
        raise RuntimeError(
            'Application initialization failed: client registry attribute not in app.state'
        )

    client_registry = app.state.client_registry
    if not client_registry:
        logger.critical('Cannot initialize services: client registry is None')
        # Instead of silently returning, raise an exception to prevent partial initialization
        raise RuntimeError('Application initialization failed: client registry is None')

    # Initialize DynamoDB tables if we're using a local endpoint
    dynamodb_client, is_available = await client_registry.get_typed_client(
        'dynamodb', DynamoDBClient
    )
    if dynamodb_client and is_available and settings.dynamodb.endpoint_url is not None:
        try:
            logger.info('Local DynamoDB endpoint detected - ensuring tables exist...')
            await dynamodb_client.create_tables()
            logger.info('DynamoDB tables ready')
        except Exception as e:
            logger.error(f'Failed to initialize DynamoDB tables: {e}')

    # Store the Valkey client directly in app state for middleware access
    valkey_client, valkey_available = await client_registry.get_client('valkey')

    # Enhanced debugging for Valkey client
    logger.info(
        f'Valkey client obtained: type={type(valkey_client)}, available={valkey_available}'
    )

    # Store the client directly in app state for middleware access using direct attribute assignment
    object.__setattr__(app.state, 'valkey_client', valkey_client)

    # Verify the client was stored correctly
    stored_client = getattr(app.state, 'valkey_client', None)
    logger.info(f'Valkey client stored in app.state: {stored_client is not None}')

    # Log if rate limiting will be disabled due to client unavailability
    if settings.rate_limit.enabled and (valkey_client is None or not valkey_available):
        logger.warning('Valkey client not available - rate limiting will be disabled')

    # No need to store rate limit configuration in app state anymore
    # The middleware will directly access valkey_client from app.state

    # Log that initialization of rate limiting is complete
    logger.info('Rate limiting configuration complete')

    # Initialize chat service
    if dynamodb_client and is_available:
        try:
            message_repo = MessageRepository(dynamodb_client)
            chat_repo = ChatRepository(dynamodb_client)
            chat_service = ChatService(message_repo=message_repo, chat_repo=chat_repo)

            # Store in app state using object.__setattr__ for more reliable attribute assignment
            object.__setattr__(app.state, 'chat_service', chat_service)

            # Verify it was set correctly
            stored_service = getattr(app.state, 'chat_service', None)
            if stored_service is None:
                logger.error('Failed to store chat_service in app.state')
                raise RuntimeError('Failed to store chat_service in app.state')

            logger.info('Chat service initialized and stored in app state')
        except Exception as e:
            logger.error(f'Failed to initialize chat service: {e}')
            raise RuntimeError(f'Failed to initialize chat service: {e!s}') from e
    else:
        logger.error('Cannot initialize chat service - DynamoDB client not available')
        raise RuntimeError(
            'Cannot initialize chat service - DynamoDB client not available'
        )

    # Initialize task handler registry with handlers
    # This ensures each worker process has its own complete set of task handlers
    logger.info('Initializing task handler registry in worker process')
    try:
        # Create registry without Valkey
        task_registry = TaskHandlerRegistry()

        # Initialize with available clients
        await initialize_task_handlers(settings, task_registry, client_registry)

        # Store in app state using object.__setattr__ for more reliable attribute assignment
        object.__setattr__(app.state, 'task_handler_registry', task_registry)

        # Verify it was set correctly
        stored_registry = getattr(app.state, 'task_handler_registry', None)
        if stored_registry is None:
            logger.error('Failed to store task_handler_registry in app.state')
            raise RuntimeError('Failed to store task_handler_registry in app.state')

        # Log available handlers
        handler_names = await task_registry.get_handler_names()
        logger.info(
            f'Task handler registry initialized with {len(handler_names)} handlers: {handler_names}'
        )
    except Exception as e:
        logger.error(f'Failed to initialize task handler registry: {e}')
        # Raise here since this is a critical service
        raise RuntimeError(f'Failed to initialize task handler registry: {e!s}') from e

    # Initialize WebSocketManager
    logger.info('Initializing WebSocket manager in worker process')
    try:
        # Valkey client is required for streaming service and WebSocketManager
        if not valkey_client or not valkey_available:
            logger.error(
                'Cannot initialize streaming service and websocket manager: Valkey client not available'
            )
            raise RuntimeError(
                'Cannot initialize streaming service: Valkey client not available'
            )

        # Create streaming service with Valkey
        from app.services.streaming import StreamingService

        # We now ensure valkey_client is not None when passed here
        streaming_service = StreamingService(valkey_client)

        # Create WebSocket manager
        from app.api.websocket import WebSocketManager

        websocket_manager = WebSocketManager(streaming_service, valkey_client)

        # Store in app state using object.__setattr__ for more reliable attribute assignment
        object.__setattr__(app.state, 'websocket_manager', websocket_manager)

        # Verify it was set correctly
        stored_manager = getattr(app.state, 'websocket_manager', None)
        if stored_manager is None:
            logger.error('Failed to store websocket_manager in app.state')
            raise RuntimeError('Failed to store websocket_manager in app.state')

        logger.info('WebSocket manager initialized and stored in app state')
    except Exception as e:
        logger.error(f'Failed to initialize WebSocket manager: {e}')
        # Raise here since this is a critical service
        raise RuntimeError(f'Failed to initialize WebSocket manager: {e!s}') from e


async def init_app_state(app: FastAPI) -> None:
    """Initialize application state in a deterministic, sequential order."""
    worker_id = os.getpid()
    start_time = time.time()
    logger.info(f'Worker {worker_id}: Starting application initialization')

    # Ensure we have the proper state class
    if not isinstance(app.state, ApplicationState):
        app.state = ApplicationState()

    settings = get_settings()

    # Initialize tracing if enabled
    try:
        console_export = os.environ.get('OTEL_DEBUG', 'false').lower() == 'true'
        setup_tracing(console_export=console_export)
        logger.info('OpenTelemetry tracing initialized during app state initialization')
    except Exception as e:
        logger.error(f'Failed to initialize OpenTelemetry tracing: {e}')
        logger.warning('Application will continue without tracing')

    # 1. Create the client registry - core component everything depends on
    logger.info('Creating client registry')
    client_registry = ClientRegistry(settings)

    # Use explicit object.__setattr__ to ensure attribute is set at the instance level
    object.__setattr__(app.state, 'client_registry', client_registry)

    # VERIFICATION STEP: Verify client registry is available in app.state
    if not hasattr(app.state, 'client_registry') or app.state.client_registry is None:
        logger.critical('Client registry not properly set in app.state')
        raise RuntimeError('Application initialization failed: client registry not set')

    # 2. Setup the registry with all client containers
    logger.info('Setting up client containers')
    await client_registry.setup()

    # 3. Initialize critical clients in sequence to avoid race conditions
    logger.info('Initializing critical clients in sequence')
    critical_clients = ['dynamodb', 'valkey', 's3']

    for name in critical_clients:
        try:
            success = await client_registry.initialize_client(name)
            if success:
                logger.info(f'Successfully initialized critical client: {name}')
            else:
                logger.warning(f'Failed to initialize critical client: {name}')
        except Exception as e:
            logger.error(f'Error initializing critical client {name}: {e}')

    # 4. Initialize remaining clients concurrently
    logger.info('Initializing remaining clients')
    await client_registry.initialize_all()

    # VERIFICATION STEP: Verify client registry is still available before dependent services
    if not hasattr(app.state, 'client_registry') or app.state.client_registry is None:
        logger.critical(
            'Client registry lost from app.state before dependent services initialization'
        )
        raise RuntimeError('Application initialization failed: client registry lost')

    # 5. Initialize dependent services using the now-initialized clients
    logger.info('Initializing dependent services')
    await init_dependent_services(app, settings)

    # 6. Log initialization completion
    logger.info(
        f'Worker {worker_id}: Application initialization complete in {time.time() - start_time:.2f}s'
    )

    # 7. Mark this worker as ready - this will also set fully_initialized flag
    await mark_worker_ready(app)
    logger.info(f'Worker {worker_id}: Marked as ready to handle requests')


# We no longer need the init_app_state_sync function - initialization
# is now fully handled by the lifespan context manager


async def mark_worker_ready(app: FastAPI) -> None:
    """Mark the current worker as ready and set in app state."""
    worker_id = os.getpid()
    logger.info(
        f'Worker {worker_id}: Verifying critical services before marking as ready'
    )

    # List of critical services to check
    critical_services = [
        ('client_registry', 'Client registry'),
        ('valkey_client', 'Valkey client'),
        ('task_handler_registry', 'Task handler registry'),
        ('chat_service', 'Chat service'),
        ('websocket_manager', 'WebSocket manager'),
    ]

    # Check if all critical services are available
    missing_services = []
    for attr_name, service_name in critical_services:
        service = getattr(app.state, attr_name, None)
        if service is None:
            missing_services.append(service_name)
            logger.error(
                f'Worker {worker_id}: Critical service missing: {service_name}'
            )

    if missing_services:
        logger.error(
            f'Worker {worker_id}: Cannot mark as ready - missing critical services: {", ".join(missing_services)}'
        )
        return  # Don't mark as ready

    logger.info(f'Worker {worker_id}: All critical services verified')

    if not hasattr(app.state, '_ready_workers'):
        # Initialize the set of ready workers if it doesn't exist
        object.__setattr__(app.state, '_ready_workers', set())

    # Add this worker to the set of ready workers
    app.state._ready_workers.add(worker_id)

    # Ensure fully_initialized flag is synchronized with worker readiness
    object.__setattr__(app.state, 'fully_initialized', True)

    logger.info(
        f'Worker {worker_id}: Added to ready workers set: {app.state._ready_workers}'
    )
    logger.info(f'Worker {worker_id}: fully_initialized flag set to True')


async def check_worker_ready(app: FastAPI, request_path: Optional[str] = None) -> bool:
    """
    Check if the current worker is ready to handle requests.
    Returns True if the worker is ready, False otherwise.
    """
    worker_id = os.getpid()

    # Always allow health checks
    if request_path and request_path.startswith(('/health', '/api/metrics')):
        return True

    # Check if this worker is in the ready set
    ready = (
        hasattr(app.state, '_ready_workers') and worker_id in app.state._ready_workers
    )

    if not ready:
        logger.warning(
            f'Worker {worker_id}: Not ready to handle requests to {request_path}'
        )

    return ready


async def cleanup_app_state(app: FastAPI) -> None:
    """Clean up application state."""
    worker_id = os.getpid()

    # Clean up client registry
    if hasattr(app.state, 'client_registry') and app.state.client_registry is not None:
        try:
            await app.state.client_registry.cleanup_all()
        except Exception as e:
            logger.error(f'Error during client registry cleanup: {e}')
    else:
        logger.warning('Client registry not found or None during cleanup')

    # Remove this worker from the ready set if it exists
    if hasattr(app.state, '_ready_workers') and worker_id in app.state._ready_workers:
        app.state._ready_workers.remove(worker_id)
        logger.info(f'Worker {worker_id}: Removed from ready workers set')

    logger.info(f'Worker {worker_id}: Application state cleaned up')
