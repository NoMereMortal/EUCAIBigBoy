# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""DynamoDB client implementation."""

import asyncio
import datetime
import decimal
import uuid
from collections.abc import Awaitable
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

from aiobotocore.session import AioSession
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from loguru import logger

from app.clients.base import BaseClient, CircuitOpenError
from app.config import get_settings
from app.utils import get_function_name

T = TypeVar('T')


def with_retry(
    max_retries: int = 3,
    base_delay: float = 0.2,
    specific_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """
    Decorator for DynamoDB operations that need retry with exponential backoff.
    Particularly useful for operations that may encounter eventual consistency issues.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will be multiplied exponentially)
        specific_exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> T:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(self, *args, **kwargs)
                except specific_exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)  # Exponential backoff
                        logger.warning(
                            f"Operation {func.__name__} failed with '{e!s}'. "
                            f'Retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})'
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f'Operation {func.__name__} failed after {max_retries} attempts: {last_exception}'
                        )
                        raise
            # This should never be reached, but satisfies type checking
            if last_exception is None:
                last_exception = Exception('Unknown error during retry')
            raise last_exception

        return wrapper

    return decorator


class DynamoDBClient(BaseClient):
    """DynamoDB client with async operations."""

    _client: Any | None = None

    async def initialize(self) -> None:
        """Initialize DynamoDB client."""
        if not self.circuit_breaker.can_execute():
            self.circuit_breaker.record_failure()
            raise CircuitOpenError('Circuit breaker is open')

        with self.monitor_operation(get_function_name()):
            session = AioSession()
            # Log the endpoint_url for debugging
            logger.info(
                f'Initializing DynamoDB with endpoint: {self.settings.aws.endpoint_url or self.settings.aws.dynamodb.endpoint_url}'
            )

            # Use dynamodb-specific endpoint if available, otherwise fall back to aws general endpoint
            endpoint_url = (
                self.settings.aws.dynamodb.endpoint_url
                or self.settings.aws.endpoint_url
            )

            self._client = await session.create_client(
                'dynamodb',
                region_name=self.settings.aws.region,
                endpoint_url=endpoint_url,
                config=self.settings.aws.get_boto_config('dynamodb'),
            ).__aenter__()
            logger.info('DynamoDB client initialized')

    async def cleanup(self) -> None:
        """Cleanup DynamoDB client."""
        if self._client:
            with self.monitor_operation(get_function_name()):
                await self._client.__aexit__(None, None, None)
                logger.info('DynamoDB client closed')

    def _get_table_name(self) -> str:
        """Get the configured single-table name."""
        settings = get_settings()
        return settings.dynamodb.table_name

    def _format_pk(self, entity_type: str, entity_id: str) -> str:
        """
        Format a partition key for single-table design.

        Args:
            entity_type: The type of entity (CHAT, MESSAGE, PERSONA, etc.)
            entity_id: The ID of the entity

        Returns:
            Formatted partition key
        """
        return f'{entity_type.upper()}#{entity_id}'

    def _format_sk(self, entity_type: str, entity_id: str | None = None) -> str:
        """
        Format a sort key for single-table design.

        Args:
            entity_type: The type of entity or item (METADATA, MESSAGE, etc.)
            entity_id: Optional ID to include in the sort key

        Returns:
            Formatted sort key
        """
        if entity_id:
            return f'{entity_type.upper()}#{entity_id}'
        return entity_type.upper()

    def create_item_key(self, pk: str, sk: str) -> dict[str, str]:
        """Create a DynamoDB key dict with lowercase field names."""
        return {'pk': pk, 'sk': sk}

    def create_gsi1_item(self, gsi1pk: str, gsi1sk: str) -> dict[str, str]:
        """Create GSI1 fields for single-table design."""
        return {'gsi1pk': gsi1pk, 'gsi1sk': gsi1sk}

    def create_gsi2_item(self, gsi2pk: str, gsi2sk: str) -> dict[str, str]:
        """Create GSI2 fields for single-table design."""
        return {'gsi2pk': gsi2pk, 'gsi2sk': gsi2sk}

    @with_retry(max_retries=3, base_delay=0.2)
    async def put_item(self, table_name: str, item: dict[str, Any]) -> None:
        """Put an item in a DynamoDB table."""
        if not self._client:
            raise ValueError('DynamoDB client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                serialized_item = self._serialize_item(item)

                # Add detailed message logging for debugging
                if 'entity_type' in item and item.get('entity_type') == 'Message':
                    message_id = item.get('message_id', 'unknown')
                    chat_id = item.get('chat_id', 'unknown')
                    kind = item.get('kind', 'unknown')
                    content_preview = 'N/A'

                    # Extract content preview from parts if available
                    if (
                        'parts' in item
                        and isinstance(item['parts'], list)
                        and len(item['parts']) > 0
                    ) and 'content' in item['parts'][0]:
                        content = item['parts'][0]['content']
                        content_preview = content[:50] + (
                            '...' if len(content) > 50 else ''
                        )

                    logger.info(
                        f'DB SAVE: Message id={message_id} chat={chat_id} kind={kind} content="{content_preview}"'
                    )

                # Debug what's being sent
                logger.debug(f'Sending to DynamoDB: {serialized_item}')
                # Use the single table name regardless of what's passed
                table_name = self._get_table_name()
                params = {'TableName': table_name, 'Item': serialized_item}
                await self._client.put_item(**params)
            except Exception as e:
                logger.error(f'Failed to put item in {table_name}: {e}')
                self.circuit_breaker.record_failure()
                raise

    @with_retry(max_retries=3, base_delay=0.2)
    async def get_item(
        self, table_name: str, key: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Get an item from DynamoDB."""
        if not self._client:
            raise ValueError('DynamoDB client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                # Use the single table name regardless of what's passed
                table_name = self._get_table_name()
                response = await self._client.get_item(
                    TableName=table_name, Key=self._serialize_item(key)
                )
                item = response.get('Item')
                return self._deserialize_item(item) if item else None
            except Exception as e:
                logger.error(f'Failed to get item from {table_name}: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def update_item(
        self,
        table_name: str,
        key: dict[str, Any],
        update_expression: str,
        expression_attribute_names: dict[str, str] | None = None,
        expression_attribute_values: dict[str, Any] | None = None,
        condition_expression: str | None = None,
        return_values: str = 'NONE',
    ) -> dict[str, Any] | None:
        """Update an item in DynamoDB."""
        if not self._client:
            raise ValueError('DynamoDB client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                # Prepare parameters
                # Use the single table name regardless of what's passed
                table_name = self._get_table_name()
                serialized_key = self._serialize_item(key)

                # Prepare serialized expression attribute values if present
                serialized_eav = None
                if expression_attribute_values:
                    # Use list comprehension and dict constructor to avoid item assignment issues
                    pairs = [
                        (k, self._serialize_value(v))
                        for k, v in expression_attribute_values.items()
                    ]
                    serialized_eav = dict(pairs)

                # Call update_item with conditional parameters
                if (
                    expression_attribute_names
                    and serialized_eav
                    and condition_expression
                ):
                    response = await self._client.update_item(
                        TableName=table_name,
                        Key=serialized_key,
                        UpdateExpression=update_expression,
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=serialized_eav,
                        ConditionExpression=condition_expression,
                        ReturnValues=return_values,
                    )
                elif expression_attribute_names and serialized_eav:
                    response = await self._client.update_item(
                        TableName=table_name,
                        Key=serialized_key,
                        UpdateExpression=update_expression,
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=serialized_eav,
                        ReturnValues=return_values,
                    )
                elif serialized_eav and condition_expression:
                    response = await self._client.update_item(
                        TableName=table_name,
                        Key=serialized_key,
                        UpdateExpression=update_expression,
                        ExpressionAttributeValues=serialized_eav,
                        ConditionExpression=condition_expression,
                        ReturnValues=return_values,
                    )
                elif expression_attribute_names and condition_expression:
                    response = await self._client.update_item(
                        TableName=table_name,
                        Key=serialized_key,
                        UpdateExpression=update_expression,
                        ExpressionAttributeNames=expression_attribute_names,
                        ConditionExpression=condition_expression,
                        ReturnValues=return_values,
                    )
                elif expression_attribute_names:
                    response = await self._client.update_item(
                        TableName=table_name,
                        Key=serialized_key,
                        UpdateExpression=update_expression,
                        ExpressionAttributeNames=expression_attribute_names,
                        ReturnValues=return_values,
                    )
                elif serialized_eav:
                    response = await self._client.update_item(
                        TableName=table_name,
                        Key=serialized_key,
                        UpdateExpression=update_expression,
                        ExpressionAttributeValues=serialized_eav,
                        ReturnValues=return_values,
                    )
                elif condition_expression:
                    response = await self._client.update_item(
                        TableName=table_name,
                        Key=serialized_key,
                        UpdateExpression=update_expression,
                        ConditionExpression=condition_expression,
                        ReturnValues=return_values,
                    )
                else:
                    response = await self._client.update_item(
                        TableName=table_name,
                        Key=serialized_key,
                        UpdateExpression=update_expression,
                        ReturnValues=return_values,
                    )

                if 'Attributes' in response:
                    return self._deserialize_item(response['Attributes'])
                return None
            except Exception as e:
                logger.error(f'Failed to update item in {table_name}: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def delete_item(
        self,
        table_name: str,
        key: dict[str, Any],
        condition_expression: str | None = None,
        return_values: str = 'NONE',
    ) -> dict[str, Any] | None:
        """Delete an item from DynamoDB."""
        if not self._client:
            raise ValueError('DynamoDB client not initialized')

        # Use the single table name regardless of what's passed
        table_name = self._get_table_name()
        params = {
            'TableName': table_name,
            'Key': self._serialize_item(key),
            'ReturnValues': return_values,
        }

        if condition_expression:
            params['ConditionExpression'] = condition_expression

        with self.monitor_operation(get_function_name()):
            try:
                response = await self._client.delete_item(**params)
                if 'Attributes' in response:
                    return self._deserialize_item(response['Attributes'])
                return None
            except Exception as e:
                logger.error(f'Failed to delete item from {table_name}: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def batch_write_items(
        self, table_name: str, items: list[dict[str, Any]], batch_size: int = 25
    ) -> None:
        """Write items in batches."""
        if not self._client:
            raise ValueError('DynamoDB client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                # Process in batches of 25 (DynamoDB limit)
                # Use the single table name regardless of what's passed
                table_name = self._get_table_name()
                for i in range(0, len(items), batch_size):
                    batch = items[i : i + batch_size]
                    request_items = {
                        table_name: [
                            {'PutRequest': {'Item': self._serialize_item(item)}}
                            for item in batch
                        ]
                    }
                    await self._client.batch_write_item(RequestItems=request_items)
            except Exception as e:
                logger.error(f'Failed batch write to {table_name}: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def scan(self, **params: Any) -> dict[str, Any]:
        """Scan a DynamoDB table."""
        if not self._client:
            raise ValueError('DynamoDB client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                # Apply table name if TableName is in params
                if 'TableName' in params:
                    params['TableName'] = self._get_table_name()

                # Serialize any expression attribute values
                if 'ExpressionAttributeValues' in params:
                    # Use list comprehension and dict constructor to avoid item assignment issues
                    eav_pairs = [
                        (k, self._serialize_value(v))
                        for k, v in params['ExpressionAttributeValues'].items()
                    ]
                    new_params = dict(params)
                    new_params['ExpressionAttributeValues'] = dict(eav_pairs)
                    params = new_params

                response = await self._client.scan(**params)

                if 'Items' in response:
                    response['Items'] = [
                        self._deserialize_item(item) for item in response['Items']
                    ]
                if 'LastEvaluatedKey' in response:
                    response['LastEvaluatedKey'] = self._deserialize_item(
                        response['LastEvaluatedKey']
                    )
                return response
            except Exception as e:
                logger.error(f'Failed to scan: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def query(self, **params: Any) -> dict[str, Any]:
        """Execute a query against DynamoDB."""
        if not self._client:
            raise ValueError('DynamoDB client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                # Apply table name if TableName is in params
                if 'TableName' in params:
                    params['TableName'] = self._get_table_name()

                # Serialize any expression attribute values
                if 'ExpressionAttributeValues' in params:
                    # Use list comprehension and dict constructor to avoid item assignment issues
                    eav_pairs = [
                        (k, self._serialize_value(v))
                        for k, v in params['ExpressionAttributeValues'].items()
                    ]
                    new_params = dict(params)
                    new_params['ExpressionAttributeValues'] = dict(eav_pairs)
                    params = new_params

                response = await self._client.query(**params)

                # Deserialize items in response
                if 'Items' in response:
                    response['Items'] = [
                        self._deserialize_item(item) for item in response['Items']
                    ]

                self.circuit_breaker.record_success()
                return response
            except Exception as e:
                logger.error(f'Failed to execute query: {e}')
                self.circuit_breaker.record_failure()
                raise

    def _serialize_item(self, item: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Convert Python dict to DynamoDB format using boto3 TypeSerializer."""
        serializer = TypeSerializer()
        result = {}

        for key, value in item.items():
            # Handle special cases before using the serializer
            if isinstance(value, uuid.UUID):
                result[key] = serializer.serialize(str(value))
            elif isinstance(value, datetime.datetime):
                result[key] = serializer.serialize(value.isoformat())
            elif isinstance(value, float):
                # Convert float to Decimal for DynamoDB compatibility
                result[key] = serializer.serialize(decimal.Decimal(str(value)))
            elif hasattr(value, 'value') and isinstance(value, Enum):
                result[key] = serializer.serialize(value.value)
            elif hasattr(value, 'model_dump'):
                # Handle Pydantic models
                result[key] = serializer.serialize(value.model_dump())
            else:
                # Use standard serializer for everything else
                result[key] = serializer.serialize(value)

        return result

    def _serialize_value(self, value: Any) -> dict[str, Any]:
        """Serialize a single value for DynamoDB."""
        serializer = TypeSerializer()
        # Handle special cases just like in _serialize_item
        if isinstance(value, uuid.UUID):
            return serializer.serialize(str(value))
        elif isinstance(value, datetime.datetime):
            return serializer.serialize(value.isoformat())
        elif isinstance(value, float):
            # Convert float to Decimal for DynamoDB compatibility
            return serializer.serialize(decimal.Decimal(str(value)))
        elif hasattr(value, 'value') and isinstance(value, Enum):
            return serializer.serialize(value.value)
        elif hasattr(value, 'model_dump'):
            return serializer.serialize(value.model_dump())
        else:
            return serializer.serialize(value)

    def _deserialize_item(self, item: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Convert DynamoDB format to Python dict using boto3 TypeDeserializer."""
        if not item:
            return {}

        deserializer = TypeDeserializer()
        return {k: deserializer.deserialize(v) for k, v in item.items()}

    async def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        if not self._client:
            raise ValueError('DynamoDB client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                table_name = self._get_table_name()
                try:
                    await self._client.describe_table(TableName=table_name)
                    return True
                except self._client.exceptions.ResourceNotFoundException:
                    return False
            except Exception as e:
                logger.error(f'Failed to check if table exists: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def create_tables(self, force_recreate: bool = False) -> None:
        """Create tables if they don't exist."""
        if not self._client:
            raise ValueError('DynamoDB client not initialized')

        from app.clients.dynamodb.schema import get_schemas

        with self.monitor_operation(get_function_name()):
            try:
                schema = (
                    get_schemas()
                )  # get_schemas returns a single schema, not multiple schemas
                # Get the configured single table name
                table_name = self._get_table_name()

                # Table name is already set in the schema
                table_exists = await self.table_exists(table_name)

                # Get reference to the client to satisfy the type checker
                client = self._client
                if client is None:
                    raise ValueError('DynamoDB client should be initialized here')

                if table_exists and force_recreate:
                    logger.info(f'Deleting existing table {table_name}')
                    await client.delete_table(TableName=table_name)
                    waiter = client.get_waiter('table_not_exists')
                    await waiter.wait(TableName=table_name)
                    table_exists = False

                if not table_exists:
                    logger.info(f'Creating table {table_name}')
                    await client.create_table(**schema)
                    # Wait for table creation
                    waiter = client.get_waiter('table_exists')
                    await waiter.wait(TableName=table_name)
                    logger.info(f'Table {table_name} created successfully')
            except Exception as e:
                logger.error(f'Failed to create tables: {e}')
                self.circuit_breaker.record_failure()
                raise
