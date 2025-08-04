# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""DynamoDB schema definitions for single-table design."""

from typing import Any

from app.config import get_settings

# Entity types for single-table design
ENTITY_TYPE_CHAT = 'Chat'
ENTITY_TYPE_MESSAGE = 'Message'
ENTITY_TYPE_PERSONA = 'Persona'
ENTITY_TYPE_PROMPT = 'Prompt'
ENTITY_TYPE_TASK_HANDLER = 'TaskHandler'
ENTITY_TYPE_SETTING = 'Setting'


def get_schemas() -> dict[str, Any]:
    """Get the schema for the single-table design."""
    settings = get_settings()
    table_name = settings.dynamodb.table_name

    return {
        'TableName': table_name,
        'KeySchema': [
            {'AttributeName': 'PK', 'KeyType': 'HASH'},
            {'AttributeName': 'SK', 'KeyType': 'RANGE'},
        ],
        'AttributeDefinitions': [
            {'AttributeName': 'PK', 'AttributeType': 'S'},
            {'AttributeName': 'SK', 'AttributeType': 'S'},
            {'AttributeName': 'UserPK', 'AttributeType': 'S'},
            {'AttributeName': 'UserSK', 'AttributeType': 'S'},
            {'AttributeName': 'ParentPK', 'AttributeType': 'S'},
            {'AttributeName': 'ParentSK', 'AttributeType': 'S'},
            {'AttributeName': 'AdminPK', 'AttributeType': 'S'},
            {'AttributeName': 'AdminSK', 'AttributeType': 'S'},
            {'AttributeName': 'GlobalPK', 'AttributeType': 'S'},
            {'AttributeName': 'GlobalSK', 'AttributeType': 'S'},
        ],
        'GlobalSecondaryIndexes': [
            {
                'IndexName': 'UserDataIndex',
                'KeySchema': [
                    {'AttributeName': 'UserPK', 'KeyType': 'HASH'},
                    {'AttributeName': 'UserSK', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5,
                },
            },
            {
                'IndexName': 'MessageHierarchyIndex',
                'KeySchema': [
                    {'AttributeName': 'ParentPK', 'KeyType': 'HASH'},
                    {'AttributeName': 'ParentSK', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5,
                },
            },
            {
                'IndexName': 'AdminLookupIndex',
                'KeySchema': [
                    {'AttributeName': 'AdminPK', 'KeyType': 'HASH'},
                    {'AttributeName': 'AdminSK', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5,
                },
            },
            {
                'IndexName': 'GlobalResourceIndex',
                'KeySchema': [
                    {'AttributeName': 'GlobalPK', 'KeyType': 'HASH'},
                    {'AttributeName': 'GlobalSK', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5,
                },
            },
        ],
        'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5},
    }
