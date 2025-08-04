# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Metrics endpoints."""

import prometheus_client
from fastapi import APIRouter, Request, Response

from app.api.dependencies.auth import public_route

router = APIRouter(tags=['system'])


@router.get('/metrics')
@public_route()
async def metrics(request: Request) -> Response:
    """Prometheus metrics endpoint."""
    registry = getattr(
        request.app.state, 'prometheus_registry', prometheus_client.REGISTRY
    )

    # Generate metrics output
    metrics_data = prometheus_client.generate_latest(registry)

    return Response(
        content=metrics_data,
        media_type='text/plain',
    )
