# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Task handler endpoints for public use."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_auth_dependency, get_task_handler_registry
from app.task_handlers.registry import TaskHandlerRegistry

router = APIRouter(
    tags=['task-handlers'], prefix='/task-handlers', dependencies=get_auth_dependency()
)


@router.get('/')
async def list_task_handlers(
    request: Request,
    registry: Annotated[TaskHandlerRegistry, Depends(get_task_handler_registry)],
):
    """List all available task handlers."""
    handler_info = await registry.handler_info()

    # Add is_default field - assume 'chat' is default
    for handler in handler_info:
        handler['is_default'] = handler['name'] == 'chat'

    return {'handlers': handler_info}
