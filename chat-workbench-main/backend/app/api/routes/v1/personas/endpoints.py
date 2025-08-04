# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import get_user_id_from_header
from app.api.dependencies.clients import get_dynamodb_client
from app.api.routes.v1.personas.handlers import (
    handle_create_persona,
    handle_get_persona,
    handle_list_personas,
    handle_update_persona,
)
from app.api.routes.v1.personas.models import (
    CreatePersonaRequest,
    ListPersonasResponse,
    Persona,
    UpdatePersonaRequest,
)
from app.clients.dynamodb.client import DynamoDBClient
from app.repositories.persona import PersonaRepository

router = APIRouter(prefix='/persona', tags=['persona'])


def get_persona_repository(
    dynamodb_client: DynamoDBClient = Depends(get_dynamodb_client()),
) -> PersonaRepository:
    """Get persona repository instance."""
    return PersonaRepository(dynamodb_client)


@router.post('')
async def create_persona(
    request: CreatePersonaRequest,
    persona_repo: Annotated[PersonaRepository, Depends(get_persona_repository)],
    user_id: Annotated[str, Depends(get_user_id_from_header)],
) -> Persona:
    """Create a new persona."""
    persona = await handle_create_persona(persona_repo, request)
    if not persona:
        raise HTTPException(status_code=500, detail='Failed to create persona')
    return persona


@router.get('/{persona_id}')
async def get_persona(
    persona_id: str,
    persona_repo: Annotated[PersonaRepository, Depends(get_persona_repository)],
    user_id: Annotated[str, Depends(get_user_id_from_header)],
) -> Persona:
    """Get a persona by ID."""
    persona = await handle_get_persona(persona_repo, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail='Persona not found')
    return persona


@router.get('')
async def list_personas(
    persona_repo: Annotated[PersonaRepository, Depends(get_persona_repository)],
    user_id: Annotated[str, Depends(get_user_id_from_header)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    last_key: str | None = None,
    is_active: str | None = None,
) -> ListPersonasResponse:
    """List personas with pagination."""
    last_evaluated_key = json.loads(last_key) if last_key else None

    # Convert is_active string to boolean if provided
    is_active_bool = None
    if is_active is not None:
        is_active_lower = is_active.lower()
        if is_active_lower == 'true':
            is_active_bool = True
        elif is_active_lower == 'false':
            is_active_bool = False

    return await handle_list_personas(
        persona_repo,
        limit=limit,
        last_key=last_evaluated_key,
        is_active=is_active_bool,
    )


@router.put('/{persona_id}')
async def update_persona(
    persona_id: str,
    request: UpdatePersonaRequest,
    persona_repo: Annotated[PersonaRepository, Depends(get_persona_repository)],
    user_id: Annotated[str, Depends(get_user_id_from_header)],
) -> Persona:
    """Update a persona."""
    persona = await handle_update_persona(persona_repo, persona_id, request)
    if not persona:
        raise HTTPException(status_code=404, detail='Persona not found')
    return persona


@router.delete('/{persona_id}')
async def delete_persona(
    persona_id: str,
    persona_repo: Annotated[PersonaRepository, Depends(get_persona_repository)],
    user_id: Annotated[str, Depends(get_user_id_from_header)],
) -> Persona:
    """Delete a persona (mark as inactive)."""
    persona = await handle_update_persona(
        persona_repo,
        persona_id,
        UpdatePersonaRequest(
            name=None, description=None, prompt=None, metadata=None, is_active=False
        ),
    )
    if not persona:
        raise HTTPException(status_code=404, detail='Persona not found')
    return persona
