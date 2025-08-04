# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Shared test fixtures and configuration."""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

import boto3
import pytest
from app.api.app import create_app
from app.config import Settings
from fastapi.testclient import TestClient
from moto import mock_aws


# Override settings for testing
@pytest.fixture
def test_settings():
    """Test settings with safe defaults."""
    # Set environment variables for testing
    os.environ.update(
        {
            'AWS_ACCESS_KEY_ID': 'testing',
            'AWS_SECRET_ACCESS_KEY': 'testing',
            'AWS_SECURITY_TOKEN': 'testing',
            'AWS_SESSION_TOKEN': 'testing',
            'AWS_DEFAULT_REGION': 'us-east-1',
            'DYNAMODB_TABLE_NAME': 'test-app-data',
            'VALKEY_HOST': 'localhost',
            'VALKEY_PORT': '6379',
            'AUTH_ENABLED': 'false',  # Disable auth for testing
            'RATE_LIMIT_ENABLED': 'false',  # Disable rate limiting for testing
        }
    )

    settings = Settings(
        api_host='localhost',
        api_port=8000,
        dynamodb_table_name='test-app-data',
        auth_enabled=False,
        rate_limit_enabled=False,
        aws_region='us-east-1',
    )
    return settings


@pytest.fixture
def app(test_settings):
    """Create FastAPI app for testing."""
    # Patch settings globally for the app
    with pytest.MonkeyPatch().context() as m:
        m.setattr('app.config.get_settings', lambda: test_settings)
        app = create_app()
        yield app


@pytest.fixture
def client(app):
    """FastAPI test client."""
    return TestClient(app)


# AWS Mocking Fixtures
@pytest.fixture
def aws_credentials():
    """Mocked AWS credentials for moto."""
    return {
        'aws_access_key_id': 'testing',
        'aws_secret_access_key': 'testing',
        'aws_session_token': 'testing',
    }


@pytest.fixture
def dynamodb_client(aws_credentials):
    """Mocked DynamoDB client."""
    with mock_aws():
        yield boto3.client('dynamodb', region_name='us-east-1')


@pytest.fixture
def dynamodb_resource(aws_credentials):
    """Mocked DynamoDB resource (higher-level interface)."""
    with mock_aws():
        yield boto3.resource('dynamodb', region_name='us-east-1')


@pytest.fixture
def s3_client(aws_credentials):
    """Mocked S3 client."""
    with mock_aws():
        yield boto3.client('s3', region_name='us-east-1')


@pytest.fixture
def bedrock_runtime_client(aws_credentials):
    """Mocked Bedrock Runtime client."""
    with mock_aws():
        yield boto3.client('bedrock-runtime', region_name='us-east-1')


@pytest.fixture
def secrets_manager_client(aws_credentials):
    """Mocked Secrets Manager client."""
    with mock_aws():
        yield boto3.client('secretsmanager', region_name='us-east-1')


@pytest.fixture
def mock_app_table(dynamodb_client):
    """Create a mock DynamoDB table for the app."""
    table_name = 'test-app-data'

    # Create the table
    dynamodb_client.create_table(
        TableName=table_name,
        KeySchema=[
            {'AttributeName': 'PK', 'KeyType': 'HASH'},
            {'AttributeName': 'SK', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'PK', 'AttributeType': 'S'},
            {'AttributeName': 'SK', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )

    return table_name


@pytest.fixture
def mock_content_bucket(s3_client):
    """Create a mock S3 bucket for content storage."""
    bucket_name = 'test-chat-content'
    s3_client.create_bucket(Bucket=bucket_name)
    return bucket_name


# Test Data Factories
@pytest.fixture
def sample_chat_id():
    """Sample chat ID."""
    return 'chat_test_123'


@pytest.fixture
def sample_user_id():
    """Sample user ID."""
    return 'user_test_456'


@pytest.fixture
def sample_message_id():
    """Sample message ID."""
    return 'msg_test_789'


@pytest.fixture
def sample_message_data():
    """Sample message data for testing."""
    return {
        'message_id': 'msg_test_789',
        'chat_id': 'chat_test_123',
        'kind': 'request',
        'parts': [{'part_kind': 'text', 'content': 'Hello, this is a test message.'}],
        'timestamp': datetime.now(timezone.utc),
        'metadata': {'test': True},
    }


@pytest.fixture
def sample_chat_session_data(sample_chat_id, sample_user_id):
    """Sample chat session data for testing."""
    return {
        'chat_id': sample_chat_id,
        'user_id': sample_user_id,
        'title': 'Test Chat Session',
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc),
        'status': 'active',
        'messages': [],
        'metadata': {'test': True},
        'usage': {},
    }


# Mock Service Fixtures
@pytest.fixture
def mock_content_storage_service():
    """Mocked ContentStorageService for testing."""
    from unittest.mock import AsyncMock

    service = AsyncMock()
    service.get_pointer_from_id.return_value = (
        's3://test-bucket/test-path/mock-file.jpg'
    )
    return service


@pytest.fixture
def mock_bedrock_response():
    """Mock Bedrock API response."""
    return {
        'ResponseMetadata': {
            'RequestId': 'test-request-id',
            'HTTPStatusCode': 200,
        },
        'body': MagicMock(),
        'contentType': 'application/json',
    }


@pytest.fixture
def mock_streaming_response():
    """Mock streaming response from Bedrock."""

    class MockStreamingBody:
        def __init__(self):
            self.events = [
                {'chunk': {'bytes': b'{"type": "content_block_start"}'}},
                {
                    'chunk': {
                        'bytes': b'{"type": "content_block_delta", "delta": {"text": "Hello"}}'
                    }
                },
                {
                    'chunk': {
                        'bytes': b'{"type": "content_block_delta", "delta": {"text": " world"}}'
                    }
                },
                {'chunk': {'bytes': b'{"type": "content_block_stop"}'}},
                {'chunk': {'bytes': b'{"type": "message_stop"}'}},
            ]
            self.index = 0

        def __iter__(self):
            return self

        def __next__(self):
            if self.index >= len(self.events):
                raise StopIteration
            event = self.events[self.index]
            self.index += 1
            return event

    mock_response = MagicMock()
    mock_response.body = MockStreamingBody()
    return mock_response


# Authentication fixtures (for when auth is enabled)
@pytest.fixture
def mock_user_claims():
    """Mock user claims for authentication testing."""
    return {
        'sub': 'user_test_456',
        'email': 'test@example.com',
        'cognito:groups': ['users'],
        'iat': 1640995200,
        'exp': 1640998800,
    }


@pytest.fixture
def auth_headers(mock_user_claims):
    """Mock authorization headers."""
    # In real tests, you might need to create a valid JWT token
    # This is a simplified version
    return {
        'Authorization': 'Bearer mock-jwt-token',
        'X-User-ID': mock_user_claims['sub'],
    }


# Helper fixtures for complex test scenarios
@pytest.fixture
def populated_chat_session(
    mock_app_table, dynamodb_client, sample_chat_session_data, sample_message_data
):
    """Create a chat session with some messages in DynamoDB."""
    # Put chat session
    dynamodb_client.put_item(
        TableName=mock_app_table,
        Item={
            'PK': {'S': f'CHAT#{sample_chat_session_data["chat_id"]}'},
            'SK': {'S': f'CHAT#{sample_chat_session_data["chat_id"]}'},
            'user_id': {'S': sample_chat_session_data['user_id']},
            'title': {'S': sample_chat_session_data['title']},
            'status': {'S': sample_chat_session_data['status']},
            'created_at': {'S': sample_chat_session_data['created_at'].isoformat()},
            'updated_at': {'S': sample_chat_session_data['updated_at'].isoformat()},
        },
    )

    # Put a message
    dynamodb_client.put_item(
        TableName=mock_app_table,
        Item={
            'PK': {'S': f'CHAT#{sample_chat_session_data["chat_id"]}'},
            'SK': {'S': f'MSG#{sample_message_data["message_id"]}'},
            'message_id': {'S': sample_message_data['message_id']},
            'kind': {'S': sample_message_data['kind']},
            'content': {'S': str(sample_message_data['parts'])},
            'timestamp': {'S': sample_message_data['timestamp'].isoformat()},
        },
    )

    return sample_chat_session_data


# Circuit breaker testing fixtures
@pytest.fixture
def failing_service():
    """Mock service that always fails (for circuit breaker testing)."""
    mock = MagicMock()
    mock.side_effect = Exception('Service unavailable')
    return mock


@pytest.fixture
def slow_service():
    """Mock service that simulates slow responses."""
    import asyncio

    async def slow_method(*args, **kwargs):
        await asyncio.sleep(0.1)  # Simulate slow response
        return {'status': 'success'}

    mock = MagicMock()
    mock.side_effect = slow_method
    return mock
