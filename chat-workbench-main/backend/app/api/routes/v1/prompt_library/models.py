# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreatePromptRequest(BaseModel):
    name: str = Field(..., description='Prompt name')
    description: str = Field(..., description='Prompt description')
    content: str = Field(..., description='The prompt content')
    category: str = Field(..., description='Prompt category')
    tags: list[str] = Field(default_factory=list, description='Tags for categorization')
    metadata: dict[str, Any] = Field(
        default_factory=dict, description='Additional metadata'
    )


class UpdatePromptRequest(BaseModel):
    name: str | None = Field(None, description='Updated prompt name')
    description: str | None = Field(None, description='Updated prompt description')
    content: str | None = Field(None, description='Updated prompt content')
    category: str | None = Field(None, description='Updated prompt category')
    tags: list[str] | None = Field(None, description='Updated tags')
    metadata: dict[str, Any] | None = Field(None, description='Updated metadata')
    is_active: bool | None = Field(None, description='Whether the prompt is active')


class Prompt(BaseModel):
    prompt_id: str
    name: str
    description: str
    content: str
    category: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ListPromptsResponse(BaseModel):
    prompts: list[Prompt] = Field(default_factory=list, description='List of prompts')
    last_evaluated_key: dict[str, Any] | None = None
