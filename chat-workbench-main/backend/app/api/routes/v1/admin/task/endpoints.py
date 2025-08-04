# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""API endpoints for task handler metadata."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from app.api.dependencies import get_dynamodb_client
from app.api.routes.v1.admin.task.handlers import (
    get_task_handler,
    list_task_handlers,
    update_task_handler,
)
from app.clients.dynamodb.client import DynamoDBClient
from app.repositories.task_handler_metadata import TaskHandlerConfigRepository
from app.task_handlers.models import (
    ListTaskHandlers,
    TaskHandlerConfig,
    TaskHandlerInfo,
)

router = APIRouter(tags=['admin', 'task'])


def get_task_handler_metadata_repo(
    dynamodb_client: DynamoDBClient = Depends(get_dynamodb_client()),
) -> TaskHandlerConfigRepository:
    """Get task handler metadata repository."""
    return TaskHandlerConfigRepository(dynamodb_client)


@router.get(
    '/',
    summary='List all task handlers',
    description='Returns a list of all task handlers.',
)
async def get_task_handlers(
    request: Request,
    config_repo: Annotated[
        TaskHandlerConfigRepository, Depends(get_task_handler_metadata_repo)
    ],
) -> ListTaskHandlers:
    """List all task handlers."""
    try:
        return await list_task_handlers(config_repo)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to list task handlers: {e!s}',
        ) from e


@router.get(
    '/{name}',
    summary='Get task handler metadata',
    description='Returns metadata for a specific task handler.',
)
async def get_task_handler_metadata(
    request: Request,
    config_repo: Annotated[
        TaskHandlerConfigRepository, Depends(get_task_handler_metadata_repo)
    ],
    name: Annotated[str, Path(description='The name of the task handler')],
) -> TaskHandlerInfo:
    """Get task handler metadata."""
    try:
        return await get_task_handler(name, config_repo)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to get task handler metadata: {e!s}',
        ) from e


@router.put(
    '/{name}',
    summary='Update task handler metadata',
    description='Updates metadata for a specific task handler.',
)
async def update_task_handler_metadata(
    request: Request,
    config: TaskHandlerConfig,
    config_repo: Annotated[
        TaskHandlerConfigRepository, Depends(get_task_handler_metadata_repo)
    ],
    name: Annotated[str, Path(description='The name of the task handler')],
) -> TaskHandlerInfo:
    """Update task handler metadata."""
    try:
        return await update_task_handler(name, config, config_repo)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to update task handler metadata: {e!s}',
        ) from e
