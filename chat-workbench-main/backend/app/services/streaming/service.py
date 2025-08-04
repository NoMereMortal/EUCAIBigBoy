# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Streaming service for real-time content delivery."""

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from loguru import logger

from app.clients.valkey.client import ValkeyClient
from app.models import Message, ModelResponse
from app.services.streaming.events import BaseEvent
from app.services.streaming.processor import EventProcessor
from app.utils import generate_nanoid


class StreamingService:
    """
    Unified streaming service for real-time content delivery.

    This service provides:
    1. Event processing and state management
    2. Message persistence and lifecycle management

    Note: Protocol handling has been moved to the API layer (app.api.websocket, etc.)
    """

    def __init__(self, valkey_client: ValkeyClient):
        """
        Initialize the streaming service.

        Args:
            valkey_client: ValkeyClient instance for pub/sub operations
        """
        self.valkey_client = valkey_client
        self.event_processor = EventProcessor(valkey_client)
        self._response_timeouts: dict[str, asyncio.Task] = {}

        # Default timeout for responses (in seconds)
        self.response_timeout = 3600  # 1 hour

    async def init_response(
        self,
        chat_id: str,
        parent_id: str,
        model_id: str,
        response_id: str | None = None,
    ) -> str:
        """
        Initialize a new response.

        Args:
            chat_id: The chat ID
            parent_id: The parent message ID
            model_id: The model ID
            response_id: Optional response ID (generated if not provided)

        Returns:
            The response ID
        """
        # Generate a response ID if not provided
        if not response_id:
            response_id = generate_nanoid()

        # Create a basic message structure
        ModelResponse(
            message_id=response_id,
            chat_id=chat_id,
            parent_id=parent_id,
            model_name=model_id,
            status='pending',
        )

        # Set up a timeout task for this response
        self._setup_response_timeout(response_id)

        logger.info(f'Initialized response {response_id} for chat {chat_id}')
        return response_id

    async def process_event(self, event: BaseEvent) -> None:
        """
        Process an event through the event processor.

        Args:
            event: The event to process
        """
        await self.event_processor.process_event(event)

    def get_message(self, response_id: str) -> Message | None:
        """
        Get the current message state for a response ID.

        Args:
            response_id: The response ID to get the message for

        Returns:
            A Message instance or None if not found
        """
        return self.event_processor.get_message(response_id)

    def _setup_response_timeout(self, response_id: str) -> None:
        """
        Set up a timeout task for a response.

        Args:
            response_id: The response ID to set up a timeout for
        """
        # Cancel any existing timeout task
        if response_id in self._response_timeouts:
            self._response_timeouts[response_id].cancel()

        # Create a new timeout task
        async def timeout_task():
            try:
                await asyncio.sleep(self.response_timeout)
                logger.warning(f'Response {response_id} timed out')
                # Clean up resources
                self.cleanup_response(response_id)
            except asyncio.CancelledError:
                # Task was cancelled, which is expected when the response completes
                pass

        # Schedule the timeout task
        self._response_timeouts[response_id] = asyncio.create_task(timeout_task())

    def cleanup_response(self, response_id: str) -> None:
        """
        Clean up resources for a response ID.

        Args:
            response_id: The response ID to clean up
        """
        # Cancel any timeout task
        if response_id in self._response_timeouts:
            self._response_timeouts[response_id].cancel()
            del self._response_timeouts[response_id]

        # Clean up in the event processor
        self.event_processor.cleanup_response(response_id)

        logger.debug(f'Cleaned up resources for response {response_id}')

    async def shutdown(self) -> None:
        """
        Shut down the streaming service and clean up resources.
        """
        # Cancel all timeout tasks
        for task in self._response_timeouts.values():
            task.cancel()

        # Clear all dictionaries
        self._response_timeouts.clear()

        logger.info('Streaming service shut down')
