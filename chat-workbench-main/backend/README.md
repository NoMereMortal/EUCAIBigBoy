# Chat Workbench Backend Development

FastAPI backend for Chat Workbench with Amazon Bedrock integration. This guide covers local development setup, architecture patterns, and extension workflows.

## Tech Stack

- **Framework**: FastAPI with Pydantic v2
- **Language**: Python 3.11+
- **AI Integration**: Amazon Bedrock with multiple model providers
- **Database**: DynamoDB for persistence, OpenSearch for retrieval
- **Caching**: Valkey (Redis-compatible) for performance optimization
- **Authentication**: JWT with AWS Cognito integration

## Architecture Overview

```
backend/app/
├── api/                   # FastAPI application and routing
├── clients/              # External service clients (AWS, databases)
├── repositories/         # Data access layer
├── services/            # Business logic services
├── task_handlers/       # AI task processing (extensible)
├── config.py            # Configuration management
├── models.py            # Pydantic data models
└── utils.py             # Utility functions
```

**Key Concept**: Task handlers are the extensibility point. The chat handler is just one example - build RAG systems, document processors, or any AI workflow by creating custom task handlers.

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- AWS CLI configured with Bedrock access
- uv package manager (recommended) or pip

### Development Setup

```bash
# 1. Install dependencies
cd backend
uv sync

# 2. Start development environment (from project root)
docker compose up -d

# 3. Start backend with hot reload
HOT_RELOAD=true python -m app.api.main

# 4. Verify setup
curl http://localhost:8000/api/health
```

**Access Points:**

- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/health
- Metrics: http://localhost:8000/api/metrics

## Development

### Development Commands

```bash
# Server
python -m app.api.main                    # Start server
HOT_RELOAD=true python -m app.api.main    # Hot reload mode

# Code Quality
ruff check app/          # Linting
ruff format app/         # Formatting
mypy app/               # Type checking
pytest                  # Run tests

# Package Management
uv sync                 # Install dependencies
uv add package-name     # Add dependency
```

## Development Patterns

### Creating New API Endpoints

1. **Create route handler**:

```python
# app/api/routes/v1/example/endpoints.py
from fastapi import APIRouter, Depends
from app.api.dependencies.auth import get_current_user

router = APIRouter(prefix='/example', tags=['Example'])

@router.get('/items')
async def list_items(user: dict = Depends(get_current_user)):
    return {"items": []}
```

2. **Register in main router**:

```python
# app/api/routes/v1/__init__.py
from .example import router as example_router
router.include_router(example_router)
```

### Adding Business Logic Services

```python
# app/services/example.py
class ExampleService:
    def __init__(self, repo: BaseRepository):
        self.repo = repo

    async def create_item(self, user_id: str, item_data: dict):
        # Validate business rules
        if await self._item_exists(item_data.get('name'), user_id):
            raise ValueError("Item already exists")
        return await self.repo.create(user_id, item_data)
```

### Amazon Bedrock Integration

```python
# app/services/bedrock_example.py
from app.clients.bedrock_runtime.client import BedrockRuntimeClient

class BedrockService:
    def __init__(self, client: BedrockRuntimeClient):
        self.client = client

    async def generate_response(self, messages, model_id, **kwargs):
        bedrock_messages = await Message.to_bedrock_messages(messages)
        body = json.dumps({
            "messages": bedrock_messages,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "temperature": kwargs.get("temperature", 0.7),
        })
        response = await self.client.invoke_model(modelId=model_id, body=body)
        return response.get('content', '')
```

### Message Parts System

```python
from app.models import TextPart, ImagePart, DocumentPart, ToolCallPart

# Multimodal message parts
text_part = TextPart(content="Hello, world!")
image_part = ImagePart(file_id="img_123", mime_type="image/jpeg")
doc_part = DocumentPart(file_id="doc_789", title="Report.pdf")
tool_part = ToolCallPart(tool_name="calculator", tool_args={"expression": "2 + 2"})
```

### Database Operations

```python
# app/repositories/example.py
from app.clients.dynamodb.client import DynamoDBClient

class ExampleRepository:
    def __init__(self, dynamodb_client: DynamoDBClient):
        self.client = dynamodb_client
        self.table_name = "app_data"  # Single table design

    async def create_item(self, item: dict) -> bool:
        return await self.client.put_item(table_name=self.table_name, item=item)

    async def get_item(self, key: dict) -> dict:
        return await self.client.get_item(table_name=self.table_name, key=key)
```

## Creating Custom Task Handlers

Task handlers are the core extensibility mechanism for adding AI capabilities.

### 1. Create Task Handler

```python
# app/task_handlers/my_handler/handler.py
from app.task_handlers.base import BaseTaskHandler

class MyTaskHandler(BaseTaskHandler):
    @property
    def name(self) -> str:
        return "my_handler"

    @property
    def description(self) -> str:
        return "My custom task handler"

    async def handle(self, chat_id: str, message: Message, **context) -> AsyncGenerator:
        # Your custom AI logic here
        # 1. Process user input
        # 2. Call external services
        # 3. Generate AI response
        # 4. Yield structured response
        yield TaskHandlerResult(message=response)
```

### 2. Register Handler

```python
# app/task_handlers/registry.py
from .my_handler.handler import MyTaskHandler

async def initialize_task_handlers():
    return [MyTaskHandler(), ...]
```

### 3. Use in API

```http
POST /api/v1/generate/stream
{
  "task": "my_handler",
  "chat_id": "chat_123",
  "messages": [...]
}
```

## Configuration

```python
from app.config import get_settings

settings = get_settings()
api_config = settings.api
aws_config = settings.aws
```

**Key Environment Variables:**

```bash
API_HOST=localhost
API_PORT=8000
AWS_REGION=us-east-1
AUTH_ENABLED=true
CONTENT_STORAGE_BASE_BUCKET=chat-content
```

## Testing

The testing framework is built on `pytest`, with a focus on clear structure, categorization, and comprehensive coverage analysis.

### Test Organization

The `tests/` directory mirrors the `app/` source directory structure. For example, tests for `app/services/chat.py` are located in `tests/services/test_chat.py`. This convention makes it easy to locate tests for specific components.

- `tests/api/`: API endpoint tests
- `tests/services/`: Business logic service tests
- `tests/repositories/`: Data access layer tests
- `tests/task_handlers/`: Core AI task handler tests
- `tests/clients/`: Tests for external service clients

### Running Tests

Execute tests from the `backend` directory:

```bash
# Run all tests with default settings
uv run pytest

# Run tests in parallel for speed (auto-detects CPU cores)
uv run pytest -n auto

# Run only tests for a specific directory
uv run pytest tests/services/

# Run tests with a specific keyword in the name
uv run pytest -k "chat"
```

### Test Categories (Markers)

Tests are categorized using `pytest` markers to allow for targeted test runs. You can run a specific category using the `-m` flag:

```bash
# Run only integration tests
uv run pytest -m integration

# Run all tests EXCEPT slow ones
uv run pytest -m "not slow"

# Run high-priority task handler tests
uv run pytest -m task_handler
```

Available markers defined in `pyproject.toml`:

- `unit`: Fast unit tests (default)
- `integration`: Integration tests with external services
- `slow`: Tests that take >5 seconds
- `aws`: Tests requiring AWS services/credentials
- `api`: API endpoint tests
- `repository`: Repository/database tests
- `service`: Service layer tests
- `task_handler`: Task handler tests (highest priority)
- `auth`: Authentication and authorization tests
- `data`: Data layer and repository pattern tests

### Coverage Reporting

Code coverage is automatically calculated when running `pytest`. The configuration enforces a minimum coverage threshold of 80%.

```bash
# The default pytest command runs coverage automatically
uv run pytest
```

**Coverage Reports:**

- **Console Report**: Summary printed after test run, showing per-file coverage and missed lines
- **HTML Report**: Detailed interactive report generated in `htmlcov/` directory. Open `htmlcov/index.html` in browser
- **XML Report**: `coverage.xml` file generated for CI/CD integration

If coverage drops below the 80% threshold, the test suite will fail.

## Monitoring

**Health Check**: `GET /api/health`
**Metrics**: `GET /api/metrics` (Prometheus format)

Available metrics:

- HTTP request metrics
- Response times and error rates
- Token usage
- Cache hit rates

## Performance Optimization

### Caching with Valkey

```python
from app.clients.valkey.client import ValkeyClient

async def cached_operation(valkey_client: ValkeyClient):
    cached = await valkey_client.get("cache_key")
    if cached:
        return cached

    result = await expensive_operation()
    await valkey_client.setex("cache_key", 3600, result)
    return result
```

### Database Optimization

- Single table design in DynamoDB
- Efficient query patterns with proper indexing
- Connection pooling for all AWS services

## Security

### Input Validation

```python
class MessagePart(BaseModel):
    content: Any = Field(..., description='Content must not be empty')

    @field_validator('content')
    def validate_content(cls, v):
        if v is None:
            raise ValueError('Content field must not be empty')
        return v
```

### Authentication

```python
async def get_current_user(token: str = Depends(get_auth_token)):
    # JWT token validation with AWS Cognito
    return user_info
```

## Troubleshooting

### Common Issues

1. **AWS Credentials**: Ensure proper AWS configuration and Bedrock access
2. **Database Connections**: Check DynamoDB connectivity and table configuration
3. **File Upload Issues**: Verify S3 bucket permissions
4. **Authentication Errors**: Check Cognito configuration

### Debug Commands

```bash
# Test AWS connectivity
python -c "import boto3; client = boto3.client('bedrock', region_name='us-east-1'); print('Bedrock OK')"

# Check configuration
python -c "from app.config import get_settings; print(get_settings().model_dump())"

# Test database connection
python -c "from app.clients.dynamodb.client import DynamoDBClient; print('DynamoDB client OK')"
```

## Next Steps

- **API Documentation**: See [API Reference](../docs/API-REFERENCE.md) for complete endpoint documentation
- **Task Handler Examples**: Check `app/task_handlers/` for RAG and chat implementations
- **Architecture Guide**: Read [Architecture Overview](../docs/ARCHITECTURE.md) for system design
- **Deployment**: See [Infrastructure Guide](../infrastructure/cdk/README.md) for production deployment
