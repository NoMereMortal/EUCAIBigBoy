# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Task handler metadata repository implementation."""

from typing import Any

from loguru import logger

from app.clients.dynamodb.client import DynamoDBClient
from app.config import get_settings
from app.repositories.base import BaseRepository, RetryConfig
from app.task_handlers.models import (
    ListTaskHandlers,
    TaskHandlerConfig,
    TaskHandlerInfo,
)


class TaskHandlerConfigRepository(BaseRepository[TaskHandlerInfo]):
    """Repository for task handler metadata."""

    def __init__(self, dynamodb_client: DynamoDBClient):
        """Initialize task handler repository."""
        # Initialize attributes directly instead of calling super().__init__()
        # Handle the case where dynamodb_client is a tuple of (client, is_available)
        if isinstance(dynamodb_client, tuple) and len(dynamodb_client) == 2:
            self.dynamodb = dynamodb_client[0]  # Extract just the client
            self.client_available = dynamodb_client[1]  # Store availability flag
        else:
            self.dynamodb = dynamodb_client
            self.client_available = dynamodb_client is not None

        self.entity_type = 'TASK_HANDLER'
        self.model_class = TaskHandlerInfo
        self.settings = get_settings()
        self.retry_config = RetryConfig()
        self.table_name = self.settings.dynamodb.table_name

    async def get_metadata(self, name: str) -> TaskHandlerInfo | None:
        """Get configuration for a task handler."""
        try:
            # In single-table design, we use the name as entity ID
            return await self.get(name)
        except Exception as e:
            logger.error(f'Error getting task handler config for {name}: {e}')
            return None

    async def list_metadata(self) -> ListTaskHandlers:
        """List all task handler configurations using GlobalResourceIndex."""
        try:
            # Use GlobalResourceIndex to get all task handlers
            params = {
                'TableName': self.table_name,
                'IndexName': 'GlobalResourceIndex',
                'KeyConditionExpression': 'GlobalPK = :gpk',
                'ExpressionAttributeValues': {
                    ':gpk': f'RESOURCE_TYPE#{self.entity_type}'
                },
            }

            result = await self.dynamodb.query(**params)

            handlers = [TaskHandlerInfo(**item) for item in result.get('Items', [])]

            return ListTaskHandlers(
                handlers=handlers, last_evaluated_key=result.get('LastEvaluatedKey')
            )
        except Exception as e:
            logger.error(f'Error listing task handler configs: {e}')
            return ListTaskHandlers(handlers=[])

    def _get_key(self, entity_id: str, sort_key: str = 'METADATA') -> dict[str, str]:
        """Override _get_key to use 'name' as the ID field."""
        return {'PK': self._format_pk(entity_id), 'SK': sort_key}

    def _format_pk(self, entity_id: str) -> str:
        """Format the partition key using the entity ID (name)."""
        return f'{self.entity_type}#{entity_id}'

    async def create_metadata(
        self, handler: Any, default: bool = False
    ) -> TaskHandlerInfo:
        """Create configuration for a task handler."""
        # Check if it already exists
        config = await self.get_metadata(handler.name)
        if config:
            logger.info(f'Task handler config for {handler.name} already exists')
            return config

        try:
            # Create item for DynamoDB
            item = TaskHandlerInfo(
                name=handler.name,
                description=handler.description,
                is_default=default,
                config={},
            )

            # Override the BaseRepository create method to use name as the ID
            # Create primary key
            dynamo_item = {'PK': self._format_pk(item.name), 'SK': 'METADATA'}

            # Convert model to dict
            if hasattr(item, 'model_dump'):
                model_dict = item.model_dump()
            else:
                model_dict = dict(vars(item))

            # Copy model fields to dynamo item
            for key, value in model_dict.items():
                dynamo_item[key] = value

            # Add GSI keys
            dynamo_item = self._format_gsi_keys(dynamo_item, item.name)

            # Save to DynamoDB
            from app.utils import make_json_serializable

            serialized_item = make_json_serializable(dynamo_item)
            await self.dynamodb.put_item(self.table_name, serialized_item)

            return item
        except Exception as e:
            logger.error(f'Error saving task handler config for {handler.name}: {e}')
            raise

    async def update_metadata(
        self, name: str, config: TaskHandlerConfig
    ) -> TaskHandlerInfo:
        """Update configuration for a task handler."""
        # Ensure config exists
        task_info = await self.get_metadata(name)
        if not task_info:
            raise ValueError(f'Task handler config for {name} does not exist')

        try:
            # Update with new config
            await self.update(
                name,
                updates={
                    'config': config.model_dump()
                    if hasattr(config, 'model_dump')
                    else vars(config)
                },
            )

            # Get the updated item
            updated_info = await self.get_metadata(name)
            if updated_info:
                return updated_info

            # Fallback if get fails - convert config to dict for type compatibility
            task_info.config = (
                config.model_dump() if hasattr(config, 'model_dump') else vars(config)
            )
            return task_info
        except Exception as e:
            logger.error(f'Error updating task handler config for {name}: {e}')
            raise

    async def delete_metadata(self, name: str) -> None:
        """Delete configuration for a task handler."""
        try:
            await self.delete(name)
        except Exception as e:
            logger.error(f'Error deleting task handler config for {name}: {e}')
            raise
