# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""API endpoints for guardrail management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.dependencies.clients import get_bedrock_client
from app.api.routes.v1.admin.guardrail.handlers import (
    create_guardrail,
    create_guardrail_version,
    delete_guardrail,
    get_guardrail,
    list_guardrails,
    update_guardrail,
)
from app.api.routes.v1.admin.guardrail.models import (
    GuardrailCreate,
    GuardrailDetail,
    GuardrailInfo,
    GuardrailUpdate,
    GuardrailVersion,
)
from app.clients.bedrock.client import BedrockClient

router = APIRouter(tags=['admin', 'guardrail'])


@router.get(
    '/',
    summary='List all guardrails',
    description='Returns a list of all guardrails.',
)
async def get_guardrails(
    client: Annotated[BedrockClient, Depends(get_bedrock_client())],
) -> list[GuardrailInfo]:
    """List all guardrails."""
    try:
        return await list_guardrails(client)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to list guardrails: {e!s}',
        ) from e


@router.post(
    '/',
    status_code=status.HTTP_201_CREATED,
    summary='Create a new guardrail',
    description='Creates a new guardrail with the provided configuration.',
)
async def create_new_guardrail(
    guardrail: GuardrailCreate,
    client: Annotated[BedrockClient, Depends(get_bedrock_client())],
) -> GuardrailInfo:
    """Create a new guardrail."""
    try:
        return await create_guardrail(client, guardrail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to create guardrail: {e!s}',
        ) from e


@router.get(
    '/{guardrail_id}',
    summary='Get guardrail details',
    description='Returns detailed information about a specific guardrail.',
)
async def get_guardrail_details(
    client: Annotated[BedrockClient, Depends(get_bedrock_client())],
    guardrail_id: Annotated[str, Path(description='The ID of the guardrail')],
    guardrail_version: str | None = None,
) -> GuardrailDetail:
    """Get guardrail details."""
    try:
        return await get_guardrail(client, guardrail_id, guardrail_version)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Guardrail not found or error retrieving guardrail: {e!s}',
        ) from e


@router.put(
    '/{guardrail_id}',
    summary='Update a guardrail',
    description='Updates an existing guardrail with the provided configuration.',
)
async def update_existing_guardrail(
    guardrail: GuardrailUpdate,
    client: Annotated[BedrockClient, Depends(get_bedrock_client())],
    guardrail_id: Annotated[str, Path(description='The ID of the guardrail to update')],
) -> GuardrailInfo:
    """Update an existing guardrail."""
    try:
        return await update_guardrail(client, guardrail_id, guardrail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to update guardrail: {e!s}',
        ) from e


@router.delete(
    '/{guardrail_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Delete a guardrail',
    description='Deletes a guardrail.',
)
async def delete_existing_guardrail(
    client: Annotated[BedrockClient, Depends(get_bedrock_client())],
    guardrail_id: Annotated[str, Path(description='The ID of the guardrail to delete')],
) -> None:
    """Delete a guardrail."""
    try:
        await delete_guardrail(client, guardrail_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to delete guardrail: {e!s}',
        ) from e


@router.post(
    '/{guardrail_id}/publish',
    summary='Publish a guardrail version',
    description='Publishes a guardrail draft as a new version.',
)
async def publish_guardrail_version(
    client: Annotated[BedrockClient, Depends(get_bedrock_client())],
    guardrail_id: Annotated[
        str, Path(description='The ID of the guardrail to publish')
    ],
    description: str | None = None,
) -> GuardrailVersion:
    """Publish a guardrail version."""
    try:
        return await create_guardrail_version(client, guardrail_id, description)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to publish guardrail: {e!s}',
        ) from e
