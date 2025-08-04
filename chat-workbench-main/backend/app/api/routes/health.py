# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Health check endpoints for the API."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel

from app.api.dependencies import get_client_registry
from app.clients.registry import ClientRegistry


class ClientHealth(BaseModel):
    """Health information for a single client."""

    available: bool
    type: str
    error: str | None = None


class ServiceHealth(BaseModel):
    """Health information for a service."""

    status: Literal['healthy', 'degraded', 'critical']
    timestamp: str
    clients: dict[str, ClientHealth]
    version: str = '1.0.0'


router = APIRouter(tags=['Health'])


@router.get('/health')
async def check_health(
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry)],
) -> ServiceHealth:
    """
    Check the health of all system components.

    Returns health status of all registered clients and overall system status:
    - healthy: All critical clients are available
    - degraded: Some non-critical clients are unavailable
    - critical: Critical clients are unavailable
    """
    client_info = client_registry.client_info()

    # Organize client health by client name
    client_health = {}
    for info in client_info:
        client_health[info.get('name', 'unknown')] = ClientHealth(
            available=info.get('initialized', False),
            type=info.get('type', 'Unknown'),
            error=info.get('error', None),
        )

    # Define which clients are critical for the application
    critical_clients = ['dynamodb', 'valkey']

    # Determine overall status
    critical_available = all(
        client_health.get(name, ClientHealth(available=False, type='Missing')).available
        for name in critical_clients
        if name in client_health
    )

    status = 'healthy'
    if not critical_available:
        status = 'critical'
        logger.warning('Health check: CRITICAL - Some critical clients are unavailable')
    elif any(not info.available for info in client_health.values()):
        status = 'degraded'
        logger.warning(
            'Health check: DEGRADED - Some non-critical clients are unavailable'
        )
    else:
        logger.info('Health check: HEALTHY - All clients are available')

    return ServiceHealth(
        status=status,
        timestamp=datetime.now().isoformat(),
        clients=client_health,
    )
