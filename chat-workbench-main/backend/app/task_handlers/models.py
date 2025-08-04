# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from typing import Any

from pydantic import BaseModel, Field


class TaskHandlerGuardrailConfig(BaseModel):
    """Guardrail configuration for a task handler."""

    guardrail_id: str
    guardrail_version: str
    enabled: bool = True


class TaskHandlerConfig(BaseModel):
    """Request model for updating a task handler configuration."""

    guardrail: TaskHandlerGuardrailConfig | None = None


class TaskHandlerInfo(BaseModel):
    """Basic information about a task handler."""

    name: str
    description: str
    tools: list[str] = Field(default_factory=list)
    is_default: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class ListTaskHandlers(BaseModel):
    handlers: list[TaskHandlerInfo]
    last_evaluated_key: dict[str, Any] | None = None
