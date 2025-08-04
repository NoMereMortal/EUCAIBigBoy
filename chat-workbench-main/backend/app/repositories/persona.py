# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Persona repository implementation."""

from typing import Any

from app.api.routes.v1.personas.models import ListPersonasResponse, Persona
from app.clients.dynamodb.client import DynamoDBClient
from app.config import get_settings
from app.repositories.base import BaseRepository, RetryConfig


class PersonaRepository(BaseRepository[Persona]):
    """Repository for persona operations."""

    def __init__(self, dynamodb_client: DynamoDBClient):
        """Initialize persona repository."""
        # Initialize attributes directly instead of calling super().__init__()
        # Handle the case where dynamodb_client is a tuple of (client, is_available)
        if isinstance(dynamodb_client, tuple) and len(dynamodb_client) == 2:
            self.dynamodb = dynamodb_client[0]  # Extract just the client
            self.client_available = dynamodb_client[1]  # Store availability flag
        else:
            self.dynamodb = dynamodb_client
            self.client_available = dynamodb_client is not None

        self.entity_type = 'PERSONA'
        self.model_class = Persona
        self.settings = get_settings()
        self.retry_config = RetryConfig()
        self.table_name = self.settings.dynamodb.table_name

    async def create_persona(self, persona: Persona) -> Persona | None:
        """Create a new persona."""
        return await self.create(
            persona, admin_key='PERSONA_NAME', admin_value=persona.name
        )

    async def get_persona(self, persona_id: str) -> Persona | None:
        """Get a persona by ID."""
        return await self.get(persona_id)

    async def get_persona_by_name(self, name: str) -> Persona | None:
        """Get a persona by name using the AdminLookupIndex."""
        params = {
            'TableName': self.table_name,
            'IndexName': 'AdminLookupIndex',
            'KeyConditionExpression': 'AdminPK = :apk',
            'ExpressionAttributeValues': {':apk': f'PERSONA_NAME#{name}'},
            'Limit': 1,
        }

        result = await self.dynamodb.query(**params)
        items = result.get('Items', [])

        if not items:
            return None

        return Persona(**items[0])

    async def list_personas(
        self,
        limit: int = 100,
        last_key: dict[str, Any] | None = None,
        is_active: bool | None = None,
    ) -> ListPersonasResponse:
        """List all personas using the GlobalResourceIndex."""
        params = {
            'TableName': self.table_name,
            'IndexName': 'GlobalResourceIndex',
            'KeyConditionExpression': 'GlobalPK = :gpk',
            'ExpressionAttributeValues': {':gpk': f'RESOURCE_TYPE#{self.entity_type}'},
            'Limit': limit,
        }

        if is_active is not None:
            params['FilterExpression'] = 'is_active = :is_active'
            params['ExpressionAttributeValues'] = {
                ':gpk': f'RESOURCE_TYPE#{self.entity_type}',
                ':is_active': str(
                    is_active
                ).lower(),  # Convert boolean to string 'true' or 'false'
            }

        if last_key:
            params['ExclusiveStartKey'] = last_key

        result = await self.dynamodb.query(**params)

        personas = [Persona(**item) for item in result.get('Items', [])]

        return ListPersonasResponse(
            personas=personas, last_evaluated_key=result.get('LastEvaluatedKey')
        )

    async def update_persona(self, persona_id: str, updates: dict[str, Any]) -> bool:
        """Update persona fields."""
        return await self.update(persona_id, updates)
