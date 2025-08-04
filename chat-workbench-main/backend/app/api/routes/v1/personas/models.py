# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreatePersonaRequest(BaseModel):
    name: str = Field(..., description='Persona name')
    description: str = Field(..., description='Persona description')
    prompt: str = Field(..., description='The prompt that defines this persona')
    metadata: dict[str, Any] = Field(
        default_factory=dict, description='Additional metadata'
    )


class UpdatePersonaRequest(BaseModel):
    name: str | None = Field(None, description='Updated persona name')
    description: str | None = Field(None, description='Updated persona description')
    prompt: str | None = Field(None, description='Updated persona prompt')
    metadata: dict[str, Any] | None = Field(None, description='Updated metadata')
    is_active: bool | None = Field(None, description='Whether the persona is active')


class Persona(BaseModel):
    persona_id: str
    name: str
    description: str
    prompt: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ListPersonasResponse(BaseModel):
    personas: list[Persona] = Field(
        default_factory=list, description='List of personas'
    )
    last_evaluated_key: dict[str, Any] | None = None
