# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from app.clients.dynamodb.client import DynamoDBClient
from app.models import Message
from app.repositories.task_handler_metadata import TaskHandlerConfigRepository
from app.services.streaming.events import BaseEvent
from app.task_handlers.models import TaskHandlerConfig


class BaseTaskHandler(ABC):
    """Base class for all task handlers."""

    def __init__(
        self,
        dynamodb_client: DynamoDBClient | None = None,
    ):
        self.dynamodb_client = dynamodb_client

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the task handler."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of the task handler."""
        pass

    async def get_guardrail(self) -> dict[str, Any] | None:
        """Get guardrail for this task handler."""
        if not self.dynamodb_client:
            return None

        task_handler_metadata_repo = TaskHandlerConfigRepository(self.dynamodb_client)
        metadata = await task_handler_metadata_repo.get_metadata(self.name)
        if not metadata:
            return None

        config = TaskHandlerConfig(**metadata.config)

        return (
            {
                'guardrailIdentifier': config.guardrail.guardrail_id,
                'guardrailVersion': config.guardrail.guardrail_version,
                'trace': 'enabled',
                'streamProcessingMode': 'async',
            }
            if config.guardrail
            else None
        )

    @abstractmethod
    async def handle(
        self,
        chat_id: str,
        message_history: list[Message],
        user_message: Message,
        model_id: str,
        response_message_id: str,
        context: list[dict[str, Any]] | None = None,
        persona: str | None = None,
    ) -> AsyncGenerator[BaseEvent, None]:
        """
        Process the request and generate streaming events.

        This method yields BaseEvent objects (ContentEvent, ToolCallEvent, etc.)
        that can be sent directly to clients.

        Args:
            chat_id: The ID of the chat
            message_history: The history of messages in the chat
            user_message: The user's message to process
            model_id: The ID of the model to use
            response_message_id: The ID to use for the response message
            context: Optional context information
            persona: Optional persona to use

        Returns:
            An async generator yielding streaming events
        """
        yield BaseEvent(response_id=response_message_id)  # Placeholder implementation
