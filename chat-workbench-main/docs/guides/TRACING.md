# Tracing with Jaeger

This guide explains how to use the tracing functionality in the Chat Workbench application.

## Overview

The Chat Workbench application uses OpenTelemetry for distributed tracing, with Jaeger as the tracing backend. This allows you to visualize the flow of requests through the application, including LLM interactions, retrievers, tool usage, and event loop processing.

## Features

- **OpenTelemetry Integration**: Native integration with OpenTelemetry, an industry standard for distributed tracing.
- **Jaeger Backend**: Visualize traces using Jaeger UI.
- **Strands Integration**: Automatic tracing of Strands Agent operations.
- **Custom Instrumentation**: Trace custom operations using decorators and context managers.

## Setup

The tracing functionality is already set up in the application. To use it, you need to:

1. Start the application with Docker Compose:

```bash
docker-compose up
```

2. Access the Jaeger UI at http://localhost:16686

## Configuration

The tracing functionality can be configured using environment variables:

- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`: The endpoint for the OTLP exporter (default: `http://jaeger:4318/v1/traces`)
- `OTEL_SERVICE_NAME`: The name of the service (default: `chat-workbench`)
- `OTEL_TRACES_SAMPLER`: The sampling strategy (default: `parentbased_always_on`)
- `OTEL_PROPAGATORS`: The propagators to use (default: `tracecontext,baggage`)
- `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED`: Whether to enable auto-instrumentation for logging (default: `true`)
- `OTEL_DEBUG`: Whether to enable debug mode with console export (default: `false`)

## Usage

### Viewing Traces

1. Open the Jaeger UI at http://localhost:16686
2. Select the `chat-workbench` service
3. Click "Find Traces" to see all traces
4. Click on a trace to see its details

### Understanding Traces

Each trace consists of multiple spans that represent different operations in the application's execution flow:

- **Agent Span**: The top-level span representing the entire agent invocation
- **Cycle Spans**: Child spans for each event loop cycle
- **LLM Spans**: Model invocation spans
- **Tool Spans**: Tool execution spans

### Custom Instrumentation

The application provides several ways to add custom instrumentation:

### Function Decorators

```python
from app.tracing import trace_function, trace_async_function

@trace_function(name="my_function")
def my_function():
    # Function code here
    pass

@trace_async_function(name="my_async_function")
async def my_async_function():
    # Async function code here
    pass
```

### HTTPX Client Instrumentation

For HTTP client requests, we use the OpenTelemetry HTTPX instrumentation:

```python
import httpx
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Instrument all clients (already done in the application)
HTTPXClientInstrumentor().instrument()

# Or instrument a specific client
client = httpx.Client()
HTTPXClientInstrumentor.instrument_client(client)

# Make requests as usual
response = client.get("https://example.com")
```

#### Context Manager

```python
from app.tracing import create_span

with create_span("my_operation", attributes={"key": "value"}):
    # Code to trace here
    pass
```

## Strands Integration

The Strands Agent is automatically instrumented with tracing. You can add custom attributes to the traces:

```python
agent = Agent(
    model="us.anthropic.claude-sonnet-4-20250514-v1:0",
    system_prompt="You are a helpful AI assistant",
    trace_attributes={
        "chat_id": chat_id,
        "response_id": response_message_id,
    },
)
```

## Troubleshooting

If you're not seeing traces in Jaeger:

1. Check that the Jaeger service is running: `docker-compose ps jaeger`
2. Verify that the application is sending traces: `docker-compose logs app | grep "OpenTelemetry tracing initialized"`
3. Ensure the `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` environment variable is set correctly to `http://jaeger:4318/v1/traces` (not `http://localhost:4318/v1/traces`)
4. Try enabling debug mode by setting `OTEL_DEBUG=true` to see trace output in the console

## Advanced Configuration

### Sampling Control

For high-volume applications, you may want to implement sampling to reduce the volume of data:

```
OTEL_TRACES_SAMPLER=traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1  # Sample 10% of traces
```

### Custom Attribute Tracking

You can add custom attributes to any span:

```python
with create_span("my_operation", attributes={"customer_id": "123", "transaction_id": "abc-123"}):
    # Code here
    pass
```
