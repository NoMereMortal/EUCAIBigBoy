# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""FastAPI application setup."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.middleware import setup_basic_middleware
from app.api.middleware.rate_limiting import RateLimitingMiddleware
from app.api.routes import router
from app.api.state import cleanup_app_state, init_app_state
from app.config import get_settings
from app.tracing import instrument_fastapi, setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for the FastAPI application.

    This replaces the traditional startup/shutdown events with a modern contextmanager approach.
    It handles initialization and cleanup of all application resources.
    """
    import asyncio
    import os
    import secrets

    worker_id = os.getpid()
    logger.info(f'Worker {worker_id}: Starting application initialization')

    # Add a small staggered delay based on worker ID to prevent initialization race conditions
    # This helps ensure that workers don't all try to initialize critical resources at the same time
    delay = 0.1 + (
        secrets.randbelow(900) / 1000
    )  # Random delay between 0.1 and 1.0 seconds
    logger.debug(f'Worker {worker_id}: Staggered initialization delay of {delay:.2f}s')
    await asyncio.sleep(delay)

    # Initialize application state asynchronously
    await init_app_state(app)
    logger.info(f'Worker {worker_id}: Application fully initialized and ready')

    yield

    # Cleanup when application is shutting down
    logger.info(
        f'Worker {worker_id}: Application shutting down - cleaning up resources'
    )
    await cleanup_app_state(app)
    logger.info(
        f'Worker {worker_id}: Application shutdown complete - all resources cleaned up'
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app_config = settings.app
    api_version_prefix = f'/{settings.api_version}'

    # Conditionally disable docs in production
    is_prod = settings.environment.lower() == 'production'
    docs_url = '/api/docs' if not is_prod else None
    redoc_url = '/api/redoc' if not is_prod else None
    openapi_url = '/api/openapi.json' if not is_prod else None

    app = FastAPI(
        title=app_config.title,
        description=app_config.description,
        version=app_config.version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,  # This is the single source of truth for initialization
    )

    # Initialize app.state with empty values
    # The lifespan context manager will properly populate these
    from app.api.state import ApplicationState

    app.state = ApplicationState()

    # Set up basic middleware that doesn't require initialized clients
    setup_basic_middleware(app, settings)

    # Configure rate limiting middleware with settings values only
    # No client references in configuration - client access will be from app.state directly
    rate_limit_settings = {
        'rate_limit': settings.rate_limit.rate_limit,
        'window_size': settings.rate_limit.window_size,
        'fail_closed': settings.rate_limit.fail_closed,
        'enabled': settings.rate_limit.enabled,
        'exclude_paths': [
            # Exclude operational endpoints from rate limiting
            '/api/health',  # Unversioned health check
            '/api/metrics',  # Metrics endpoint
            # Docs URLs (conditionally available in non-prod)
            '/api/docs',
            '/api/redoc',
            '/api/openapi.json',
        ],
    }

    # Add rate limiting middleware - passes only configuration settings, no client references
    app.add_middleware(RateLimitingMiddleware, **rate_limit_settings)  # type: ignore
    logger.info('Rate limiting middleware registered with default configuration')

    # No need to register startup and shutdown events
    # as we're using the lifespan context manager instead

    # Add middleware to validate app state initialization
    @app.middleware('http')
    async def validate_app_initialized(request: Request, call_next):
        """Ensure the application is fully initialized before processing requests."""
        # Skip health checks and metrics even if not initialized
        if request.url.path.startswith(('/health', '/api/metrics')):
            return await call_next(request)

        # Import worker readiness check
        from app.api.state import check_worker_ready

        # For all other requests, check if this worker is ready
        worker_ready = await check_worker_ready(request.app, request.url.path)
        if not worker_ready:
            import os

            worker_id = os.getpid()
            logger.warning(
                f'Worker {worker_id}: Request to {request.url.path} rejected - worker not ready'
            )
            return JSONResponse(
                status_code=503,
                content={
                    'detail': 'Service initializing, please try again later',
                    'worker_id': worker_id,
                },
            )

        # Worker readiness check is sufficient - no need for global initialization check

        # Validate critical services are available - this shouldn't happen if fully_initialized is true
        # but added as an additional safeguard
        critical_services = [
            'client_registry',
            'task_handler_registry',
            'valkey_client',
        ]
        missing_services = [
            svc
            for svc in critical_services
            if not hasattr(request.app.state, svc)
            or getattr(request.app.state, svc) is None
        ]

        if missing_services:
            import os

            worker_id = os.getpid()
            logger.error(
                f'Worker {worker_id}: Critical services missing: {", ".join(missing_services)}'
            )
            return JSONResponse(
                status_code=500,
                content={
                    'detail': 'Application configuration error - missing required services',
                    'missing': missing_services,
                    'worker_id': worker_id,
                },
            )

        return await call_next(request)

    # Include health router behind /api prefix (unversioned)
    from app.api.routes.health import router as health_router

    app.include_router(health_router, prefix='/api')

    # Include system endpoints (metrics, cache) under /api (unversioned)
    from app.api.routes.cache import router as cache_router
    from app.api.routes.metrics import router as metrics_router

    app.include_router(metrics_router, prefix='/api')
    app.include_router(cache_router, prefix='/api')

    # Include main router with the /api/v1 prefix.
    # This will create endpoints like /api/v1/chats, /api/v1/generate, etc.
    app.include_router(router, prefix=f'/api{api_version_prefix}')

    # Initialize OpenTelemetry tracing
    try:
        # Get settings for tracing configuration
        console_export = os.environ.get('OTEL_DEBUG', 'false').lower() == 'true'

        # Set up tracing with the service name and OTLP endpoint from environment variables
        setup_tracing(console_export=console_export)

        # Instrument FastAPI
        instrument_fastapi(app)

        logger.info('OpenTelemetry tracing initialized')
    except Exception as e:
        logger.error(f'Failed to initialize OpenTelemetry tracing: {e}')
        logger.warning('Application will continue without tracing')

    return app
