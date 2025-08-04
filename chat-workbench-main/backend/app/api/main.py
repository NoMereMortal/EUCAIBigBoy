# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Application entry point."""

import os

import uvicorn
from loguru import logger

from app.api.app import create_app
from app.config import get_settings

# Create the application
logger.info('Starting application creation')
app = create_app()

# Diagnostic logging to verify app.state
logger.info(f'Application created with app.state attributes: {dir(app.state)}')
logger.info(f'Application state class: {app.state.__class__.__name__}')

# Verify if client_registry is available
if hasattr(app.state, 'client_registry'):
    logger.info(
        f'client_registry is available: {app.state.client_registry is not None}'
    )
    if app.state.client_registry is not None:
        client_names = app.state.client_registry.get_client_names()
        logger.info(f'client_registry contains clients: {client_names}')
else:
    logger.critical('client_registry attribute not found in app.state')

# Verify other critical components with more details
for attr in [
    'valkey_client',
    'chat_service',
    'task_handler_registry',
    'websocket_manager',
]:
    if hasattr(app.state, attr):
        value = getattr(app.state, attr)
        logger.info(f'{attr} is available: {value is not None}')
        if value is not None:
            logger.info(f'{attr} type: {type(value).__name__}')
    else:
        logger.warning(f'{attr} attribute not found in app.state')

# Check for the presence of rate_limit_config (should be removed)
if hasattr(app.state, 'rate_limit_config'):
    logger.warning(
        'rate_limit_config still present in app.state - this should be removed'
    )

if __name__ == '__main__':
    settings = get_settings()

    # Check for hot reload environment variable
    hot_reload = os.environ.get('HOT_RELOAD', 'false').lower() == 'true'

    # Determine number of workers - for hot reload, default to 1 worker to avoid state issues
    workers = int(os.environ.get('WORKERS', '1' if hot_reload else '0'))

    if hot_reload:
        logger.info(
            'Hot reload enabled - server will automatically restart when files change'
        )
        if workers > 1:
            logger.warning(
                f'Hot reload with multiple workers ({workers}) may cause state inconsistency issues'
            )

    if workers > 0:
        logger.info(f'Running with {workers} worker processes')
    else:
        logger.info('Running with default number of workers (based on CPU cores)')

    # Determine log level based on environment
    log_level = os.environ.get('LOG_LEVEL', 'info').lower()

    uvicorn.run(
        'app.api.main:app',
        host=settings.api.host,
        port=settings.api.port,
        reload=hot_reload,  # Enable hot reload based on env var
        reload_dirs=['app'],  # Only watch the app directory for changes
        workers=workers
        if workers > 0
        else None,  # Use specified workers or default to CPU count
        log_level=log_level,  # Use configurable log level
    )
