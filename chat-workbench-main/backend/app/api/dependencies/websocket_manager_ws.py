# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from typing import Any

from fastapi import WebSocket
from loguru import logger


async def get_websocket_manager_ws(websocket: WebSocket) -> Any:
    """Get websocket manager from app state for WebSocket."""
    logger.debug('Getting websocket manager from WebSocket app state')

    if not hasattr(websocket.app.state, 'websocket_manager'):
        raise RuntimeError('Websocket manager not initialized in WebSocket app state')

    websocket_manager = websocket.app.state.websocket_manager
    logger.debug('Successfully retrieved websocket manager from app state')
    return websocket_manager
