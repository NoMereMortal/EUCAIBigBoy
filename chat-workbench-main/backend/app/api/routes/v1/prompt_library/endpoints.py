# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.clients import get_dynamodb_client
from app.api.routes.v1.prompt_library.handlers import (
    handle_create_prompt,
    handle_get_prompt,
    handle_list_prompts,
    handle_search_prompts,
    handle_update_prompt,
)
from app.api.routes.v1.prompt_library.models import (
    CreatePromptRequest,
    ListPromptsResponse,
    Prompt,
    UpdatePromptRequest,
)
from app.clients.dynamodb.client import DynamoDBClient
from app.repositories.prompt import PromptRepository

router = APIRouter(prefix='/prompt', tags=['prompt'])


def get_prompt_repository(
    dynamodb_client: DynamoDBClient = Depends(get_dynamodb_client()),
) -> PromptRepository:
    """Get prompt repository instance."""
    return PromptRepository(dynamodb_client)


@router.post('')
async def create_prompt(
    request: CreatePromptRequest,
    prompt_repo: Annotated[PromptRepository, Depends(get_prompt_repository)],
) -> Prompt:
    """Create a new prompt."""
    prompt = await handle_create_prompt(prompt_repo, request)
    if not prompt:
        raise HTTPException(status_code=500, detail='Failed to create prompt')
    return prompt


@router.get('/{prompt_id}')
async def get_prompt(
    prompt_id: str,
    prompt_repo: Annotated[PromptRepository, Depends(get_prompt_repository)],
) -> Prompt:
    """Get a prompt by ID."""
    prompt = await handle_get_prompt(prompt_repo, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail='Prompt not found')
    return prompt


@router.get('')
async def list_prompts(
    prompt_repo: Annotated[PromptRepository, Depends(get_prompt_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    last_key: str | None = None,
    category: str | None = None,
    is_active: str | None = None,
) -> ListPromptsResponse:
    """List prompts with pagination."""
    last_evaluated_key = json.loads(last_key) if last_key else None

    # Convert is_active string to boolean if provided
    is_active_bool = None
    if is_active is not None:
        is_active_lower = is_active.lower()
        if is_active_lower == 'true':
            is_active_bool = True
        elif is_active_lower == 'false':
            is_active_bool = False

    return await handle_list_prompts(
        prompt_repo,
        limit=limit,
        last_key=last_evaluated_key,
        category=category,
        is_active=is_active_bool,
    )


@router.get('/search')
async def search_prompts(
    query: str,
    prompt_repo: Annotated[PromptRepository, Depends(get_prompt_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    last_key: str | None = None,
) -> ListPromptsResponse:
    """Search prompts by content, name, or description."""
    last_evaluated_key = json.loads(last_key) if last_key else None
    return await handle_search_prompts(
        prompt_repo,
        query=query,
        limit=limit,
        last_key=last_evaluated_key,
    )


@router.put('/{prompt_id}')
async def update_prompt(
    prompt_id: str,
    request: UpdatePromptRequest,
    prompt_repo: Annotated[PromptRepository, Depends(get_prompt_repository)],
) -> Prompt:
    """Update a prompt."""
    prompt = await handle_update_prompt(prompt_repo, prompt_id, request)
    if not prompt:
        raise HTTPException(status_code=404, detail='Prompt not found')
    return prompt


@router.delete('/{prompt_id}')
async def delete_prompt(
    prompt_id: str,
    prompt_repo: Annotated[PromptRepository, Depends(get_prompt_repository)],
) -> Prompt:
    """Delete a prompt (mark as inactive)."""
    prompt = await handle_update_prompt(
        prompt_repo,
        prompt_id,
        UpdatePromptRequest(
            name=None,
            description=None,
            content=None,
            category=None,
            tags=None,
            metadata=None,
            is_active=False,
        ),
    )
    if not prompt:
        raise HTTPException(status_code=404, detail='Prompt not found')
    return prompt
