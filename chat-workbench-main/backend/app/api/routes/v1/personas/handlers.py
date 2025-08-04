# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from datetime import datetime, timezone
from typing import Any

from app.api.routes.v1.personas.models import (
    CreatePersonaRequest,
    ListPersonasResponse,
    Persona,
    UpdatePersonaRequest,
)
from app.repositories.persona import PersonaRepository
from app.utils import generate_nanoid


async def handle_create_persona(
    persona_repo: PersonaRepository, request: CreatePersonaRequest
) -> Persona | None:
    """Create a new persona."""
    persona = Persona(
        persona_id=generate_nanoid(),
        name=request.name,
        description=request.description,
        prompt=request.prompt,
        metadata=request.metadata,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        is_active=True,
    )

    return await persona_repo.create_persona(persona)


async def handle_get_persona(
    persona_repo: PersonaRepository, persona_id: str
) -> Persona | None:
    """Get a persona by ID."""
    return await persona_repo.get_persona(persona_id)


async def handle_list_personas(
    persona_repo: PersonaRepository,
    limit: int = 100,
    last_key: dict[str, Any] | None = None,
    is_active: bool | None = None,
) -> ListPersonasResponse:
    """List personas with pagination."""
    return await persona_repo.list_personas(
        limit=limit,
        last_key=last_key,
        is_active=is_active,
    )


async def handle_update_persona(
    persona_repo: PersonaRepository,
    persona_id: str,
    request: UpdatePersonaRequest,
) -> Persona | None:
    """Update a persona."""
    # Get existing persona
    persona = await persona_repo.get_persona(persona_id)
    if not persona:
        return None

    # Build update dictionary with non-None values
    updates: dict[str, Any] = {}
    if request.name is not None:
        updates['name'] = request.name
    if request.description is not None:
        updates['description'] = request.description
    if request.prompt is not None:
        updates['prompt'] = request.prompt
    if request.is_active is not None:
        updates['is_active'] = request.is_active
    if request.metadata is not None:
        # Merge with existing metadata
        updates['metadata'] = {**persona.metadata, **request.metadata}

    # Update persona
    success = await persona_repo.update_persona(persona_id, updates)
    if not success:
        return None

    # Return updated persona
    return await persona_repo.get_persona(persona_id)
