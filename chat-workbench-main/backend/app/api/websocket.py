# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""WebSocket connection management for the API layer."""

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from fastapi import WebSocket
from loguru import logger
from pydantic import BaseModel, Field

from app.clients.valkey.client import ValkeyClient
from app.services.streaming.events import BaseEvent
from app.utils import make_json_serializable


class WSMessageType(str, Enum):
    """WebSocket message types."""

    # client -> server
    INITIALIZE = 'initialize'  # initial setup with generate request
    INTERRUPT = 'interrupt'  # stop current generation
    PING = 'ping'  # ping to keep connection alive

    # server -> client
    EVENT = 'event'  # streaming event from backend
    PONG = 'pong'  # response to ping
    CONNECTION_ESTABLISHED = 'connection_established'  # initial connection confirmation
    ERROR = 'error'  # error messages
    STATUS = 'status'  # status updates


class WSMessage(BaseModel):
    """WebSocket message model."""

    type: WSMessageType
    data: Any
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def format_event_for_websocket(event: BaseEvent) -> str:
    """Format a BaseEvent for WebSocket delivery."""
    ws_format = event.to_websocket()
    message = {
        'type': 'event',
        'data': ws_format,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(make_json_serializable(message))


class WebSocketManager:
    """
    WebSocket connection manager for the API layer.

    Handles:
    1. WebSocket connection lifecycle
    2. Client subscription management
    3. Event delivery to connected clients
    4. Connection state tracking
    """

    def __init__(self, streaming_service, valkey_client: ValkeyClient):
        """
        Initialize the WebSocket manager.

        Args:
            streaming_service: The streaming service instance
            valkey_client: Optional Valkey client for state persistence, can be None
        """
        self.streaming_service = streaming_service
        self.valkey_client = valkey_client

        # Connection management
        self.conn_prefix = 'ws:conn:'
        self.chat_prefix = 'ws:chat:'
        self.gen_prefix = 'ws:gen:'

        # In-memory storage for websocket objects (cannot be serialized to valkey)
        self._active_connections: dict[str, WebSocket] = {}
        self._response_clients: dict[str, set[Callable[[str], None]]] = {}
        self._accumulated_content: dict[str, str] = {}  # key is chat_id:message_id

        # Pub/sub management
        self._pubsub_tasks: dict[
            str, asyncio.Task
        ] = {}  # response_id -> background task
        self._pubsub_objects: dict[str, Any] = {}  # response_id -> pubsub object

    async def connect(self, connection_id: str, websocket: WebSocket) -> str:
        """
        Connect a new WebSocket client.

        Args:
            connection_id: Unique identifier for this connection
            websocket: The WebSocket connection

        Returns:
            The connection ID
        """
        # Store the websocket object in memory
        self._active_connections[connection_id] = websocket

        # Store metadata in valkey if available
        if self.valkey_client:
            try:
                await self.valkey_client.hset(
                    f'{self.conn_prefix}{connection_id}',
                    mapping={
                        'created_at': datetime.now(timezone.utc).isoformat(),
                        'last_activity': datetime.now(timezone.utc).isoformat(),
                        'active_chats': '[]',  # Empty JSON array
                    },
                )
                # Set TTL to avoid stale connections (24 hours)
                await self.valkey_client.expire(
                    f'{self.conn_prefix}{connection_id}', 86400
                )
                logger.info(
                    f'Connection info stored in valkey [connection_id={connection_id}]'
                )
            except Exception as e:
                logger.error(f'Error storing connection in valkey: {e}', exc_info=True)

        logger.info(f'WebSocket client connected [connection_id={connection_id}]')
        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """Disconnect a WebSocket client."""
        # Clean up in-memory connection
        if connection_id in self._active_connections:
            del self._active_connections[connection_id]

        # Clean up valkey data
        if self.valkey_client:
            try:
                # Get active chats to clean up chat-to-connection mappings
                key = f'{self.conn_prefix}{connection_id}'
                chats_json = await self.valkey_client.hget(key, 'active_chats') or '[]'
                chats = json.loads(chats_json)

                # Clean up each chat's connection reference
                for chat_id in chats:
                    await self.valkey_client.delete(
                        f'{self.chat_prefix}{chat_id}:connection'
                    )
                    # Also clean up any active generations for this chat
                    await self.valkey_client.delete(f'{self.gen_prefix}{chat_id}')

                # Remove connection info
                await self.valkey_client.delete(key)
            except Exception as e:
                logger.error(f'Error cleaning up valkey data: {e}', exc_info=True)

        logger.info(f'WebSocket client disconnected [connection_id={connection_id}]')

    async def register_chat(self, connection_id: str, chat_id: str) -> None:
        """Register a chat with a connection."""
        if self.valkey_client:
            try:
                key = f'{self.conn_prefix}{connection_id}'

                # Get current chats as JSON string
                chats_json = await self.valkey_client.hget(key, 'active_chats') or '[]'
                chats = set(json.loads(chats_json))
                chats.add(chat_id)

                # Update chats and last activity
                await self.valkey_client.hset(
                    key,
                    mapping={
                        'active_chats': json.dumps(list(chats)),
                        'last_activity': datetime.now(timezone.utc).isoformat(),
                    },
                )

                # Also track which connection is handling this chat
                await self.valkey_client.set(
                    f'{self.chat_prefix}{chat_id}:connection', connection_id
                )
                # 1 hour TTL for chat-connection mapping
                await self.valkey_client.expire(
                    f'{self.chat_prefix}{chat_id}:connection', 3600
                )
            except Exception as e:
                logger.error(f'Error registering chat in valkey: {e}', exc_info=True)

        logger.info(
            f'Chat registered with connection [connection_id={connection_id}, chat_id={chat_id}]'
        )

    async def track_generation(self, chat_id: str, message_id: str) -> None:
        """Track an active generation in valkey."""
        if self.valkey_client:
            try:
                await self.valkey_client.hset(
                    f'{self.gen_prefix}{chat_id}',
                    mapping={
                        'message_id': message_id,
                        'started_at': datetime.now(timezone.utc).isoformat(),
                    },
                )
                # Set TTL to avoid stale generations (1 hour)
                await self.valkey_client.expire(f'{self.gen_prefix}{chat_id}', 3600)
            except Exception as e:
                logger.error(f'Error tracking generation in valkey: {e}', exc_info=True)

    async def stop_generation(self, chat_id: str) -> None:
        """Stop tracking a generation in valkey."""
        if self.valkey_client:
            try:
                await self.valkey_client.delete(f'{self.gen_prefix}{chat_id}')
            except Exception as e:
                logger.error(f'Error stopping generation in valkey: {e}', exc_info=True)

    async def update_heartbeat(self, connection_id: str) -> None:
        """Update the last activity timestamp for a connection."""
        if self.valkey_client:
            try:
                await self.valkey_client.hset(
                    f'{self.conn_prefix}{connection_id}',
                    mapping={'last_activity': datetime.now(timezone.utc).isoformat()},
                )
            except Exception as e:
                logger.error(f'Error updating heartbeat in valkey: {e}', exc_info=True)

    def track_content(
        self, chat_id: str, message_id: str, content: str, append: bool = True
    ) -> None:
        """Track accumulated content for a message."""
        key = f'{chat_id}:{message_id}'
        if append and key in self._accumulated_content:
            self._accumulated_content[key] += content
        else:
            self._accumulated_content[key] = content

    def get_accumulated_content(self, chat_id: str, message_id: str) -> str | None:
        """Get the accumulated content for a message."""
        key = f'{chat_id}:{message_id}'
        return self._accumulated_content.get(key)

    def clear_accumulated_content(self, chat_id: str, message_id: str) -> None:
        """Clear the accumulated content for a message."""
        key = f'{chat_id}:{message_id}'
        if key in self._accumulated_content:
            del self._accumulated_content[key]

    async def subscribe_to_response(
        self, response_id: str, client: Callable[[str], None]
    ) -> None:
        """
        Subscribe a client to events for a response.

        Args:
            response_id: The response ID to subscribe to
            client: A callback function to send WebSocket messages to the client
        """
        logger.info(f'Subscribing client to response {response_id}')

        # Store the client
        if response_id not in self._response_clients:
            self._response_clients[response_id] = set()

            # Subscribe to the streaming service events
            await self._subscribe_to_streaming_events(response_id)

        self._response_clients[response_id].add(client)
        logger.info(
            f'Client added to response {response_id}, total clients: {len(self._response_clients[response_id])}'
        )

        # Send initial event to indicate connection is established for this request
        client(
            json.dumps(
                {
                    'type': WSMessageType.CONNECTION_ESTABLISHED,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                }
            )
        )

    async def unsubscribe_from_response(
        self, response_id: str, client: Callable[[str], None]
    ) -> None:
        """
        Unsubscribe a client from events for a response.

        Args:
            response_id: The response ID to unsubscribe from
            client: The client to stop delivering events to
        """
        # Remove the client
        if response_id in self._response_clients:
            if client in self._response_clients[response_id]:
                self._response_clients[response_id].remove(client)

            # If no more clients, clean up subscription
            if not self._response_clients[response_id]:
                del self._response_clients[response_id]
                await self._unsubscribe_from_streaming_events(response_id)

    async def send_message(
        self, connection_id: str, message_type: WSMessageType, data: dict[str, Any]
    ) -> None:
        """Send a formatted message to the WebSocket client."""
        if connection_id in self._active_connections:
            try:
                # Format the message
                message = {
                    'type': message_type,
                    'data': data,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                }

                # Serialize and send
                serialized = make_json_serializable(message)

                # Enhanced logging
                logger.info(
                    f'Sending WebSocket message [connection_id={connection_id}, type={message_type}]'
                )
                logger.debug(f'WebSocket message data: {str(serialized)[:200]}...')

                await self._active_connections[connection_id].send_json(serialized)

                # Update heartbeat
                await self.update_heartbeat(connection_id)

                logger.info(
                    f'Successfully sent message [connection_id={connection_id}, type={message_type}]'
                )
            except Exception as e:
                logger.error(
                    f'Error sending message: {e} [connection_id={connection_id}]',
                    exc_info=True,
                )
        else:
            logger.warning(f'Connection not found [connection_id={connection_id}]')

    async def send_event_to_response_clients(
        self, response_id: str, event: BaseEvent
    ) -> None:
        """Send an event to all clients subscribed to a response."""
        if response_id in self._response_clients:
            # Format the event
            formatted_event = format_event_for_websocket(event)

            # Handle error events specially
            from app.services.streaming.events import ErrorEvent

            if isinstance(event, ErrorEvent):
                error_message = {
                    'type': 'error',
                    'data': {
                        'error': event.message,
                        'error_type': event.error_type,
                        'details': event.details or {},
                        'response_id': response_id,
                        'sequence': event.sequence,
                    },
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                }
                formatted_event = json.dumps(make_json_serializable(error_message))

            # Send to all clients
            clients = list(self._response_clients[response_id])
            logger.info(
                f'Sending event to {len(clients)} clients for response {response_id}'
            )

            failed_clients = []
            for client in clients:
                try:
                    client(formatted_event)
                except Exception as e:
                    logger.error(f'Failed to send to client: {e}')
                    failed_clients.append(client)

            # Remove failed clients
            for client in failed_clients:
                self._response_clients[response_id].discard(client)

            logger.info(
                f'Event delivery complete. Active clients: {len(self._response_clients[response_id])}'
            )

    async def _subscribe_to_streaming_events(self, response_id: str) -> None:
        """Subscribe to streaming service events for a response."""
        if not self.valkey_client:
            logger.warning(
                f'No Valkey client available for subscribing to response {response_id}'
            )
            return

        channel = f'response:{response_id}'
        logger.info(f'Subscribing to Valkey channel: {channel}')

        try:
            # Create a pubsub object
            pubsub = await self.valkey_client.pubsub()
            self._pubsub_objects[response_id] = pubsub

            # Subscribe to the channel
            await pubsub.subscribe(channel)
            logger.info(f'Successfully subscribed to channel: {channel}')

            # Start background task to listen for messages
            async def listen_for_messages():
                """Background task to listen for pubsub messages."""
                try:
                    while True:
                        # Get the next message (blocks until one is available)
                        message = await pubsub.get_message(
                            ignore_subscribe_messages=True, timeout=1.0
                        )

                        if message is None:
                            # Timeout occurred, continue listening
                            continue

                        if message['type'] == 'message':
                            channel_name = message['channel']
                            event_data = message['data']

                            # Ensure event_data is a string
                            if isinstance(event_data, bytes):
                                event_data = event_data.decode('utf-8')
                            elif not isinstance(event_data, str):
                                event_data = str(event_data)

                            logger.debug(
                                f'Received event from channel {channel_name}: {event_data[:200]}...'
                            )

                            try:
                                # Deserialize the event
                                from app.services.streaming.utils import (
                                    deserialize_event,
                                )

                                event = deserialize_event(event_data)

                                if event:
                                    logger.info(
                                        f'Deserialized event: {type(event).__name__} for response {response_id}'
                                    )
                                    # Send to all subscribed clients
                                    await self.send_event_to_response_clients(
                                        response_id, event
                                    )
                                else:
                                    logger.warning(
                                        f'Failed to deserialize event from channel {channel_name}'
                                    )

                            except Exception as e:
                                logger.error(
                                    f'Error handling event from channel {channel_name}: {e}',
                                    exc_info=True,
                                )

                except asyncio.CancelledError:
                    logger.info(
                        f'Pubsub listener task cancelled for response {response_id}'
                    )
                    raise
                except Exception as e:
                    logger.error(
                        f'Error in pubsub listener for response {response_id}: {e}',
                        exc_info=True,
                    )
                finally:
                    # Clean up pubsub object
                    try:
                        await pubsub.unsubscribe(channel)
                        await pubsub.aclose()
                    except Exception as e:
                        logger.error(
                            f'Error cleaning up pubsub for response {response_id}: {e}'
                        )

            # Start the background task
            task = asyncio.create_task(listen_for_messages())
            self._pubsub_tasks[response_id] = task
            logger.info(f'Started pubsub listener task for response {response_id}')

        except Exception as e:
            logger.error(f'Error subscribing to channel {channel}: {e}', exc_info=True)

    async def _unsubscribe_from_streaming_events(self, response_id: str) -> None:
        """Unsubscribe from streaming service events for a response."""
        if not self.valkey_client:
            return

        channel = f'response:{response_id}'
        logger.info(f'Unsubscribing from Valkey channel: {channel}')

        try:
            # Cancel the background task
            if response_id in self._pubsub_tasks:
                task = self._pubsub_tasks[response_id]
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                del self._pubsub_tasks[response_id]
                logger.info(f'Cancelled pubsub task for response {response_id}')

            # Clean up pubsub object
            if response_id in self._pubsub_objects:
                pubsub = self._pubsub_objects[response_id]
                try:
                    await pubsub.unsubscribe(channel)
                    await pubsub.aclose()
                except Exception as e:
                    logger.error(f'Error closing pubsub object: {e}')
                del self._pubsub_objects[response_id]
                logger.info(f'Cleaned up pubsub object for response {response_id}')

        except Exception as e:
            logger.error(
                f'Error unsubscribing from channel {channel}: {e}', exc_info=True
            )
