# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from typing import Any

from pydantic import BaseModel, Field

from app.models import ChatSession


class CreateChatRequest(BaseModel):
    title: str = Field(..., description='Chat title')
    user_id: str | None = Field(None, description='User ID')
    metadata: dict[str, Any] = Field(
        default_factory=dict, description='Additional metadata'
    )


class UpdateChatRequest(BaseModel):
    title: str | None = Field(None, description='New chat title')
    status: str | None = Field(
        None, description='New status (active, archived, deleted)'
    )
    metadata: dict[str, Any] | None = Field(None, description='Updated metadata')


class ListChatsResponse(BaseModel):
    chats: list[ChatSession] = Field(
        default_factory=list, description='List of chat sessions'
    )
    last_evaluated_key: dict[str, Any] | None = None
