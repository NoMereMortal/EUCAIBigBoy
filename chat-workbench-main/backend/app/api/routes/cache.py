# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Cache management routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_valkey_client
from app.clients.valkey.client import ValkeyClient

router = APIRouter(
    prefix='/cache',
    tags=['system'],
)


@router.get('/stats')
async def cache_stats(
    valkey_client: Annotated[ValkeyClient, Depends(get_valkey_client())],
) -> dict[str, Any]:
    """Get cache statistics."""
    if not valkey_client or not valkey_client._client:
        return {'status': 'unavailable'}

    try:
        info = await valkey_client._client.info()
        stats = {
            'status': 'available',
            'used_memory': info.get('used_memory', 'unknown'),
            'connected_clients': info.get('connected_clients', 'unknown'),
            'uptime_in_seconds': info.get('uptime_in_seconds', 'unknown'),
        }
        return stats
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@router.post('/flush')
async def flush_cache(
    valkey_client: Annotated[ValkeyClient, Depends(get_valkey_client())],
) -> dict[str, Any]:
    """Flush the cache."""
    if not valkey_client or not valkey_client._client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Cache service unavailable',
        )

    try:
        await valkey_client._client.flushdb()
        return {'status': 'success'}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to flush cache: {e!s}',
        ) from e
