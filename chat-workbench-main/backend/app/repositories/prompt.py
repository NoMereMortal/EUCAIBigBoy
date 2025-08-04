# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Prompt repository implementation."""

from typing import Any

from app.api.routes.v1.prompt_library.models import ListPromptsResponse, Prompt
from app.clients.dynamodb.client import DynamoDBClient
from app.config import get_settings
from app.repositories.base import BaseRepository, RetryConfig


class PromptRepository(BaseRepository[Prompt]):
    """Repository for prompt library operations."""

    def __init__(self, dynamodb_client: DynamoDBClient):
        """Initialize prompt repository."""
        # Initialize attributes directly instead of calling super().__init__()
        # Handle the case where dynamodb_client is a tuple of (client, is_available)
        if isinstance(dynamodb_client, tuple) and len(dynamodb_client) == 2:
            self.dynamodb = dynamodb_client[0]  # Extract just the client
            self.client_available = dynamodb_client[1]  # Store availability flag
        else:
            self.dynamodb = dynamodb_client
            self.client_available = dynamodb_client is not None

        self.entity_type = 'PROMPT'
        self.model_class = Prompt
        self.settings = get_settings()
        self.retry_config = RetryConfig()
        self.table_name = self.settings.dynamodb.table_name

    async def create_prompt(self, prompt: Prompt) -> Prompt | None:
        """Create a new prompt."""
        # Add category to AdminLookupIndex for category-based lookups
        kwargs = {}
        if prompt.category:
            kwargs['admin_key'] = 'PROMPT_CATEGORY'
            kwargs['admin_value'] = prompt.category

        return await self.create(prompt, **kwargs)

    async def get_prompt(self, prompt_id: str) -> Prompt | None:
        """Get a prompt by ID."""
        return await self.get(prompt_id)

    async def list_prompts(
        self,
        limit: int = 100,
        last_key: dict[str, Any] | None = None,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> ListPromptsResponse:
        """List prompts with pagination."""
        if category:
            # Query by category using the AdminLookupIndex
            params = {
                'TableName': self.table_name,
                'IndexName': 'AdminLookupIndex',
                'KeyConditionExpression': 'AdminPK = :apk',
                'ExpressionAttributeValues': {':apk': f'PROMPT_CATEGORY#{category}'},
                'Limit': limit,
            }

            # Add filter for active status if specified
            if is_active is not None:
                params['FilterExpression'] = 'is_active = :is_active'
                # Create a new dict with the needed expression values
                params['ExpressionAttributeValues'] = {
                    ':apk': f'PROMPT_CATEGORY#{category}',
                    ':is_active': str(
                        is_active
                    ).lower(),  # Convert boolean to string 'true' or 'false'
                }
        else:
            # Use GlobalResourceIndex to list all prompts
            params = {
                'TableName': self.table_name,
                'IndexName': 'GlobalResourceIndex',
                'KeyConditionExpression': 'GlobalPK = :gpk',
                'ExpressionAttributeValues': {
                    ':gpk': f'RESOURCE_TYPE#{self.entity_type}'
                },
                'Limit': limit,
            }

            # Add filter for active status if specified
            if is_active is not None:
                params['FilterExpression'] = 'is_active = :is_active'
                # Create a new dict with the needed expression values
                params['ExpressionAttributeValues'] = {
                    ':gpk': f'RESOURCE_TYPE#{self.entity_type}',
                    ':is_active': str(
                        is_active
                    ).lower(),  # Convert boolean to string 'true' or 'false'
                }

        if last_key:
            params['ExclusiveStartKey'] = last_key

        # Execute query
        result = await self.dynamodb.query(**params)

        prompts = [Prompt(**item) for item in result.get('Items', [])]

        return ListPromptsResponse(
            prompts=prompts, last_evaluated_key=result.get('LastEvaluatedKey')
        )

    async def update_prompt(self, prompt_id: str, updates: dict[str, Any]) -> bool:
        """Update prompt fields."""
        return await self.update(prompt_id, updates)

    async def search_prompts(
        self,
        query: str,
        limit: int = 100,
        last_key: dict[str, Any] | None = None,
    ) -> ListPromptsResponse:
        """Search prompts by content, name, or description."""
        params = {
            'TableName': self.table_name,
            'FilterExpression': 'begins_with(SK, :sk_prefix) AND (contains(#name, :query) OR contains(#description, :query) OR contains(#content, :query))',
            'ExpressionAttributeNames': {
                '#name': 'name',
                '#description': 'description',
                '#content': 'content',
            },
            'ExpressionAttributeValues': {':sk_prefix': 'METADATA', ':query': query},
            'Limit': limit,
        }

        if last_key:
            params['ExclusiveStartKey'] = last_key

        result = await self.dynamodb.scan(**params)

        # Filter for prompt entities only
        prompts = [
            Prompt(**item)
            for item in result.get('Items', [])
            if item.get('entity_type') == self.entity_type
        ]

        return ListPromptsResponse(
            prompts=prompts, last_evaluated_key=result.get('LastEvaluatedKey')
        )
