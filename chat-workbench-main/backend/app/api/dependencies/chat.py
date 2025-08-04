# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from typing import Any

from fastapi import Request, WebSocket
from loguru import logger

from app.services.chat import ChatService
from app.task_handlers.registry import TaskHandlerRegistry


async def get_task_handler_registry(request: Request) -> TaskHandlerRegistry:
    """Get task handler registry from app state."""
    if not hasattr(request.app.state, 'task_handler_registry'):
        raise RuntimeError('Task handler registry not initialized')

    return request.app.state.task_handler_registry


async def get_task_handler_registry_ws(websocket: WebSocket) -> TaskHandlerRegistry:
    """Get task handler registry from app state for WebSocket."""
    logger.debug('Getting task handler registry from WebSocket app state')

    if not hasattr(websocket.app.state, 'task_handler_registry'):
        raise RuntimeError(
            'Task handler registry not initialized in WebSocket app state'
        )

    registry = websocket.app.state.task_handler_registry

    # Log available handlers for debugging
    handler_names = await registry.get_handler_names()
    logger.debug(
        f'Task handler registry has {len(handler_names)} handlers: {handler_names}'
    )

    return registry


def get_websocket_manager(request: Request) -> Any:
    """Get websocket manager from app state."""
    if not hasattr(request.app.state, 'websocket_manager'):
        raise RuntimeError('Websocket manager not initialized')
    return request.app.state.websocket_manager


async def get_websocket_manager_ws(websocket: WebSocket) -> Any:
    """Import and use the standalone websocket manager dependency."""
    from app.api.dependencies.websocket_manager_ws import (
        get_websocket_manager_ws as standalone_get_ws_mgr,
    )

    return await standalone_get_ws_mgr(websocket)


def get_chat_service(request: Request) -> ChatService:
    """Get chat service from app state."""
    if not hasattr(request.app.state, 'chat_service'):
        raise RuntimeError('Chat service not initialized')
    return request.app.state.chat_service


async def get_chat_service_ws(websocket: WebSocket) -> ChatService:
    """Get chat service from app state for WebSocket."""
    logger.debug('Getting chat service from WebSocket app state')

    if not hasattr(websocket.app.state, 'chat_service'):
        raise RuntimeError('Chat service not initialized in WebSocket app state')

    chat_service = websocket.app.state.chat_service
    logger.debug(
        f'Retrieved chat service from WebSocket app state: {chat_service.__class__.__name__}'
    )

    return chat_service
