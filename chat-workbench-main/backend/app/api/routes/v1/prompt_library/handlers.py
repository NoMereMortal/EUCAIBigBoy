# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from datetime import datetime, timezone
from typing import Any

from app.api.routes.v1.prompt_library.models import (
    CreatePromptRequest,
    ListPromptsResponse,
    Prompt,
    UpdatePromptRequest,
)
from app.repositories.prompt import PromptRepository
from app.utils import generate_nanoid


async def handle_create_prompt(
    prompt_repo: PromptRepository, request: CreatePromptRequest
) -> Prompt | None:
    """Create a new prompt."""
    prompt = Prompt(
        prompt_id=generate_nanoid(),
        name=request.name,
        description=request.description,
        content=request.content,
        category=request.category,
        tags=request.tags,
        metadata=request.metadata,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        is_active=True,
    )

    return await prompt_repo.create_prompt(prompt)


async def handle_get_prompt(
    prompt_repo: PromptRepository, prompt_id: str
) -> Prompt | None:
    """Get a prompt by ID."""
    return await prompt_repo.get_prompt(prompt_id)


async def handle_list_prompts(
    prompt_repo: PromptRepository,
    limit: int = 100,
    last_key: dict[str, Any] | None = None,
    category: str | None = None,
    is_active: bool | None = None,
) -> ListPromptsResponse:
    """List prompts with pagination."""
    return await prompt_repo.list_prompts(
        limit=limit,
        last_key=last_key,
        category=category,
        is_active=is_active,
    )


async def handle_update_prompt(
    prompt_repo: PromptRepository,
    prompt_id: str,
    request: UpdatePromptRequest,
) -> Prompt | None:
    """Update a prompt."""
    # Get existing prompt
    prompt = await prompt_repo.get_prompt(prompt_id)
    if not prompt:
        return None

    # Build update dictionary with non-None values
    updates: dict[str, Any] = {}
    if request.name is not None:
        updates['name'] = request.name
    if request.description is not None:
        updates['description'] = request.description
    if request.content is not None:
        updates['content'] = request.content
    if request.category is not None:
        updates['category'] = request.category
    if request.tags is not None:
        updates['tags'] = request.tags
    if request.is_active is not None:
        updates['is_active'] = request.is_active
    if request.metadata is not None:
        # Merge with existing metadata
        updates['metadata'] = {**prompt.metadata, **request.metadata}

    # Update prompt
    success = await prompt_repo.update_prompt(prompt_id, updates)
    if not success:
        return None

    # Return updated prompt
    return await prompt_repo.get_prompt(prompt_id)


async def handle_search_prompts(
    prompt_repo: PromptRepository,
    query: str,
    limit: int = 100,
    last_key: dict[str, Any] | None = None,
) -> ListPromptsResponse:
    """Search prompts by content, name, or description."""
    return await prompt_repo.search_prompts(
        query=query,
        limit=limit,
        last_key=last_key,
    )
