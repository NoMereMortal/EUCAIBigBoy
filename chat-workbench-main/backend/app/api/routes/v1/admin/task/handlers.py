# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Handlers for task handler configuration API."""

from fastapi import HTTPException, status
from loguru import logger

from app.repositories.task_handler_metadata import TaskHandlerConfigRepository
from app.task_handlers.models import (
    ListTaskHandlers,
    TaskHandlerConfig,
    TaskHandlerInfo,
)


async def list_task_handlers(
    config_repo: TaskHandlerConfigRepository,
) -> ListTaskHandlers:
    """List all task handlers"""
    try:
        return await config_repo.list_metadata()

    except Exception as e:
        logger.error(f'Error listing task handlers: {e}')
        raise


async def get_task_handler(
    name: str,
    config_repo: TaskHandlerConfigRepository,
) -> TaskHandlerInfo:
    """Get task handler configuration"""
    try:
        config = await config_repo.get_metadata(name)
        if config is None:
            raise ValueError(f'Task handler {name} not found')
        return config

    except Exception as e:
        logger.error(f'Error getting task handler {name}: {e}')
        raise


async def update_task_handler(
    name: str,
    config: TaskHandlerConfig,
    config_repo: TaskHandlerConfigRepository,
) -> TaskHandlerInfo:
    """Update task handler configuration"""
    try:
        # Save updated configuration
        return await config_repo.update_metadata(name, config)

    except ValueError as e:
        logger.error(f'Error updating task handler {name}: {e}')
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    except Exception as e:
        logger.error(f'Error updating task handler {name}: {e}')
        raise
