# Chat Workbench API Reference

Complete API documentation for Chat Workbench backend endpoints. All endpoints require authentication unless otherwise noted.

## Base URL

```
Production: https://your-domain.com/api
Development: http://localhost:8000/api
```

## Authentication

Chat Workbench uses optional OIDC/JWT Bearer authentication. Production deployments typically use AWS Cognito, while development can run with authentication disabled.

### Authentication Header

```http
Authorization: Bearer <jwt_token>
```

### Development Bypass

For development only, authentication can be bypassed by setting `AUTH_ENABLED=false` in environment variables.

## Core Endpoints

### Health Check

Monitor service availability and dependencies.

```http
GET /api/health
```

**Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-01T12:00:00Z",
  "clients": {
    "dynamodb": {
      "available": true,
      "type": "DynamoDB",
      "error": null
    },
    "bedrock": {
      "available": true,
      "type": "Bedrock",
      "error": null
    },
    "s3": {
      "available": true,
      "type": "S3",
      "error": null
    }
  }
}
```

### Metrics

Prometheus-formatted metrics for monitoring.

```http
GET /api/metrics
```

**Response:** Prometheus metrics format

### Cache Management

#### Get Cache Statistics

```http
GET /api/cache/stats
```

**Response:**

```json
{
  "hits": 1250,
  "misses": 150,
  "hit_rate": 0.89,
  "total_keys": 400
}
```

#### Flush Cache

```http
POST /api/cache/flush
```

**Response:**

```json
{
  "message": "Cache flushed successfully"
}
```

## Chat API (v1)

All v1 endpoints are prefixed with `/api/v1/`.

### Chat Management

#### List User Chats

Get paginated list of user's chat sessions.

```http
GET /api/v1/chat
```

**Query Parameters:**

- `user_id` (string, optional): User ID to filter by
- `status` (string, optional): Filter by status (active|archived|deleted, default: active)
- `limit` (integer, optional): Number of chats to return (default: 100, max: 100)
- `last_key` (string, optional): Pagination key for next page
- `with_messages` (integer, optional): Include messages for N most recent chats (default: 5, max: 10)

**Response:**

```json
{
  "chats": [
    {
      "chat_id": "chat_abc123",
      "user_id": "user_123",
      "title": "My Chat Session",
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T13:30:00Z",
      "status": "active",
      "messages": [
        {
          "message_id": "msg_001",
          "chat_id": "chat_abc123",
          "parent_id": null,
          "kind": "request",
          "parts": [
            {
              "part_kind": "text",
              "content": "Hello, how can you help me today?"
            }
          ],
          "timestamp": "2024-01-01T12:00:00Z",
          "status": "complete"
        }
      ],
      "metadata": {},
      "usage": {}
    }
  ],
  "last_evaluated_key": null
}
```

#### Create New Chat

Start a new chat session.

```http
POST /api/v1/chat
```

**Request Body:**

```json
{
  "title": "My New Chat",
  "user_id": "user_123",
  "metadata": {
    "source": "web_ui",
    "tags": ["research", "analysis"]
  }
}
```

**Response:**

```json
{
  "chat_id": "chat_new456",
  "user_id": "user_123",
  "title": "My New Chat",
  "created_at": "2024-01-01T14:00:00Z",
  "updated_at": "2024-01-01T14:00:00Z",
  "status": "active",
  "messages": [],
  "metadata": {
    "source": "web_ui",
    "tags": ["research", "analysis"]
  },
  "usage": {}
}
```

#### Get Chat Details

Retrieve specific chat session information.

```http
GET /api/v1/chat/{chat_id}
```

**Response:**

```json
{
  "chat_id": "chat_abc123",
  "user_id": "user_123",
  "title": "My Chat Session",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T13:30:00Z",
  "status": "active",
  "messages": [
    {
      "message_id": "msg_001",
      "chat_id": "chat_abc123",
      "parent_id": null,
      "kind": "request",
      "parts": [
        {
          "part_kind": "text",
          "content": "Hello, how can you help me today?",
          "timestamp": "2024-01-01T12:00:00Z"
        }
      ],
      "timestamp": "2024-01-01T12:00:00Z",
      "metadata": {},
      "status": "complete"
    }
  ],
  "metadata": {},
  "usage": {}
}
```

#### Update Chat

Modify chat session properties.

```http
PUT /api/v1/chat/{chat_id}
```

**Request Body:**

```json
{
  "title": "Updated Chat Title",
  "status": "active",
  "metadata": {
    "tags": ["updated", "modified"]
  }
}
```

#### Delete Chat

Remove a chat session and all its messages.

```http
DELETE /api/v1/chat/{chat_id}
```

**Response:**

```json
{
  "chat_id": "chat_abc123",
  "user_id": "user_123",
  "title": "My Chat Session",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T13:30:00Z",
  "status": "deleted",
  "messages": [],
  "metadata": {},
  "usage": {}
}
```

### AI Generation

The Chat Workbench uses a unified generation API for all AI interactions. Messages are sent and responses are generated through the generation endpoints.

#### Generate Response (Streaming)

Generate AI responses with real-time streaming.

```http
POST /api/v1/generate/stream
```

**Request Body:**

```json
{
  "task": "chat",
  "chat_id": "chat_abc123",
  "model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
  "parent_id": "msg_parent123",
  "parts": [
    {
      "part_kind": "text",
      "content": "What is the capital of France?"
    }
  ],
  "context": null,
  "persona": "You are a helpful assistant"
}
```

**Response:** Server-Sent Events (SSE) stream

```
data: {"type": "message_start", "message_id": "msg_response123"}

data: {"type": "content_delta", "content": "The"}

data: {"type": "content_delta", "content": " capital"}

data: {"type": "content_delta", "content": " of France is Paris."}

data: {"type": "message_complete", "token_usage": {"input_tokens": 10, "output_tokens": 8}}
```

#### Generate Response (Complete)

Generate complete AI response without streaming.

```http
POST /api/v1/generate/invoke
```

**Request Body:** Same as streaming endpoint

**Response:**

```json
{
  "message_id": "msg_response456",
  "chat_id": "chat_abc123",
  "parts": [
    {
      "part_kind": "text",
      "content": "The capital of France is Paris. It is the largest city in France and serves as the country's political, economic, and cultural center.",
      "timestamp": "2024-01-01T15:00:00Z"
    }
  ],
  "usage": {
    "input_tokens": 10,
    "output_tokens": 32
  },
  "metadata": {}
}
```

#### Retrieve Binary Content

Get binary content by pointer ID.

```http
GET /api/v1/generate/content/{pointer_path}
```

**Response:** Binary content with appropriate headers

### File Management

#### Upload Files

Upload files for use in conversations.

```http
POST /api/v1/files/
```

**Request:** Multipart form data

- `files`: Array of files to upload
- `chat_id` (optional): Associate with specific chat
- `model_id` (optional): Validate compatibility with specific model

**Response:**

```json
{
  "files": [
    {
      "file_id": "file_abc789",
      "mime_type": "application/pdf",
      "filename": "document.pdf",
      "file_type": "document",
      "format": "pdf"
    }
  ]
}
```

#### Retrieve File Content

Get file content by file ID.

```http
GET /api/v1/files/{file_id}
```

**Response:** File content with appropriate headers

### Model Management

#### List Available Models

Get supported AI models and their capabilities.

```http
GET /api/v1/models/
```

**Query Parameters:**

- `provider` (string, optional): Filter models by provider
- `limit` (integer, optional): Maximum number of models to return (default: 100)

**Response:**

```json
{
  "models": [
    {
      "id": "anthropic.claude-3-sonnet-20240229-v1:0",
      "name": "Claude 3 Sonnet",
      "provider": "anthropic",
      "description": "Balanced model for a wide range of tasks",
      "features": [
        {
          "name": "text",
          "description": "Text generation and analysis"
        },
        {
          "name": "multimodal",
          "description": "Supports images and documents"
        }
      ],
      "provider_link": "https://docs.anthropic.com/claude/docs",
      "order": 0,
      "is_available": true
    }
  ]
}
```

#### Get Model Details

Retrieve specific model information.

```http
GET /api/v1/models/{model_id}
```

**Response:**

```json
{
  "id": "anthropic.claude-3-sonnet-20240229-v1:0",
  "name": "Claude 3 Sonnet",
  "provider": "anthropic",
  "description": "Balanced model for a wide range of tasks",
  "features": [
    {
      "name": "text",
      "description": "Text generation and analysis"
    },
    {
      "name": "multimodal",
      "description": "Supports images and documents"
    }
  ],
  "provider_link": "https://docs.anthropic.com/claude/docs",
  "order": 0,
  "is_available": true
}
```

### Persona Management

#### List Personas

Get available conversation personas.

```http
GET /api/v1/persona
```

**Query Parameters:**

- `limit` (integer, optional): Number of personas to return (default: 100, max: 100)
- `last_key` (string, optional): Pagination key for next page
- `is_active` (string, optional): Filter by active status

**Response:**

```json
{
  "personas": [
    {
      "persona_id": "persona_assistant",
      "name": "Helpful Assistant",
      "description": "A helpful, harmless, and honest AI assistant",
      "prompt": "You are a helpful AI assistant...",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z",
      "metadata": {},
      "is_active": true
    }
  ],
  "last_evaluated_key": null
}
```

#### Create Persona

Add a new conversation persona.

```http
POST /api/v1/persona
```

**Request Body:**

```json
{
  "name": "Code Review Assistant",
  "description": "Specialized in code review and best practices",
  "prompt": "You are an expert code reviewer...",
  "metadata": {
    "languages": ["python", "javascript", "typescript"],
    "expertise": ["security", "performance", "maintainability"]
  }
}
```

#### Get Persona

Retrieve specific persona information.

```http
GET /api/v1/persona/{persona_id}
```

#### Update Persona

Modify existing persona.

```http
PUT /api/v1/persona/{persona_id}
```

#### Delete Persona

Remove persona from system (mark as inactive).

```http
DELETE /api/v1/persona/{persona_id}
```

### Prompt Library

#### List Prompts

Get saved prompt templates.

```http
GET /api/v1/prompt
```

**Query Parameters:**

- `limit` (integer, optional): Number of prompts to return (default: 100, max: 100)
- `last_key` (string, optional): Pagination key for next page
- `category` (string, optional): Filter by category
- `is_active` (string, optional): Filter by active status

**Response:**

```json
{
  "prompts": [
    {
      "prompt_id": "prompt_123",
      "name": "Code Explanation",
      "description": "Template for explaining code functionality",
      "content": "Please explain the following code:\n\n{code}\n\nFocus on: {focus_areas}",
      "category": "development",
      "tags": ["code", "explanation"],
      "created_at": "2024-01-01T10:00:00Z",
      "updated_at": "2024-01-01T10:00:00Z",
      "metadata": {},
      "is_active": true
    }
  ],
  "last_evaluated_key": null
}
```

#### Create Prompt Template

Save new prompt template.

```http
POST /api/v1/prompt
```

**Request Body:**

```json
{
  "name": "Document Analysis",
  "description": "Template for analyzing uploaded documents",
  "content": "Analyze the following document and provide insights on: {analysis_points}",
  "category": "analysis",
  "tags": ["document", "analysis"],
  "metadata": {
    "use_cases": ["research", "business_analysis"]
  }
}
```

#### Get Prompt

Retrieve specific prompt information.

```http
GET /api/v1/prompt/{prompt_id}
```

#### Update Prompt

Modify existing prompt.

```http
PUT /api/v1/prompt/{prompt_id}
```

#### Delete Prompt

Remove prompt from system (mark as inactive).

```http
DELETE /api/v1/prompt/{prompt_id}
```

#### Search Prompts

Search prompts by content, name, or description.

```http
GET /api/v1/prompt/search
```

**Query Parameters:**

- `query` (string, required): Search query
- `limit` (integer, optional): Number of prompts to return (default: 100, max: 100)
- `last_key` (string, optional): Pagination key for next page

### Admin Endpoints

Admin endpoints require elevated privileges.

#### Guardrails Management

Configure content safety and guardrails.

##### List Guardrails

```http
GET /api/v1/admin/guardrail/
```

**Response:**

```json
[
  {
    "id": "guardrail_123",
    "name": "Content Filter",
    "description": "Filters inappropriate content",
    "created_at": "2024-01-01T00:00:00Z",
    "versions": [
      {
        "version": "1",
        "created_at": "2024-01-01T00:00:00Z"
      }
    ],
    "current_version": "1"
  }
]
```

##### Create Guardrail

```http
POST /api/v1/admin/guardrail/
```

**Request Body:**

```json
{
  "name": "Content Filter",
  "description": "Filters inappropriate content",
  "content_filters": [
    {
      "type": "HATE",
      "input_strength": "HIGH",
      "output_strength": "HIGH"
    }
  ],
  "denied_topics": [
    {
      "name": "Violence",
      "definition": "Content depicting violence",
      "examples": ["fighting", "weapons"]
    }
  ],
  "word_filters": [
    {
      "text": "badword"
    }
  ],
  "pii_entities": [
    {
      "type": "EMAIL",
      "action": "ANONYMIZE"
    }
  ]
}
```

##### Get Guardrail Details

```http
GET /api/v1/admin/guardrail/{guardrail_id}
```

##### Update Guardrail

```http
PUT /api/v1/admin/guardrail/{guardrail_id}
```

##### Delete Guardrail

```http
DELETE /api/v1/admin/guardrail/{guardrail_id}
```

##### Publish Guardrail Version

```http
POST /api/v1/admin/guardrail/{guardrail_id}/publish
```

#### Task Handler Management

Manage task handlers and their configurations.

##### List Task Handlers

```http
GET /api/v1/admin/task/
```

**Response:**

```json
{
  "handlers": [
    {
      "name": "chat",
      "description": "Standard chat handler",
      "tools": ["search", "calculator"],
      "is_default": true,
      "config": {
        "guardrail": {
          "guardrail_id": "guardrail_123",
          "guardrail_version": "1",
          "enabled": true
        }
      }
    }
  ],
  "last_evaluated_key": null
}
```

##### Get Task Handler

```http
GET /api/v1/admin/task/{name}
```

##### Update Task Handler

```http
PUT /api/v1/admin/task/{name}
```

**Request Body:**

```json
{
  "guardrail": {
    "guardrail_id": "guardrail_123",
    "guardrail_version": "1",
    "enabled": true
  }
}
```

## Message Part Types

Chat Workbench supports multimodal message parts. All parts have the following base structure:

### Base Part Structure

```json
{
  "part_kind": "text|image|document|tool-call|tool-return|reasoning|citation",
  "content": "Content varies by part type",
  "metadata": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Text Part

```json
{
  "part_kind": "text",
  "content": "Your text message here",
  "metadata": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Image Part

```json
{
  "part_kind": "image",
  "content": "base64_encoded_image_data",
  "file_id": "file_img123",
  "user_id": "user_123",
  "mime_type": "image/jpeg",
  "width": 1024,
  "height": 768,
  "format": "jpeg",
  "metadata": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Document Part

```json
{
  "part_kind": "document",
  "content": "document_content",
  "file_id": "file_doc456",
  "mime_type": "application/pdf",
  "pointer": "s3://bucket/path/to/file",
  "title": "Report.pdf",
  "user_id": "user_123",
  "page_count": 25,
  "word_count": 5000,
  "metadata": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Tool Call Part

```json
{
  "part_kind": "tool-call",
  "content": null,
  "tool_name": "calculator",
  "tool_args": {
    "expression": "2 + 2"
  },
  "tool_calls": [
    {
      "id": "call_123",
      "function": "add",
      "arguments": { "a": 2, "b": 2 }
    }
  ],
  "tool_id": "tool_123",
  "metadata": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Tool Return Part

```json
{
  "part_kind": "tool-return",
  "content": null,
  "tool_name": "calculator",
  "tool_id": "tool_123",
  "result": {
    "answer": 4
  },
  "metadata": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Reasoning Part

```json
{
  "part_kind": "reasoning",
  "content": "Internal reasoning process",
  "signature": "reasoning_signature",
  "redacted_content": "base64_encoded_redacted_content",
  "metadata": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Citation Part

```json
{
  "part_kind": "citation",
  "content": "Referenced text content",
  "document_id": "doc_123",
  "text": "The cited text from the document",
  "page": 5,
  "section": "Introduction",
  "citation_id": "citation_123",
  "reference_number": "[1]",
  "document_title": "Research Paper",
  "document_pointer": "s3://bucket/path/to/document",
  "metadata": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Error Responses

All endpoints follow consistent error response format:

### Error Format

```json
{
  "detail": [
    {
      "loc": ["body", "model_id"],
      "msg": "Model not found",
      "type": "value_error"
    }
  ]
}
```

### Common Error Codes

| HTTP Status | Description                             |
| ----------- | --------------------------------------- |
| 400         | Bad Request - Invalid parameters        |
| 401         | Unauthorized - Missing/invalid auth     |
| 403         | Forbidden - Insufficient permissions    |
| 404         | Not Found - Resource doesn't exist      |
| 422         | Validation Error - Invalid request body |
| 429         | Too Many Requests - Rate limited        |
| 500         | Internal Server Error                   |
| 503         | Service Unavailable                     |

## Model Availability

Available models depend on your deployment type and AWS region:

### Commercial AWS Regions

Full model catalog including:

- Claude 3.5 Sonnet
- Claude 3 Opus
- Claude 3 Haiku
- Titan models
- Cohere models
- Meta Llama models

### AWS GovCloud Regions

Limited model selection based on GovCloud availability:

- Claude 3 Sonnet
- Claude 3 Haiku
- Select Titan models

### Model Configuration

Models are loaded from a JSON configuration file located at:
`backend/app/api/routes/v1/models/models.json`

The available models are determined by:

1. AWS region capabilities
2. Model approval status
3. Deployment configuration

### Model Features

Each model includes feature information:

- **Text generation**: Basic text input/output
- **Multimodal**: Support for images and documents
- **Tool calling**: Function/tool invocation capabilities
- **Streaming**: Real-time response streaming

## Rate Limits

Rate limiting is implemented via middleware. Default limits vary by endpoint and can be configured per deployment.

Rate limit information is not currently exposed in response headers but may be added in future versions.

## Pagination

List endpoints support key-based pagination:

**Query Parameters:**

- `limit`: Number of items per page (default varies by endpoint, max 100)
- `last_key`: Last evaluated key from previous response

**Response Format:**

```json
{
  "items": [...],
  "last_evaluated_key": "key_for_next_page"
}
```

## Authentication

Chat Workbench uses optional OIDC/JWT Bearer authentication. In development, authentication can be bypassed.

### Authentication Header

```http
Authorization: Bearer <jwt_token>
```

### User ID Header

Many endpoints accept an optional user ID header:

```http
X-User-Id: user_123
```

## OpenAPI Specification

The complete OpenAPI specification is available at:

- **Development**: `http://localhost:8000/api/openapi.json`
- **Production**: `https://your-domain.com/api/openapi.json`

Interactive documentation is available at:

- **Development**: `http://localhost:8000/docs`
- **Production**: `https://your-domain.com/docs`
