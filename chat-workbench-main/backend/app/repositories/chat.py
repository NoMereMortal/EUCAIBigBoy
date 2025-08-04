# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Chat repository implementation."""

from decimal import Decimal
from typing import Any, Union

from loguru import logger

from app.clients.dynamodb.client import DynamoDBClient
from app.config import get_settings
from app.models import ChatSession, ListChatSessions
from app.repositories.base import BaseRepository, RetryConfig
from app.repositories.message import MessageRepository


class ChatRepository(BaseRepository[ChatSession]):
    """Repository for chat session operations."""

    @staticmethod
    def _convert_floats_to_decimals(
        data: Union[dict[str, Any], list, float, int, str, bool, None],
    ) -> Any:
        """Recursively convert all float values to Decimal for DynamoDB compatibility.

        Args:
            data: The data to convert, which can be a dict, list, float, or other primitive types

        Returns:
            The same data structure with all floats converted to Decimal
        """
        if isinstance(data, float):
            return Decimal(str(data))
        elif isinstance(data, dict):
            return {
                k: ChatRepository._convert_floats_to_decimals(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [ChatRepository._convert_floats_to_decimals(item) for item in data]
        else:
            return data

    def __init__(self, dynamodb_client: DynamoDBClient):
        """Initialize chat repository."""
        # Initialize attributes directly instead of calling super().__init__()
        # Handle the case where dynamodb_client is a tuple of (client, is_available)
        if isinstance(dynamodb_client, tuple) and len(dynamodb_client) == 2:
            self.dynamodb = dynamodb_client[0]  # Extract just the client
            self.client_available = dynamodb_client[1]  # Store availability flag
        else:
            self.dynamodb = dynamodb_client
            self.client_available = dynamodb_client is not None

        self.entity_type = 'CHAT'
        self.model_class = ChatSession
        self.settings = get_settings()
        self.retry_config = RetryConfig()
        self.table_name = self.settings.dynamodb.table_name

    async def create_chat(self, chat: ChatSession) -> ChatSession | None:
        """Create a new chat session."""
        return await self.create(chat, user_id=chat.user_id)

    async def get_chat(self, chat_id: str) -> ChatSession | None:
        """Get a chat session by ID."""
        return await self.get(chat_id)

    async def update_chat_metadata(
        self, chat_id: str, metadata: dict[str, Any]
    ) -> bool:
        """Update chat metadata."""
        return await self.update(chat_id, updates={'metadata': metadata})

    async def update_chat_usage(
        self, chat_id: str, message_id: str, usage: dict[str, Any], model_id: str
    ) -> bool:
        """Update usage metrics for a chat."""
        try:
            # Log the start of usage update for debugging
            logger.debug(
                f'Updating usage for chat {chat_id}, message {message_id}, model {model_id}'
            )
            logger.debug(f'Usage data: {usage}')

            # Get current chat including its usage data
            chat = await self.get_chat(chat_id)
            if not chat:
                logger.warning(f'Chat {chat_id} not found for usage update')
                return False

            # First, convert any float values in the incoming usage data to Decimal
            usage_safe = self._convert_floats_to_decimals(usage)

            # Initialize usage if not exists and convert any existing float values to Decimal
            current_usage = self._convert_floats_to_decimals(chat.usage or {})

            # Update total tokens
            total_tokens = current_usage.get('total_tokens', 0)
            total_tokens += usage_safe.get('total_tokens', 0)

            # Update total cost
            current_cost = current_usage.get('total_cost', 0.0)
            current_cost = (
                Decimal(str(current_cost))
                if isinstance(current_cost, float)
                else current_cost
            )
            total_cost = current_cost
            if 'cost' in usage_safe:
                total_cost += usage_safe['cost']

            # Update model-specific metrics
            by_model = current_usage.get('by_model', {})
            # Convert existing model usage to ensure compatibility
            if model_id in by_model:
                by_model[model_id] = self._convert_floats_to_decimals(
                    by_model[model_id]
                )

            model_usage = by_model.get(model_id, {'tokens': 0, 'cost': Decimal('0.0')})
            model_usage['tokens'] = model_usage.get('tokens', 0) + usage_safe.get(
                'total_tokens', 0
            )

            if 'cost' in usage_safe:
                model_usage['cost'] = (
                    model_usage.get('cost', Decimal('0.0')) + usage_safe['cost']
                )

            by_model[model_id] = model_usage

            # Update message metrics
            by_message = current_usage.get('by_message', {})
            by_message[message_id] = usage_safe

            # Construct updated usage object
            updated_usage = {
                'total_tokens': total_tokens,
                'total_cost': total_cost,
                'by_model': by_model,
                'by_message': by_message,
            }

            logger.debug(f'Updated usage object: {updated_usage}')

            # Update in DynamoDB
            result = await self.update(chat_id, updates={'usage': updated_usage})
            logger.debug(
                f'Usage update for chat {chat_id} {"succeeded" if result else "failed"}'
            )
            return result
        except Exception as e:
            logger.error(f'Error updating chat usage: {e}')
            return False

    async def list_chats(
        self,
        user_id: str,
        with_messages: int,
        message_repo: MessageRepository,
        limit: int = 100,
        status: str = 'active',
        last_key: dict[str, Any] | None = None,
    ) -> ListChatSessions:
        """List chats for a user with pagination."""
        params = {
            'TableName': self.table_name,
            'IndexName': 'UserDataIndex',
            'KeyConditionExpression': 'UserPK = :upk AND begins_with(UserSK, :prefix)',
            'FilterExpression': '#status = :status',
            'ExpressionAttributeNames': {'#status': 'status'},
            'ExpressionAttributeValues': {
                ':upk': f'USER#{user_id}',
                ':prefix': f'{self.entity_type}#',
                ':status': status,
            },
            'Limit': limit,
            'ScanIndexForward': False,  # newest first
        }

        if last_key:
            params['ExclusiveStartKey'] = last_key

        result = await self.dynamodb.query(**params)

        chats = [ChatSession(**item) for item in result.get('Items', [])]

        if with_messages > 0:
            chats_with_messages = chats[: min(with_messages, len(chats))]
            for chat in chats_with_messages:
                messages = await message_repo.get_chat_messages(chat.chat_id)
                chat.messages.extend(messages)

        return ListChatSessions(
            chats=chats,
            last_evaluated_key=result.get('LastEvaluatedKey'),
        )
