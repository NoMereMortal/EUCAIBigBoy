# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Message repository implementation."""

import datetime
from typing import Any

from loguru import logger

from app.clients.dynamodb.client import DynamoDBClient
from app.config import get_settings
from app.models import (
    CitationPart,
    DocumentPart,
    ImagePart,
    Message,
    MessagePart,
    ModelRequest,
    ModelResponse,
    ReasoningPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from app.repositories.base import BaseRepository, RetryConfig


class MessageRepository(BaseRepository[Message]):
    """Repository for message operations."""

    def __init__(self, dynamodb_client: DynamoDBClient):
        """Initialize message repository."""
        # Initialize attributes directly instead of calling super().__init__()
        # Handle the case where dynamodb_client is a tuple of (client, is_available)
        if isinstance(dynamodb_client, tuple) and len(dynamodb_client) == 2:
            self.dynamodb = dynamodb_client[0]  # Extract just the client
            self.client_available = dynamodb_client[1]  # Store availability flag
        else:
            self.dynamodb = dynamodb_client
            self.client_available = dynamodb_client is not None

        self.entity_type = 'MESSAGE'
        self.model_class = Message
        self.settings = get_settings()
        self.retry_config = RetryConfig()
        self.table_name = self.settings.dynamodb.table_name

    def generate_message_id(self) -> str:
        """Generate a unique message ID."""
        from app.models import generate_nanoid

        return generate_nanoid()

    def _deserialize_message(self, item: dict[str, Any]) -> Message:
        """Convert DynamoDB item to the appropriate Message subclass with properly typed parts."""
        if not item:
            raise ValueError('Cannot deserialize empty item')

        # Ensure 'parts' field is present
        if 'parts' not in item:
            item['parts'] = []
            logger.warning(f"Missing 'parts' field in message {item.get('message_id')}")

        message_id = item.get('message_id', 'unknown')

        # Process each part and convert it to the appropriate type
        if 'parts' in item and isinstance(item['parts'], list):
            logger.debug(
                f'Deserializing {len(item["parts"])} parts for message {message_id}'
            )
            processed_parts = []

            for i, part in enumerate(item['parts']):
                if isinstance(part, dict) and 'part_kind' in part:
                    part_kind = part['part_kind']
                    try:
                        # Create appropriate part type based on part_kind
                        if part_kind == 'text':
                            processed_parts.append(TextPart(**part))

                        elif part_kind == 'citation':
                            # Special handling for citation parts to ensure all fields are set
                            citation_content = part.get('content', '')
                            citation_text = part.get('text', '')

                            # Log citation part details before processing
                            logger.debug(
                                f'Deserializing citation part {i} from message {message_id}: '
                                f'text_len={len(citation_text)}, content_len={len(citation_content)}, '
                                f'document_id={part.get("document_id", "unknown")}'
                            )

                            # Ensure citation has a document_id
                            if 'document_id' not in part or not part['document_id']:
                                part['document_id'] = (
                                    'cd4739en'  # Set a default document ID
                                )
                                logger.warning(
                                    f'Citation {i} missing document_id, setting default value: cd4739en'
                                )

                            # If text is empty but content exists, make text match content
                            if not citation_text and citation_content:
                                part['text'] = citation_content
                                logger.debug(
                                    f'Citation {i}: Synced empty text with content ({len(citation_content)} chars)'
                                )

                            # Ensure citation has required fields
                            required_fields = {
                                'text': citation_text
                                or citation_content
                                or 'No citation text available',
                                'content': citation_content
                                or citation_text
                                or 'No citation content available',
                            }

                            # Update part with any missing required fields
                            for field, default in required_fields.items():
                                if field not in part or not part[field]:
                                    part[field] = default
                                    logger.debug(
                                        f'Citation {i}: Added missing required field {field}'
                                    )

                            try:
                                citation_part = CitationPart(**part)
                                processed_parts.append(citation_part)
                                logger.debug(
                                    f'Successfully created CitationPart for part {i}'
                                )
                            except Exception as e:
                                logger.error(
                                    f'Failed to create CitationPart for part {i}: {e}'
                                )
                                # Create a TextPart fallback with the citation content
                                text = f'[Citation from {part.get("document_id", "unknown")}]: {citation_text or citation_content}'
                                processed_parts.append(TextPart(content=text))
                                logger.debug(
                                    f'Created TextPart fallback for failed citation part {i}'
                                )

                        elif part_kind == 'image':
                            processed_parts.append(ImagePart(**part))

                        elif part_kind == 'document':
                            processed_parts.append(DocumentPart(**part))

                        elif part_kind == 'tool-call':
                            processed_parts.append(ToolCallPart(**part))

                        elif part_kind == 'tool-return':
                            processed_parts.append(ToolReturnPart(**part))

                        elif part_kind == 'reasoning':
                            processed_parts.append(ReasoningPart(**part))

                        else:
                            # Fallback for unknown part types
                            logger.warning(
                                f'Unknown part_kind: {part_kind}, using raw dict'
                            )
                            processed_parts.append(part)

                    except Exception as e:
                        logger.error(f'Error deserializing message part: {e}')
                        processed_parts.append(
                            part
                        )  # Use raw part if deserialization fails
                else:
                    # If part doesn't have part_kind, keep it as is
                    processed_parts.append(part)

            # Replace the parts list with our processed parts
            item['parts'] = processed_parts

            # Log summary of processed parts
            part_types: dict[str, int] = {}
            for part in processed_parts:
                if isinstance(part, MessagePart):
                    part_type: str = part.part_kind
                    # Use direct dictionary access with fallback instead of .get()
                    if part_type in part_types:
                        part_types[part_type] += 1
                    else:
                        part_types[part_type] = 1

            logger.debug(
                f'Processed {len(processed_parts)} parts for message {message_id}: {part_types}'
            )

        # Ensure timestamp is timezone-aware to prevent comparison issues
        if (
            'timestamp' in item
            and isinstance(item['timestamp'], datetime.datetime)
            and item['timestamp'].tzinfo is None
        ):
            # Convert naive datetime to timezone-aware (UTC)
            item['timestamp'] = item['timestamp'].replace(tzinfo=datetime.timezone.utc)

        # Ensure all parts have timezone-aware timestamps
        if 'parts' in item and isinstance(item['parts'], list):
            for part in item['parts']:
                if (
                    isinstance(part, dict)
                    and 'timestamp' in part
                    and (
                        isinstance(part['timestamp'], datetime.datetime)
                        and part['timestamp'].tzinfo is None
                    )
                ):
                    part['timestamp'] = part['timestamp'].replace(
                        tzinfo=datetime.timezone.utc
                    )

        # Create appropriate message type based on 'kind'
        if item.get('kind') == 'request':
            return ModelRequest(**item)
        elif item.get('kind') == 'response':
            return ModelResponse(**item)
        else:
            return Message(**item)

    async def create_message(self, message: Message) -> Message:
        """Create a new message."""
        # Skip empty response messages
        try:
            message_id = message.message_id
            chat_id = message.chat_id

            # Get a dict representation of the message
            if hasattr(message, 'model_dump'):
                item = message.model_dump()
            else:
                item = dict(vars(message))

            # Set the correct PK and SK for DynamoDB - use Message entity type for PK
            item['PK'] = f'{self.entity_type}#{chat_id}'
            item['SK'] = f'MESSAGE#{message_id}'

            # Update timestamps
            item['updated_at'] = datetime.datetime.now().isoformat()
            if 'created_at' not in item:
                item['created_at'] = item['updated_at']

            # Ensure timestamp is timezone-aware
            if (
                'timestamp' in item
                and isinstance(item['timestamp'], datetime.datetime)
                and item['timestamp'].tzinfo is None
            ):
                item['timestamp'] = item['timestamp'].replace(
                    tzinfo=datetime.timezone.utc
                )

            # Serialize datetime objects in message parts to strings
            if 'parts' in item and isinstance(item['parts'], list):
                for part in item['parts']:
                    if (
                        isinstance(part, dict)
                        and 'timestamp' in part
                        and isinstance(part['timestamp'], datetime.datetime)
                    ):
                        # Ensure part timestamp is timezone-aware before serializing
                        if part['timestamp'].tzinfo is None:
                            part['timestamp'] = part['timestamp'].replace(
                                tzinfo=datetime.timezone.utc
                            )
                        part['timestamp'] = part['timestamp'].isoformat()

            # Add parent relationship for message hierarchy
            if message.parent_id:
                item['ParentPK'] = f'PARENT#{message.parent_id}'
                item['ParentSK'] = (
                    f'{self.entity_type}#{item["created_at"]}#{message_id}'
                )

            # Save to DynamoDB directly
            await self.dynamodb.put_item(self.table_name, item)

            # Log the creation for debugging
            logger.debug(
                f'Created message {message_id} for chat {chat_id} with PK={item["PK"]}'
            )

            return message
        except Exception as e:
            logger.error(f'Error creating message: {e}')
            raise

    async def get_message(self, chat_id: str, message_id: str) -> Message | None:
        """Get a message by ID."""
        key = {'PK': f'{self.entity_type}#{chat_id}', 'SK': f'MESSAGE#{message_id}'}

        item = await self.dynamodb.get_item(self.table_name, key)

        if not item:
            return None

        # Convert to appropriate message type
        return self._deserialize_message(item)

    async def get_chat_messages(
        self,
        chat_id: str,
        sort_order: str = 'asc',
    ) -> list[Message]:
        """Get all messages for a chat. (Used for user facing endpoints)"""

        logger.info(f'Getting messages for chat {chat_id}')

        params = {
            'TableName': self.table_name,
            'KeyConditionExpression': 'PK = :pk AND begins_with(SK, :sk_prefix)',
            'ExpressionAttributeValues': {
                ':pk': f'{self.entity_type}#{chat_id}',
                ':sk_prefix': 'MESSAGE#',
            },
        }

        logger.debug(f'Querying DynamoDB with PK: {self.entity_type}#{chat_id}')
        result = await self.dynamodb.query(**params)
        raw_items = result.get('Items', [])

        logger.info(f'Total message items found: {len(raw_items)}')

        # Deserialize to proper message types
        logger.debug(f'Deserializing {len(raw_items)} messages')
        messages = []
        for item in raw_items:
            try:
                message = self._deserialize_message(item)
                messages.append(message)
            except Exception as e:
                logger.error(f'Failed to deserialize message: {e}')

        logger.info(f'Deserialized {len(messages)} messages for chat {chat_id}')

        # Sort by timestamp
        messages.sort(key=lambda m: m.timestamp, reverse=(sort_order == 'desc'))
        logger.debug(f'Messages sorted by timestamp ({sort_order})')

        return messages

    async def get_conversation_path(
        self,
        chat_id: str,
        message_id: str,
    ) -> list[Message]:
        """Get the conversation path from root to a message. (Used for model input)"""
        path: list[Message] = []
        current_id: str | None = message_id

        while current_id and current_id != chat_id:
            message = await self.get_message(chat_id, current_id)
            if not message:
                # Log the failure to find a message
                logger.warning(
                    f'Failed to find message in conversation path: chat_id={chat_id}, message_id={current_id}'
                )
                break

            path.insert(0, message)
            current_id = message.parent_id

        return path

    async def get_messages_by_parent_id(
        self, chat_id: str, parent_id: str
    ) -> list[Message]:
        """Get all messages with a specific parent_id."""
        params = {
            'TableName': self.table_name,
            'IndexName': 'MessageHierarchyIndex',
            'KeyConditionExpression': 'ParentPK = :ppk',
            'ExpressionAttributeValues': {':ppk': f'PARENT#{parent_id}'},
        }

        result = await self.dynamodb.query(**params)
        messages = [self._deserialize_message(item) for item in result.get('Items', [])]

        return messages

    async def update_message_content(
        self,
        chat_id: str,
        message_id: str,
        content: str,
        part_index: int = 0,
    ) -> bool:
        """Update the content of the first part of a message."""
        message = await self.get_message(chat_id, message_id)
        if not message or not message.parts:
            logger.error(
                f'Failed to update message content: chat_id={chat_id}, message_id={message_id}'
            )
            return False

        try:
            message.parts[part_index].content = content
            return await self.save_message(message)
        except Exception as e:
            logger.error(f'Error updating message content: {e}')
            return False

    async def save_message(self, message: Message) -> bool:
        """Save a complete message object to the database.

        This method replaces the entire message in the database with the provided
        message object. Use this when you have modified a message object directly.
        """
        try:
            message_id = message.message_id
            chat_id = message.chat_id

            # Log detailed information about message parts before serialization
            logger.info(
                f'SAVE MESSAGE START: id={message_id} chat={chat_id} kind={message.kind} parts_count={len(message.parts)}'
            )

            # Log detailed info for each part
            for i, part in enumerate(message.parts):
                part_kind = part.part_kind
                part_id = getattr(part, 'citation_id', None) or f'part_{i}'

                # Special detailed logging for citations
                if part_kind == 'citation':
                    logger.debug(
                        f'Message {message_id} Part {i} (citation): citation_id={part_id}, '
                        f'document_id={getattr(part, "document_id", "unknown")}, '
                        f'text_len={len(getattr(part, "text", ""))}, '
                        f'content_len={len(getattr(part, "content", ""))}, '
                        f"text='{getattr(part, 'text', '')[:100]}...', "
                        f"content='{getattr(part, 'content', '')[:100]}...'"
                    )
                else:
                    # Generic part logging
                    content_preview = 'N/A'
                    if hasattr(part, 'content'):
                        if isinstance(part.content, str):
                            content_preview = part.content[:100] + (
                                '...' if len(part.content) > 100 else ''
                            )
                        else:
                            content_preview = str(part.content)[:100] + '...'

                    logger.debug(
                        f"Message {message_id} Part {i} ({part_kind}): id={part_id}, content_preview='{content_preview}'"
                    )

            # Get a dict representation of the message
            if hasattr(message, 'model_dump'):
                item = message.model_dump()
                logger.debug(f'Serializing message {message_id} using model_dump()')
            else:
                item = dict(vars(message))
                logger.debug(f'Serializing message {message_id} using vars()')

            # Set the correct PK and SK for DynamoDB
            item['PK'] = f'{self.entity_type}#{chat_id}'
            item['SK'] = f'MESSAGE#{message_id}'

            # Update the timestamp
            item['updated_at'] = datetime.datetime.now().isoformat()
            if 'created_at' not in item:
                item['created_at'] = item['updated_at']

            # Ensure timestamp is timezone-aware
            if (
                'timestamp' in item
                and isinstance(item['timestamp'], datetime.datetime)
                and item['timestamp'].tzinfo is None
            ):
                item['timestamp'] = item['timestamp'].replace(
                    tzinfo=datetime.timezone.utc
                )

            # Serialize datetime objects in message parts to strings
            if 'parts' in item and isinstance(item['parts'], list):
                logger.debug(
                    f'Processing {len(item["parts"])} parts for timestamp serialization in message {message_id}'
                )
                for part_idx, part in enumerate(item['parts']):
                    if (
                        isinstance(part, dict)
                        and 'timestamp' in part
                        and isinstance(part['timestamp'], datetime.datetime)
                    ):
                        # Ensure part timestamp is timezone-aware before serializing
                        if part['timestamp'].tzinfo is None:
                            part['timestamp'] = part['timestamp'].replace(
                                tzinfo=datetime.timezone.utc
                            )
                        part['timestamp'] = part['timestamp'].isoformat()
                        logger.debug(
                            f'Serialized timestamp for part {part_idx} in message {message_id}'
                        )

            # Log detailed structure of serialized message before saving
            logger.debug(
                f'Serialized message structure before DynamoDB save: message_id={message_id}, parts_count={len(item.get("parts", []))}'
            )

            # Log detailed part information after serialization for DynamoDB
            if 'parts' in item and isinstance(item['parts'], list):
                for i, part in enumerate(item['parts']):
                    if isinstance(part, dict):
                        part_kind = part.get('part_kind', 'unknown')

                        # Special handling for citation parts
                        if part_kind == 'citation':
                            logger.debug(
                                f'SERIALIZED Citation Part {i}: document_id={part.get("document_id", "unknown")}, '
                                f'citation_id={part.get("citation_id", "unknown")}, '
                                f'text={part.get("text", "")[:50]}..., '
                                f'content={part.get("content", "")[:50]}...'
                            )
                        else:
                            # Generic part logging
                            content = part.get('content', '')
                            content_preview = str(content)[:100] + (
                                '...' if len(str(content)) > 100 else ''
                            )
                            logger.debug(
                                f'SERIALIZED Part {i}: kind={part_kind}, content_type={type(content).__name__}, content={content_preview}'
                            )

            # Final log right before saving to DynamoDB
            logger.debug(
                f'FINAL SAVE PAYLOAD: message_id={message_id}, parts_count={len(item.get("parts", []))}, total_size~={len(str(item))} chars'
            )

            # Save to DynamoDB directly
            await self.dynamodb.put_item(self.table_name, item)

            # Log confirmation after successful save
            logger.info(
                f'SAVE MESSAGE SUCCESS: id={message_id} with {len(item.get("parts", []))} parts'
            )
            return True
        except Exception as e:
            logger.error(f'Error saving message: {e}')
            return False

    async def update_message(
        self, chat_id: str, message_id: str, updates: dict[str, Any]
    ) -> bool:
        """Update specific fields of a message.

        This method retrieves the message, updates the specified fields, and saves it back
        to the database.
        """
        message = await self.get_message(chat_id, message_id)
        if not message:
            logger.warning(
                f'Cannot update message - not found: chat_id={chat_id}, message_id={message_id}'
            )
            return False

        try:
            # Apply updates to message fields
            for field, value in updates.items():
                if hasattr(message, field):
                    setattr(message, field, value)

            # Save updated message back to database
            return await self.save_message(message)
        except Exception as e:
            logger.error(f'Error updating message {message_id}: {e}')
            return False

    async def update_message_status(
        self, chat_id: str, message_id: str, status: str
    ) -> bool:
        """Update the status field of a message."""
        return await self.update_message(chat_id, message_id, {'status': status})
