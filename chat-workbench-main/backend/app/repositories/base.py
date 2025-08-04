# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Base repository for single-table DynamoDB design with error handling and retry capabilities."""

import asyncio
import time
from collections.abc import Awaitable
from datetime import datetime
from typing import Any, Callable, Generic, Optional, TypeVar, cast

from loguru import logger

from app.clients.dynamodb.client import DynamoDBClient
from app.config import get_settings
from app.utils import make_json_serializable

# Generic types
T = TypeVar('T')  # Model type
R = TypeVar('R')  # Return type for operations


class RepositoryOperationError(Exception):
    """Error raised when a repository operation fails."""

    def __init__(self, operation: str, error: Exception) -> None:
        """Initialize with operation details."""
        self.operation = operation
        self.error = error
        super().__init__(f"Repository operation '{operation}' failed: {error}")


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        backoff_factor: float = 2.0,
        jitter: float = 0.1,
    ) -> None:
        """
        Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            backoff_factor: Multiplier for delay after each retry
            jitter: Random factor to add to delay for avoiding thundering herd
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter


class BaseRepository(Generic[T]):
    """Base repository for all entity types using the single-table design."""

    def __init__(
        self,
        dynamodb_client: Optional[DynamoDBClient | tuple[DynamoDBClient, bool]],
        entity_type: str,
        model_class: type[T],
        retry_config: Optional[RetryConfig] = None,
    ):
        """Initialize the base repository.

        Args:
            dynamodb_client: The DynamoDB client (may be None) or tuple of (client, is_available)
            entity_type: The entity type (e.g., CHAT, MESSAGE, etc.)
            model_class: The model class for this repository
            retry_config: Configuration for retry behavior (optional)
        """
        # Handle the case where dynamodb_client is a tuple of (client, is_available)
        if isinstance(dynamodb_client, tuple) and len(dynamodb_client) == 2:
            self.dynamodb = dynamodb_client[0]  # Extract just the client
            self.client_available = dynamodb_client[1]  # Store availability flag
        else:
            self.dynamodb = dynamodb_client
            self.client_available = dynamodb_client is not None

        self.entity_type = entity_type
        self.model_class = model_class
        self.settings = get_settings()
        self.retry_config = retry_config or RetryConfig()

        # Use the single table name for all entities
        self.table_name = self.settings.dynamodb.table_name

    def _format_pk(self, entity_id: str) -> str:
        """Format the partition key for this entity type."""
        return f'{self.entity_type}#{entity_id}'

    def _format_sk(self, sort_key_type: str, sort_key_id: str | None = None) -> str:
        """Format the sort key for this entity type."""
        if sort_key_id:
            return f'{sort_key_type}#{sort_key_id}'
        return sort_key_type

    def _format_gsi_keys(
        self,
        item: dict[str, Any],
        entity_id: str,
        user_id: str | None = None,
        parent_id: str | None = None,
        admin_key: str | None = None,
        admin_value: str | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Format GSI keys for the single-table design.

        Args:
            item: The item to add GSI keys to
            entity_id: The ID of the entity
            user_id: Optional user ID for UserDataIndex
            parent_id: Optional parent ID for MessageHierarchyIndex
            admin_key: Optional admin key for AdminLookupIndex
            admin_value: Optional admin value paired with admin_key
            timestamp: Optional timestamp for chronological ordering

        Returns:
            The updated item with GSI keys
        """
        # Add entity_type for all items
        item['entity_type'] = self.entity_type

        # Add timestamps if not present
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        if 'created_at' not in item:
            item['created_at'] = timestamp
        if 'updated_at' not in item:
            item['updated_at'] = timestamp

        # Add GSI1 keys for user-based queries if user_id is provided
        if user_id:
            item['UserPK'] = f'USER#{user_id}'
            item['UserSK'] = f'{self.entity_type}#{timestamp}#{entity_id}'

        # Add GSI2 keys for global resource type queries (always)
        item['GlobalPK'] = f'RESOURCE_TYPE#{self.entity_type}'
        item['GlobalSK'] = f'CREATED_AT#{timestamp}#{entity_id}'

        return item

    def _get_key(self, entity_id: str, sort_key: str = 'METADATA') -> dict[str, str]:
        """Get the primary key for an item."""
        return {'PK': self._format_pk(entity_id), 'SK': sort_key}

    async def _execute_with_retry(
        self,
        operation_name: str,
        operation: Callable[..., Awaitable[R]],
        *args: Any,
        default_value: Optional[R] = None,
        **kwargs: Any,
    ) -> R:
        """
        Execute an operation with retry logic.

        Args:
            operation_name: Name of the operation for logging
            operation: Callable operation that returns an awaitable
            *args: Arguments to pass to the operation
            default_value: Default value to return on failure (optional)
            **kwargs: Keyword arguments to pass to the operation

        Returns:
            Result of the operation or default value on failure

        Raises:
            RepositoryOperationError: If all retries fail and no default value is provided
        """
        if self.dynamodb is None:
            logger.warning(
                f'Cannot perform {operation_name}: DynamoDB client not available'
            )
            if default_value is not None:
                return default_value
            raise RepositoryOperationError(
                operation_name, ValueError('DynamoDB client is not available')
            )

        retries = 0
        last_error = None
        config = self.retry_config

        while retries <= config.max_retries:
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_error = e
                retries += 1

                if retries <= config.max_retries:
                    # Calculate delay with exponential backoff and jitter
                    delay = config.base_delay * (config.backoff_factor ** (retries - 1))
                    jitter = (
                        config.jitter * delay * (2 * (0.5 - time.time() % 1))
                    )  # -jitter to +jitter
                    total_delay = max(0.1, delay + jitter)

                    logger.warning(
                        f'{operation_name} failed (attempt {retries}/{config.max_retries}): {e}. '
                        f'Retrying in {total_delay:.2f}s'
                    )
                    await asyncio.sleep(total_delay)
                else:
                    logger.error(
                        f'{operation_name} failed after {config.max_retries} retries: {e}'
                    )
                    if default_value is not None:
                        return default_value
                    raise RepositoryOperationError(operation_name, e) from e

        # This should never happen but added for type safety
        if default_value is not None:
            return default_value
        raise RepositoryOperationError(
            operation_name,
            last_error or ValueError('Unknown error in repository operation'),
        )

    async def create(
        self, model: T, sort_key: str = 'METADATA', **kwargs
    ) -> Optional[T]:
        """Create a new item.

        Args:
            model: The model to create
            sort_key: The sort key to use (default: METADATA)
            **kwargs: Additional parameters for GSI keys

        Returns:
            The created model
        """
        # Get model attributes as dict
        if hasattr(model, 'model_dump'):
            # Handle Pydantic models
            from typing import Any, cast

            pydantic_model = cast(Any, model)
            item = pydantic_model.model_dump()
        else:
            # Handle dataclasses or other objects
            import inspect
            from dataclasses import asdict, is_dataclass
            from typing import Any, cast

            # First check if this is a class type vs an instance
            if inspect.isclass(model):
                # It's a class, use vars
                item = dict(vars(model))
            elif is_dataclass(model):
                # It's a dataclass instance - cast it for type safety
                dataclass_instance = cast(Any, model)  # Cast to Any first
                item = asdict(dataclass_instance)
            else:
                # Regular object, use vars
                item = dict(vars(model))

        # Get entity ID from item
        entity_id_field = f'{self.entity_type.lower()}_id'
        if entity_id_field not in item:
            raise ValueError(f'Missing {entity_id_field} in model')

        entity_id = item[entity_id_field]

        # Create new dict for DynamoDB item with primary key
        dynamo_item = {'PK': self._format_pk(entity_id), 'SK': sort_key}

        # Copy all model fields to the DynamoDB item
        for key, value in item.items():
            dynamo_item[key] = value

        # Add GSI keys
        dynamo_item = self._format_gsi_keys(dynamo_item, entity_id, **kwargs)

        # Serialize item for DynamoDB
        serialized_item = make_json_serializable(dynamo_item)

        # Save to DynamoDB with retry
        # Create a properly typed wrapper function
        async def typed_wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
            """Wrapper with explicit typing for mypy."""
            if self.dynamodb:
                await self.dynamodb.put_item(self.table_name, serialized_item)
                return model
            return None

        result = await self._execute_with_retry(
            f'create_{self.entity_type.lower()}', typed_wrapper, default_value=None
        )

        return result

    async def get(self, entity_id: str, sort_key: str = 'METADATA') -> Optional[T]:
        """Get an item by ID with error handling and retry logic.

        Args:
            entity_id: The ID of the entity to get
            sort_key: The sort key to use (default: METADATA)

        Returns:
            The model instance or None if not found
        """
        key = self._get_key(entity_id, sort_key)

        # Create a properly typed wrapper function
        async def typed_get_item(*args: Any, **kwargs: Any) -> Any:
            """Wrapper with explicit typing for mypy."""
            if self.dynamodb:
                return await self.dynamodb.get_item(self.table_name, key)
            return None

        item = await self._execute_with_retry(
            f'get_{self.entity_type.lower()}', typed_get_item, default_value=None
        )

        if not item:
            return None

        try:
            return self.model_class(**item)  # type: ignore
        except Exception as e:
            logger.error(f'Error creating model from item: {e}')
            return None

    async def update(
        self, entity_id: str, updates: dict[str, Any], sort_key: str = 'METADATA'
    ) -> bool:
        """Update an item with error handling and retry logic.

        Args:
            entity_id: The ID of the entity to update
            updates: Dict of fields to update
            sort_key: The sort key to use (default: METADATA)

        Returns:
            True if the update was successful
        """
        key = self._get_key(entity_id, sort_key)

        # Build update expression
        expression_parts = []
        expression_names = {}
        expression_values = {}

        for field_name, value in updates.items():
            # Use expression attribute names for all fields to avoid reserved word conflicts
            attr_name = f'#{field_name}'
            attr_value = f':{field_name}'

            expression_parts.append(f'{attr_name} = {attr_value}')
            expression_names[attr_name] = field_name
            expression_values[attr_value] = value

        # Always update the updated_at timestamp
        expression_parts.append('#updated_at = :updated_at')
        expression_names['#updated_at'] = 'updated_at'
        expression_values[':updated_at'] = datetime.now().isoformat()

        update_expression = 'SET ' + ', '.join(expression_parts)

        # Create a properly typed wrapper function
        async def typed_update_item(*args: Any, **kwargs: Any) -> bool:
            """Wrapper with explicit typing for mypy."""
            if self.dynamodb:
                await self.dynamodb.update_item(
                    table_name=self.table_name,
                    key=key,
                    update_expression=update_expression,
                    expression_attribute_names=expression_names,
                    expression_attribute_values=expression_values,
                )
                return True
            return False

        result = await self._execute_with_retry(
            f'update_{self.entity_type.lower()}', typed_update_item, default_value=False
        )

        return result

    async def delete(self, entity_id: str, sort_key: str = 'METADATA') -> bool:
        """Delete an item with error handling and retry logic.

        Args:
            entity_id: The ID of the entity to delete
            sort_key: The sort key to use (default: METADATA)

        Returns:
            True if the deletion was successful
        """
        key = self._get_key(entity_id, sort_key)

        # Create a properly typed wrapper function
        async def typed_delete_item(*args: Any, **kwargs: Any) -> bool:
            """Wrapper with explicit typing for mypy."""
            if self.dynamodb:
                await self.dynamodb.delete_item(self.table_name, key)
                return True
            return False

        result = await self._execute_with_retry(
            f'delete_{self.entity_type.lower()}', typed_delete_item, default_value=False
        )

        return result

    async def list_by_user(
        self,
        user_id: str,
        limit: int = 20,
        last_key: dict[str, Any] | None = None,
    ) -> tuple[list[T], dict[str, Any] | None]:
        """List items for a specific user with error handling.

        Args:
            user_id: The user ID to filter by
            limit: Maximum number of items to return
            last_key: Key for pagination

        Returns:
            Tuple of (items, last_evaluated_key)
        """
        params = {
            'TableName': self.table_name,
            'IndexName': 'UserDataIndex',
            'KeyConditionExpression': 'UserPK = :upk AND begins_with(UserSK, :prefix)',
            'ExpressionAttributeValues': {
                ':upk': f'USER#{user_id}',
                ':prefix': f'{self.entity_type}#',
            },
            'ScanIndexForward': False,  # newest first
            'Limit': limit,
        }

        if last_key:
            params['ExclusiveStartKey'] = last_key

        # Create a properly typed wrapper function
        async def typed_query(*args: Any, **kwargs: Any) -> dict[str, Any]:
            """Wrapper with explicit typing for mypy."""
            if self.dynamodb:
                return await self.dynamodb.query(**params)
            return {'Items': [], 'LastEvaluatedKey': None}

        result = await self._execute_with_retry(
            f'list_{self.entity_type.lower()}_by_user',
            typed_query,
            default_value={'Items': [], 'LastEvaluatedKey': None},
        )

        items = [self.model_class(**item) for item in result.get('Items', [])]  # type: ignore

        # Handle the LastEvaluatedKey with proper typing
        last_evaluated_key = result.get('LastEvaluatedKey')
        # Use a more direct cast approach to satisfy the type checker
        if last_evaluated_key is not None and isinstance(last_evaluated_key, dict):
            return items, cast(dict[str, Any], last_evaluated_key)
        return items, None

    async def list_by_global_type(
        self,
        limit: int = 20,
        last_key: dict[str, Any] | None = None,
        is_admin_only: bool = False,
    ) -> tuple[list[T], dict[str, Any] | None]:
        """List all items by resource type with error handling.

        Args:
            limit: Maximum number of items to return
            last_key: Key for pagination
            is_admin_only: Whether to filter for admin-only items

        Returns:
            Tuple of (items, last_evaluated_key)
        """
        params = {
            'TableName': self.table_name,
            'IndexName': 'GlobalResourceIndex',
            'KeyConditionExpression': 'GlobalPK = :gpk',
            'ExpressionAttributeValues': {':gpk': f'RESOURCE_TYPE#{self.entity_type}'},
            'ScanIndexForward': False,  # newest first
            'Limit': limit,
        }

        if is_admin_only:
            params['FilterExpression'] = 'is_admin = :is_admin'
            # Create a new dictionary for expression values
            expr_values = {}
            # Copy existing values
            if 'ExpressionAttributeValues' in params and isinstance(
                params['ExpressionAttributeValues'], dict
            ):
                for k, v in params['ExpressionAttributeValues'].items():
                    expr_values[k] = v
            # Add the new value - convert boolean to string for type compatibility
            expr_values[':is_admin'] = 'true'
            # Replace the expression values dict
            params['ExpressionAttributeValues'] = expr_values

        if last_key:
            params['ExclusiveStartKey'] = last_key

        # Create a properly typed wrapper function
        async def typed_query(*args: Any, **kwargs: Any) -> dict[str, Any]:
            """Wrapper with explicit typing for mypy."""
            if self.dynamodb:
                return await self.dynamodb.query(**params)
            return {'Items': [], 'LastEvaluatedKey': None}

        result = await self._execute_with_retry(
            f'list_{self.entity_type.lower()}_by_global_type',
            typed_query,
            default_value={'Items': [], 'LastEvaluatedKey': None},
        )

        items = [self.model_class(**item) for item in result.get('Items', [])]  # type: ignore

        # Handle the LastEvaluatedKey with proper typing
        last_evaluated_key = result.get('LastEvaluatedKey')
        # Use a more direct cast approach to satisfy the type checker
        if last_evaluated_key is not None and isinstance(last_evaluated_key, dict):
            return items, cast(dict[str, Any], last_evaluated_key)
        return items, None
