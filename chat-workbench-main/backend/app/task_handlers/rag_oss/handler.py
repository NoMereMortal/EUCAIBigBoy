# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Strands demo task handler for demonstrating Strands Agent with calculator tool."""

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from botocore.config import Config as BotocoreConfig
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from loguru import logger
from strands import Agent
from strands_tools import calculator, http_request

from app.clients.bedrock_runtime.client import BedrockRuntimeClient
from app.clients.opensearch.client import OpenSearchClient
from app.models import Message
from app.services.streaming.events import (
    BaseEvent,
    ContentEvent,
    DocumentEvent,
    ErrorEvent,
    MetadataEvent,
    ReasoningEvent,
    ResponseEndEvent,
    StatusEvent,
)
from app.task_handlers.base import BaseTaskHandler
from app.task_handlers.rag_oss.events import (
    FINAL_STOP_REASONS,
    ContentBlockContext,
    get_event_type,
    is_enriched_event,
    is_init_event,
    parse_tool_args,
)
from app.task_handlers.rag_oss.retrieval import (
    add_citation,
    add_document,
    knowledge_base_search,
    set_clients,
    status_update,
)
from app.tracing import create_span, trace_async_generator_function
from app.utils import generate_nanoid


def recursively_parse_json(value):
    """
    Recursively parse JSON strings until we get a non-JSON string or a dict.

    Args:
        value: The value to parse, which might be a JSON string or any other type

    Returns:
        The parsed value, with any nested JSON strings also parsed
    """
    if not isinstance(value, str):
        return value

    try:
        parsed = json.loads(value)
        # If it's a dict, recursively parse its values
        if isinstance(parsed, dict):
            for key, val in parsed.items():
                parsed[key] = recursively_parse_json(val)
        return parsed
    except Exception:
        # If it's not valid JSON, return the original string
        return value


def normalize_status_event(status_event):
    """
    Normalize a status event to ensure the status field is a simple string and all details are in the message field.

    Args:
        status_event: The StatusEvent object to normalize

    Returns:
        A normalized StatusEvent object
    """
    # Make a deep copy to avoid modifying the original
    event = deepcopy(status_event)

    # Recursively parse any JSON strings in the message field
    if hasattr(event, 'message') and event.message:
        message_data = recursively_parse_json(event.message)

        # If parsing resulted in a dict, ensure it has required fields
        if isinstance(message_data, dict):
            # Ensure the message has a proper title
            if 'title' not in message_data or message_data['title'] == 'Processing...':
                if 'text' in message_data:
                    message_data['title'] = message_data['text'][:50] + (
                        '...' if len(message_data['text']) > 50 else ''
                    )
                else:
                    message_data['title'] = 'Processing research'

            # Convert dict back to JSON string for StatusEvent compatibility
            event.message = json.dumps(message_data)
        else:
            # If parsing didn't result in a dict, create a new message dict
            event.message = json.dumps(
                {'text': str(event.message), 'title': 'Processing research'}
            )

    # Check if status is a JSON string or a long descriptive text
    if hasattr(event, 'status') and event.status:
        raw_status = event.status
        status_type = None

        # Try to extract status type if it's a JSON string
        if isinstance(raw_status, str) and raw_status.startswith('{'):
            try:
                status_obj = recursively_parse_json(raw_status)
                if isinstance(status_obj, dict) and 'type' in status_obj:
                    status_type = status_obj['type']

                    # If message is empty or just a title, use data from status_obj
                    if (
                        not hasattr(event, 'message')
                        or not event.message
                        or event.message == '{"title": "Processing..."}'
                    ):
                        message_data = {
                            k: v for k, v in status_obj.items() if k != 'type'
                        }
                        if 'title' not in message_data:
                            message_data['title'] = 'Processing research'
                        # Convert dict to JSON string for StatusEvent compatibility
                        event.message = json.dumps(message_data)
            except Exception as e:
                # Keep original if parsing fails
                logger.debug(f'Error parsing status object: {e}')

        # Extract message content for phase detection
        message_content = ''
        if hasattr(event, 'message') and event.message:
            try:
                message_data = json.loads(event.message)
                if isinstance(message_data, dict):
                    message_content = message_data.get('text', '').lower()
            except Exception as e:
                logger.debug(f'Error parsing message data: {e}')
                message_content = str(event.message).lower()

        # If not a JSON string but contains common status types, extract them
        if not status_type:
            # Determine status type based on message content first
            if 'beginning research' in message_content or 'start' in message_content:
                status_type = 'research_start'
            elif (
                'research complete' in message_content or 'completed' in message_content
            ):
                status_type = 'research_complete'
            # Then check the raw status
            elif 'research_start' in raw_status.lower():
                status_type = 'research_start'
            elif (
                'research_progress' in raw_status.lower()
                or 'analyzing' in raw_status.lower()
            ):
                status_type = 'research_progress'
            elif (
                'research_complete' in raw_status.lower()
                or 'compiling' in raw_status.lower()
            ):
                status_type = 'research_complete'
            elif 'http_request' in raw_status.lower():
                status_type = 'http_request'
            else:
                # Default to research_progress for any other descriptive text
                status_type = 'research_progress'

                # If the message is empty or just a title, create a message with the descriptive text
                if (
                    not hasattr(event, 'message')
                    or not event.message
                    or event.message == '{"title": "Processing..."}'
                ):
                    message_data = {
                        'text': raw_status,
                        'title': raw_status[:50] + '...'
                        if len(raw_status) > 50
                        else raw_status,
                    }
                    # Convert dict to JSON string for StatusEvent compatibility
                    event.message = json.dumps(message_data)

        # Set the normalized status
        if status_type:
            event.status = status_type

    return event


def repair_tool_sequences(
    bedrock_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Repair tool call sequences by converting tool calls to text blocks.

    AWS Bedrock requires that every tool_use block in an assistant message has a corresponding
    tool_result block in the immediately following user message. Instead of trying to create
    synthetic tool results, this function converts tool calls into descriptive text blocks,
    eliminating the need for tool results entirely.

    Args:
        bedrock_messages: List of messages in Bedrock format

    Returns:
        List of messages with tool calls converted to text blocks
    """
    if not bedrock_messages:
        logger.debug('No messages to repair')
        return bedrock_messages

    logger.debug(
        f'Starting tool-to-text conversion for {len(bedrock_messages)} messages'
    )

    # Log the structure of messages for debugging
    for i, msg in enumerate(bedrock_messages):
        logger.debug(
            f'Message {i}: role={msg.get("role", "unknown")}, content_blocks={len(msg.get("content", []))}'
        )
        if msg.get('content'):
            for j, content in enumerate(msg['content']):
                if isinstance(content, dict):
                    content_keys = list(content.keys())
                    logger.debug(f'Message {i}, Block {j}: {content_keys}')

    repaired_messages = []

    for i, message in enumerate(bedrock_messages):
        # Check if this is an assistant message with tool uses
        if message.get('role') == 'assistant' and message.get('content'):
            modified_content = []
            tool_calls_converted = 0

            for j, content_block in enumerate(message.get('content', [])):
                if isinstance(content_block, dict):
                    tool_use_info = None
                    tool_name = None
                    tool_input = None

                    # Check different possible formats for tool calls
                    if 'toolUse' in content_block:
                        tool_use_info = content_block['toolUse']
                    elif 'tool_use' in content_block:
                        tool_use_info = content_block['tool_use']
                    elif 'tooluse' in content_block:
                        tool_use_info = content_block['tooluse']

                    if tool_use_info and isinstance(tool_use_info, dict):
                        # Extract tool information
                        tool_name = tool_use_info.get('name', 'unknown_tool')
                        tool_input = tool_use_info.get('input', {})
                        tool_id = (
                            tool_use_info.get('toolUseId')
                            or tool_use_info.get('tool_use_id')
                            or tool_use_info.get('id', 'unknown_id')
                        )

                        # Convert tool call to descriptive text
                        text_description = _synthesize_tool_call_to_text(
                            tool_name, tool_input, tool_id
                        )

                        # Replace tool call with text block
                        modified_content.append({'text': text_description})
                        tool_calls_converted += 1

                        logger.info(
                            f'Converted tool call in message {i}, block {j}: {tool_name} -> text'
                        )
                        logger.debug(f'Tool text: {text_description}')
                    else:
                        # Keep non-tool content blocks as-is
                        modified_content.append(content_block)
                else:
                    # Keep non-dict content as-is
                    modified_content.append(content_block)

            if tool_calls_converted > 0:
                # Create modified message with converted content
                modified_message = message.copy()
                modified_message['content'] = modified_content
                repaired_messages.append(modified_message)
                logger.info(
                    f'Message {i}: Converted {tool_calls_converted} tool calls to text'
                )
            else:
                # No tool calls found, keep message as-is
                repaired_messages.append(message)
        else:
            # Non-assistant messages or messages without content, keep as-is
            repaired_messages.append(message)

    logger.info(
        f'Tool-to-text conversion complete: {len(bedrock_messages)} -> {len(repaired_messages)} messages'
    )

    # Final validation - ensure no tool calls remain
    remaining_tool_calls = 0
    for i, msg in enumerate(repaired_messages):
        if msg.get('role') == 'assistant':
            for content_block in msg.get('content', []):
                if isinstance(content_block, dict) and any(
                    key in content_block for key in ['toolUse', 'tool_use', 'tooluse']
                ):
                    remaining_tool_calls += 1
                    logger.warning(
                        f'Message {i} still contains tool call: {list(content_block.keys())}'
                    )

    if remaining_tool_calls == 0:
        logger.debug('VALIDATION PASSED: All tool calls converted to text')
    else:
        logger.error(f'VALIDATION FAILED: {remaining_tool_calls} tool calls remain')

    return repaired_messages


def _synthesize_tool_call_to_text(
    tool_name: str, tool_input: dict[str, Any], tool_id: str
) -> str:
    """
    Convert a tool call into a descriptive text representation.

    Args:
        tool_name: Name of the tool being called
        tool_input: Input parameters for the tool
        tool_id: Unique identifier for the tool call

    Returns:
        Descriptive text representation of the tool call
    """
    try:
        # Handle different tool types with specific descriptions
        if tool_name == 'status_update':
            status = tool_input.get('status', 'unknown')
            message_data = tool_input.get('message_data', {})

            if isinstance(message_data, dict):
                phase = message_data.get('phase', '')
                text = message_data.get('text', '')
                title = message_data.get('title', '')

                if title:
                    return f'[Status Update: {status}] {title}'
                elif text:
                    return f'[Status Update: {status}] {text}'
                elif phase:
                    return f'[Status Update: {status}] Phase: {phase}'
                else:
                    return f'[Status Update: {status}]'
            else:
                return f'[Status Update: {status}] {message_data!s}'

        elif tool_name == 'knowledge_base_search':
            query = tool_input.get('query', '')
            return f'[Knowledge Search] Searching for: {query}'

        elif tool_name == 'http_request':
            url = tool_input.get('url', '')
            method = tool_input.get('method', 'GET')
            return f'[HTTP Request] {method} {url}'

        elif tool_name == 'calculator':
            expression = tool_input.get('expression', '')
            return f'[Calculator] Computing: {expression}'

        elif tool_name == 'add_document':
            title = tool_input.get('title', '')
            return f'[Document Added] {title}'

        elif tool_name == 'add_citation':
            document_id = tool_input.get('document_id', '')
            text_preview = str(tool_input.get('text', ''))[:50]
            return f'[Citation Added] From {document_id}: {text_preview}...'

        else:
            # Generic tool call description
            if tool_input:
                # Try to create a meaningful description from the input
                input_summary = _summarize_tool_input(tool_input)
                return f'[Tool: {tool_name}] {input_summary}'
            else:
                return f'[Tool: {tool_name}] Executed'

    except Exception as e:
        logger.warning(f'Error synthesizing tool call text for {tool_name}: {e}')
        return f'[Tool: {tool_name}] Executed (ID: {tool_id[:8]}...)'


def _summarize_tool_input(tool_input: dict[str, Any]) -> str:
    """
    Create a brief summary of tool input parameters.

    Args:
        tool_input: Dictionary of tool input parameters

    Returns:
        Brief text summary of the input
    """
    try:
        if not tool_input:
            return 'No parameters'

        # Look for common descriptive fields
        descriptive_fields = [
            'query',
            'text',
            'message',
            'topic',
            'title',
            'url',
            'expression',
        ]

        for field in descriptive_fields:
            if tool_input.get(field):
                value = str(tool_input[field])
                if len(value) > 100:
                    return f'{field}: {value[:100]}...'
                else:
                    return f'{field}: {value}'

        # If no descriptive fields found, use first available field
        first_key = next(iter(tool_input.keys()))
        first_value = str(tool_input[first_key])
        if len(first_value) > 50:
            return f'{first_key}: {first_value[:50]}...'
        else:
            return f'{first_key}: {first_value}'

    except Exception as e:
        logger.warning(f'Error summarizing tool input: {e}')
        return 'Parameters provided'


class RagOssHandler(BaseTaskHandler):
    """Demo handler that uses Strands Agent with calculator tool."""

    def __init__(
        self,
        opensearch_client: OpenSearchClient,
        bedrock_runtime_client: BedrockRuntimeClient,
        botocore_config: BotocoreConfig,
    ) -> None:
        super().__init__()
        # Maps contentBlockIndex -> ContentBlockContext
        self._content_blocks = {}
        # Maps tool IDs to names for quick lookups across blocks
        self._tool_id_mapping = {}
        # Store clients for use in tools
        self._opensearch_client = opensearch_client
        self._bedrock_runtime_client = bedrock_runtime_client

        # Initialize clients for knowledge base tools
        set_clients(opensearch_client, bedrock_runtime_client)

    def _get_or_create_block_context(self, index):
        """Get an existing block context or create a new one."""
        if index not in self._content_blocks:
            self._content_blocks[index] = ContentBlockContext()
            self._content_blocks[
                index
            ].start_time = time.time()  # Use float timestamp instead of datetime
        return self._content_blocks[index]

    def _cleanup_block_context(self, index):
        """Clean up a block context when no longer needed."""
        if index in self._content_blocks:
            # Log block completion for debugging
            context = self._content_blocks[index]
            logger.debug(
                f'Cleaning up block {index}: '
                f'type={context.block_type}, tool={context.tool_name}'
            )
            del self._content_blocks[index]

    def _generate_descriptive_title(self, status_value: str, message_data: dict) -> str:
        """Generate a descriptive title for status updates."""
        # Extract key information for title generation
        phase = message_data.get('phase', '')
        text = message_data.get('text', '')
        search_queries = message_data.get('search_queries', [])
        message_data.get('keyword_queries', [])

        # Check for research completion in text
        if 'research complete' in text.lower() or 'completed' in text.lower():
            return 'Research completed'

        # Check for research start in text
        if 'beginning research' in text.lower() or 'start' in text.lower():
            return 'Beginning research analysis'

        # Generate titles based on phase and content
        if phase == 'start':
            return 'Beginning research analysis'

        elif phase == 'planning':
            return 'Planning research strategy'

        elif phase == 'searching':
            search_type = message_data.get('search_type', '')
            if search_type == 'foundation':
                if search_queries and len(search_queries) > 0:
                    # Extract key terms from first search query
                    first_query = str(search_queries[0]).lower()
                    if 'urban' in first_query and 'rural' in first_query:
                        return 'Searching urban-rural data sources'
                    elif 'population' in first_query:
                        return 'Searching population databases'
                    elif 'mapping' in first_query:
                        return 'Searching mapping resources'
                    else:
                        return 'Searching knowledge sources'
                else:
                    return 'Searching knowledge base'
            elif search_type == 'refinement':
                return 'Refining search parameters'
            else:
                return 'Conducting targeted search'

        elif phase == 'evaluating':
            docs_found = message_data.get('documents_found', 0)
            if docs_found:
                return f'Evaluating {docs_found} sources'
            else:
                return 'Assessing search results'

        elif phase == 'analyzing':
            return 'Analyzing research findings'

        elif phase == 'complete':
            return 'Research completed'

        elif phase == 'http_request':
            domain = message_data.get('domain', 'external API')
            return f'Querying {domain}'

        # Fallback based on status_value
        if status_value == 'research_start':
            return 'Beginning research'
        elif status_value == 'research_progress':
            return 'Research in progress'
        elif status_value == 'research_complete':
            return 'Research completed'
        elif status_value == 'http_request':
            return 'Making API request'
        else:
            # Generic title based on text content
            if text and len(text) > 0:
                # Don't truncate titles
                return text.strip()
            else:
                return 'Processing research'

    def create_streaming_callback(
        self, response_message_id: str, content_block_index: int
    ):
        """Create a streaming callback for report generation."""

        def streaming_callback(chunk: str):
            """Callback function to handle streaming chunks from report generator."""
            try:
                # Get or create block context for streaming content
                context = self._get_or_create_block_context(content_block_index)
                if context.block_type is None:
                    context.block_type = 'streaming_report'

                # Increment block sequence counter
                context.block_sequence_counter += 1

                # Create ContentEvent for immediate emission
                if not hasattr(context, 'pending_content_events'):
                    context.pending_content_events = []

                # Create ContentEvent with proper sequence
                content_event = {
                    'type': 'ContentEvent',
                    'response_id': response_message_id,
                    'content': chunk,
                    'content_block_index': content_block_index,
                    'block_sequence': context.block_sequence_counter,
                    'emit': True,
                    'persist': True,
                }

                context.pending_content_events.append(content_event)

                logger.debug(f'Created ContentEvent for chunk: {chunk[:50]}...')

            except Exception as e:
                logger.error(f'Error processing chunk: {e}')

        return streaming_callback

    @property
    def name(self) -> str:
        """Name of the task handler."""
        return 'rag_oss'

    @property
    def description(self) -> str:
        """Description of the task handler."""
        return 'Document search and retrieval-augmented generation using local document collection'

    @property
    def tools(self) -> list[str]:
        """List of tools available to this task handler."""
        return [
            'knowledge_base_search',
            'status_update',
            'add_document',
            'add_citation',
        ]

    async def _convert_user_message(
        self, user_message: Message
    ) -> tuple[list[dict[str, Any]], str]:
        """
        Convert a user message with potential multimodal content into:
        1. A list of Bedrock-format messages that preserve the multimodal context
        2. A text-only string for Strands Agent stream_async()

        Args:
            user_message: The user message object, potentially with multimodal content

        Returns:
            tuple containing:
                - list[dict]: List of Bedrock-format messages with media content blocks
                - str: Text-only content from the user message
        """
        # Initialize variables
        multimodal_messages = []
        text_only_parts = []

        # Split parts by modality
        media_parts = []

        for part in user_message.parts:
            if part.part_kind in ['image', 'document']:
                # Add media part to the list
                media_parts.append(part)
            elif part.part_kind == 'text':
                # Collect text content
                text_only_parts.append(part.content)

        # If we have media parts, create a single message with all media content blocks
        if media_parts:
            # Convert all media parts to Bedrock format - await each one
            content_blocks = []
            for part in media_parts:
                block = await part.to_bedrock()
                content_blocks.append(block)

            # Create a user message with all media parts as content blocks
            media_message = {'role': 'user', 'content': content_blocks}
            multimodal_messages.append(media_message)

            # Add a single assistant acknowledgment message
            ack_message = {
                'role': 'assistant',
                'content': [{'text': "I'll use this media in my response."}],
            }
            multimodal_messages.append(ack_message)

        # Combine text parts into a single string
        text_only_content = ' '.join(text_only_parts) if text_only_parts else ''

        return multimodal_messages, text_only_content

    def _render_system_prompt(self, persona: str | None = None) -> str:
        """
        Render the system prompt template with the provided persona.

        Args:
            persona: Optional persona string to populate in the template

        Returns:
            Rendered system prompt string
        """
        fallback = f'{persona or "You are a helpful AI assistant."}'
        try:
            # Get the path to the prompts directory
            current_dir = Path(__file__).parent
            prompts_dir = current_dir / 'prompts'

            # Set up Jinja2 environment with autoescape enabled for security
            env = Environment(loader=FileSystemLoader(prompts_dir), autoescape=True)
            template = env.get_template('system.xml.j2')

            # Render the template with persona and current date
            context = {
                'persona': persona or 'You are a helpful AI assistant.',
                'current_date': datetime.now(timezone.utc).strftime('%B %d, %Y'),
            }

            rendered_prompt = template.render(context)
            logger.debug(f'Rendered system prompt with persona: {persona}')

            return rendered_prompt

        except TemplateNotFound as e:
            logger.error(f'System prompt template not found: {e}')
            return fallback

        except Exception as e:
            logger.error(f'Error rendering system prompt template: {e}')
            return fallback

    @trace_async_generator_function(name='RagOssHandler.handle')
    async def handle(
        self,
        chat_id: str,
        message_history: list[Message],
        user_message: Message,
        model_id: str,
        response_message_id: str,
        context: list[dict[str, Any]] | None = None,
        persona: str | None = None,
        streaming_service=None,
    ) -> AsyncGenerator[BaseEvent, None]:
        """
        Process the request using Strands Agent with calculator tool.

        This handler demonstrates the use of Strands Agent with streaming responses
        and tool usage, with explicit event conversion and state management.
        """
        try:
            # Reset state at the start of handling
            self._content_blocks = {}
            self._tool_id_mapping = {}

            # Create a span for message processing
            with create_span('process_messages', attributes={'chat_id': chat_id}):
                # Process the user message to handle multimodal content
                # Convert each message to Bedrock format, awaiting each one
                messages = []
                for message in message_history:
                    bedrock_message = await message.to_bedrock()
                    messages.append(bedrock_message)

                # Process user's message
                user_multimodal_messages, user_text = await self._convert_user_message(
                    user_message
                )
            if user_multimodal_messages:
                messages.extend(user_multimodal_messages)

            # Repair tool call sequences to ensure Bedrock compatibility
            # This fixes the validation error by injecting synthetic tool results for orphaned tool calls
            logger.info(f'Starting repair of {len(messages)} messages')

            # Log message structure before repair for debugging
            for i, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content_count = len(msg.get('content', []))
                logger.debug(
                    f'BEFORE: Message {i} - role={role}, content_blocks={content_count}'
                )

            messages = repair_tool_sequences(messages)

            # Log message structure after repair for debugging
            logger.info(f'Repair complete: final message count = {len(messages)}')
            for i, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content_count = len(msg.get('content', []))
                logger.debug(
                    f'AFTER: Message {i} - role={role}, content_blocks={content_count}'
                )

            # Log the final messages being sent to Bedrock in a compact format
            logger.info('Final messages structure:')
            for i, msg in enumerate(messages):
                content_summary = []
                for _j, content in enumerate(msg.get('content', [])):
                    if isinstance(content, dict):
                        if 'text' in content:
                            content_summary.append(
                                f'text({len(content["text"])} chars)'
                            )
                        elif 'toolUse' in content:
                            tool_info = content['toolUse']
                            tool_name = tool_info.get('name', 'unknown')
                            tool_id = tool_info.get('toolUseId', 'unknown')
                            content_summary.append(
                                f'toolUse({tool_name}:{tool_id[:8]}...)'
                            )
                        elif 'toolResult' in content:
                            result_info = content['toolResult']
                            tool_id = result_info.get('toolUseId', 'unknown')
                            status = result_info.get('status', 'unknown')
                            content_summary.append(
                                f'toolResult({tool_id[:8]}...:{status})'
                            )
                        else:
                            content_summary.append(f'other({list(content.keys())})')
                    else:
                        content_summary.append(f'non-dict({type(content)})')

                logger.info(
                    f'Message {i}: {msg.get("role")} -> [{", ".join(content_summary)}]'
                )

            # Create a span for agent initialization
            with create_span('initialize_agent', attributes={'model_id': model_id}):
                # Render the system prompt using the template
                system_prompt = self._render_system_prompt(persona)

                # Log the model ID being used for debugging
                logger.debug(f"Using model ID: '{model_id}' (length: {len(model_id)})")

                # Ensure model ID is correctly formatted (no whitespace)
                model_id = model_id.strip()

                # Use a more direct approach to bypass type checking
                # The messages structure is compatible with what Agent expects
                agent = Agent(
                    model=model_id,  # Explicitly pass the model ID
                    tools=[
                        http_request,
                        knowledge_base_search,
                        status_update,
                        add_document,
                        add_citation,
                        calculator,
                    ],
                    system_prompt=system_prompt,
                    messages=messages,  # type: ignore
                    callback_handler=None,
                    trace_attributes={
                        'chat_id': chat_id,
                        'response_id': response_message_id,
                    },
                )

            # Get agent stream response
            agent_stream = agent.stream_async(user_text)
            try:
                # Initialize state for event processing
                sequence = 0
                usage_metrics = {}

                async for event in agent_stream:
                    logger.debug(f'Processing event: {type(event)}')

                    # Make sure to log any current_tool_use info if present for tracking tool calls and results
                    if isinstance(event, dict) and 'current_tool_use' in event:
                        tool_use = event['current_tool_use']
                        tool_id = tool_use.get('toolUseId', 'unknown')
                        tool_name = tool_use.get('name', 'unknown')
                        tool_input = tool_use.get('input', '')
                        logger.debug(
                            f'Current tool use ID: {tool_id}, Name: {tool_name}, Input: {tool_input}'
                        )

                    logger.debug(f'Raw event from Strands Agent: {event}')
                    if asyncio.iscoroutine(event):
                        logger.warning('Event is a coroutine, awaiting it...')
                        event = await event
                        logger.debug(f'After awaiting event: {type(event)}')

                    # Extract token usage from enriched events BEFORE skipping them
                    if isinstance(event, dict) and 'event_loop_metrics' in event:
                        event_loop_metrics = event['event_loop_metrics']
                        if hasattr(event_loop_metrics, 'accumulated_usage'):
                            strands_usage = event_loop_metrics.accumulated_usage
                            logger.debug(f'Found Strands usage data: {strands_usage}')

                            # Convert Strands usage format to our format
                            if strands_usage:
                                converted_usage = {
                                    'request_tokens': strands_usage.get(
                                        'inputTokens', 0
                                    ),
                                    'response_tokens': strands_usage.get(
                                        'outputTokens', 0
                                    ),
                                    'total_tokens': strands_usage.get('totalTokens', 0),
                                }
                                # Update usage_metrics with latest token counts (they accumulate over time)
                                if (
                                    converted_usage['total_tokens'] > 0
                                ):  # Only update if we have real token counts
                                    usage_metrics.update(converted_usage)
                                    logger.debug(
                                        f'Updated usage_metrics with Strands data: {usage_metrics}'
                                    )

                    # Skip initialization and enriched events
                    if is_init_event(event) or is_enriched_event(event):
                        logger.debug('Skipping initialization or enriched event')
                        continue

                    # Check if event is properly formatted
                    if not isinstance(event, dict):
                        logger.warning(f'Event is not a dict: {type(event)}')
                        continue

                    # Check for tool results in message content (this format appears differently in the events)
                    if (
                        'message' in event
                        and isinstance(event['message'], dict)
                        and 'content' in event['message']
                    ):
                        message_content = event['message'].get('content', [])
                        if isinstance(message_content, list):
                            for content_item in message_content:
                                if (
                                    isinstance(content_item, dict)
                                    and 'toolResult' in content_item
                                ):
                                    tool_result = content_item['toolResult']
                                    tool_use_id = tool_result.get(
                                        'toolUseId', 'unknown'
                                    )
                                    status = tool_result.get('status', 'unknown')

                                    # Log detailed information about the tool result from message
                                    logger.info(
                                        f'[TOOL_RESULT_MESSAGE:{tool_use_id}] Received tool result in message'
                                    )
                                    logger.info(
                                        f'[TOOL_RESULT_MESSAGE:{tool_use_id}] Status: {status}'
                                    )

                                    # Log content details
                                    result_content = tool_result.get('content', [])
                                    if result_content:
                                        for result_item in result_content:
                                            if 'text' in result_item:
                                                logger.info(
                                                    f'[TOOL_RESULT_MESSAGE:{tool_use_id}] Text content: {result_item["text"]}'
                                                )
                                            if 'json' in result_item:
                                                logger.info(
                                                    f'[TOOL_RESULT_MESSAGE:{tool_use_id}] JSON content: {json.dumps(result_item["json"])}'
                                                )
                                            if 'image' in result_item:
                                                logger.info(
                                                    f'[TOOL_RESULT_MESSAGE:{tool_use_id}] Contains image content'
                                                )
                                            if 'document' in result_item:
                                                logger.info(
                                                    f'[TOOL_RESULT_MESSAGE:{tool_use_id}] Contains document content'
                                                )

                    if 'event' not in event:
                        logger.warning("Event doesn't contain 'event' key")
                        continue

                    # Get event data and type
                    event_data = event['event']
                    event_type = get_event_type(event)

                    logger.debug(f'Type: {event_type}')

                    # Process toolResult events - this captures when tool results come back
                    if 'toolResult' in event_data:
                        tool_result = event_data['toolResult']
                        tool_use_id = tool_result.get('toolUseId', 'unknown')
                        status = tool_result.get('status', 'unknown')

                        # Log detailed information about the tool result
                        logger.info(f'[TOOL_RESULT:{tool_use_id}] Received tool result')
                        logger.info(f'[TOOL_RESULT:{tool_use_id}] Status: {status}')

                        # Log content details based on what's available
                        content = tool_result.get('content', [])
                        if content:
                            for content_item in content:
                                if 'text' in content_item:
                                    logger.info(
                                        f'[TOOL_RESULT:{tool_use_id}] Text content: {content_item["text"]}'
                                    )
                                if 'json' in content_item:
                                    logger.info(
                                        f'[TOOL_RESULT:{tool_use_id}] JSON content: {json.dumps(content_item["json"])}'
                                    )
                                if 'image' in content_item:
                                    logger.info(
                                        f'[TOOL_RESULT:{tool_use_id}] Contains image content'
                                    )
                                if 'document' in content_item:
                                    logger.info(
                                        f'[TOOL_RESULT:{tool_use_id}] Contains document content'
                                    )

                    # Process messageStart events
                    elif 'messageStart' in event_data:
                        # Just log the start, no event to emit
                        logger.debug('Message started')

                    # Process contentBlockStart events
                    elif 'contentBlockStart' in event_data:
                        block_start = event_data['contentBlockStart']
                        content_block_index = block_start.get('contentBlockIndex', 0)

                        # Get or create block context
                        context = self._get_or_create_block_context(content_block_index)

                        # Check for tool use starts
                        start_info = block_start.get('start', {})
                        if 'toolUse' in start_info:
                            tool_use = start_info['toolUse']
                            context.tool_name = tool_use.get('name', '')
                            context.tool_id = tool_use.get('toolUseId', '')
                            context.block_type = 'tool_call'

                            # Store in cross-block tool ID mapping
                            if context.tool_id and context.tool_name:
                                self._tool_id_mapping[context.tool_id] = (
                                    context.tool_name
                                )
                                logger.debug(
                                    f'Registered tool: {context.tool_name} with ID {context.tool_id} for block {content_block_index}'
                                )

                    # Process contentBlockDelta events
                    elif 'contentBlockDelta' in event_data:
                        delta_event = event_data['contentBlockDelta']
                        content_block_index = delta_event.get('contentBlockIndex', 0)
                        delta = delta_event.get('delta', {})

                        # Get context for this block
                        context = self._get_or_create_block_context(content_block_index)

                        # Handle text content - emit immediately
                        if 'text' in delta:
                            text = delta['text']
                            if context.block_type is None:
                                context.block_type = 'text'

                            # Increment block sequence counter
                            context.block_sequence_counter += 1

                            sequence += 1
                            content_event = ContentEvent(
                                response_id=response_message_id,
                                content=text,
                                content_block_index=content_block_index,
                                block_sequence=context.block_sequence_counter,
                                sequence=sequence,
                                emit=True,
                                persist=True,
                            )
                            logger.info(
                                f"[SEQUENCE_DEBUG] Created ContentEvent with sequence={sequence}, content='{text[:50]}...'"
                            )
                            yield content_event
                            logger.debug(f'Emitting text content: {text}')

                        # Handle tool result content - capture and log details of tool results
                        elif 'toolResult' in delta:
                            tool_result = delta['toolResult']
                            tool_use_id = tool_result.get('toolUseId', 'unknown')

                            if context.block_type is None:
                                context.block_type = 'tool_result'

                            logger.info(
                                f'[TOOL_RESULT_DELTA:{tool_use_id}] Processing tool result content'
                            )

                            # If there's content, log it
                            content = tool_result.get('content', [])
                            if isinstance(content, list) and content:
                                for item in content:
                                    logger.info(
                                        f'[TOOL_RESULT_DELTA:{tool_use_id}] Content item: {item}'
                                    )

                        # Handle tool use input - accumulate and emit with complete context
                        elif 'toolUse' in delta:
                            # Add to accumulated tool input
                            tool_input_fragment = delta['toolUse'].get('input', '')

                            if context.block_type is None:
                                context.block_type = 'tool_call'

                            context.accumulated_tool_input += tool_input_fragment

                            # Extract or retrieve tool info
                            tool_use = delta.get('toolUse', {})

                            # Get tool ID from delta if missing in context
                            if not context.tool_id:
                                context.tool_id = tool_use.get(
                                    'toolUseId', generate_nanoid()
                                )

                            # Try multiple methods to get the tool name
                            if not context.tool_name:
                                # 1. Try from delta directly
                                context.tool_name = tool_use.get('name', '')

                                # 2. Try from cross-block tool ID mapping
                                if (
                                    not context.tool_name
                                    and context.tool_id in self._tool_id_mapping
                                ):
                                    context.tool_name = self._tool_id_mapping[
                                        context.tool_id
                                    ]

                                # 3. Try pattern matching as fallback
                                if not context.tool_name:
                                    if (
                                        context.tool_id
                                        and 'calc' in context.tool_id.lower()
                                    ):
                                        context.tool_name = 'calculator'
                                        self._tool_id_mapping[context.tool_id] = (
                                            context.tool_name
                                        )
                                        logger.debug(
                                            f'Mapped tool ID to calculator: {context.tool_id}'
                                        )
                                    elif (
                                        context.tool_id
                                        and 'think' in context.tool_id.lower()
                                    ):
                                        context.tool_name = 'think'
                                        self._tool_id_mapping[context.tool_id] = (
                                            context.tool_name
                                        )
                                        logger.debug(
                                            f'Mapped tool ID to think: {context.tool_id}'
                                        )
                                    elif (
                                        context.tool_id
                                        and 'time' in context.tool_id.lower()
                                    ):
                                        context.tool_name = 'current_time'
                                        self._tool_id_mapping[context.tool_id] = (
                                            context.tool_name
                                        )
                                        logger.debug(
                                            f'Mapped tool ID to current_time: {context.tool_id}'
                                        )
                                    elif (
                                        context.tool_id
                                        and 'knowledge' in context.tool_id.lower()
                                    ):
                                        context.tool_name = 'knowledge_base_search'
                                        self._tool_id_mapping[context.tool_id] = (
                                            context.tool_name
                                        )
                                        logger.debug(
                                            f'Mapped tool ID to knowledge_base_search: {context.tool_id}'
                                        )

                        # Handle reasoning content (emit immediately)
                        elif 'reasoningContent' in delta:
                            reasoning = delta['reasoningContent']
                            if context.block_type is None:
                                context.block_type = 'reasoning'

                            # Increment block sequence counter
                            context.block_sequence_counter += 1

                            sequence += 1
                            yield ReasoningEvent(
                                response_id=response_message_id,
                                text=reasoning.get('text'),
                                signature=reasoning.get('signature'),
                                redacted_content=reasoning.get('redactedContent'),
                                content_block_index=content_block_index,
                                block_sequence=context.block_sequence_counter,
                                sequence=sequence,
                                emit=False,
                                persist=False,
                            )
                            logger.debug('Emitting reasoning event')

                    # Process contentBlockStop events
                    elif 'contentBlockStop' in event_data:
                        block_stop = event_data['contentBlockStop']
                        content_block_index = block_stop.get('contentBlockIndex', 0)

                        # Get final context for block before cleanup
                        if content_block_index in self._content_blocks:
                            context = self._content_blocks[content_block_index]
                            logger.debug(
                                f'Content block stopped: {content_block_index}, type={context.block_type}'
                            )

                            # For tool calls with accumulated input, process the complete input
                            if (
                                context.block_type == 'tool_call'
                                and context.accumulated_tool_input
                            ):
                                try:
                                    # Final emission of tool event with complete inputs
                                    if context.tool_name:
                                        # Only emit if we have a proper tool name
                                        logger.debug(
                                            f'Final tool call for {context.tool_name} with input: {context.accumulated_tool_input}'
                                        )

                                        # Log Tool Result completion information
                                        end_time = time.time()
                                        execution_time = end_time - getattr(
                                            context, 'start_time', end_time
                                        )

                                        # Format for ToolResult logging
                                        logger.info(
                                            f'[TOOL_RESULT:{context.tool_id}] Tool execution completed'
                                        )
                                        logger.info(
                                            f'[TOOL_RESULT:{context.tool_id}] Tool type: {context.tool_name}'
                                        )
                                        logger.info(
                                            f'[TOOL_RESULT:{context.tool_id}] Input: {context.accumulated_tool_input}'
                                        )
                                        logger.info(
                                            f'[TOOL_RESULT:{context.tool_id}] Execution time: {execution_time:.2f} seconds'
                                        )
                                        logger.info(
                                            f'[TOOL_RESULT:{context.tool_id}] Status: success'
                                        )

                                        # The following fields match the ToolResult and ToolResultContent TypedDict structure
                                        logger.debug(
                                            f'[TOOL_RESULT:{context.tool_id}] ToolResult structure:'
                                        )
                                        logger.debug(
                                            f'[TOOL_RESULT:{context.tool_id}] - toolUseId: {context.tool_id}'
                                        )
                                        logger.debug(
                                            f'[TOOL_RESULT:{context.tool_id}] - status: success'
                                        )
                                        logger.debug(
                                            f'[TOOL_RESULT:{context.tool_id}] - content: [content objects]'
                                        )
                                except Exception as e:
                                    logger.error(
                                        f'Error processing complete tool input: {e}'
                                    )

                            # Completion-based event generation for tools
                            if context.tool_name in [
                                'status_update',
                                'add_document',
                                'add_citation',
                                'http_request',
                            ]:
                                try:
                                    # Parse the complete accumulated tool input
                                    logger.debug(
                                        f'Parsing tool input for {context.tool_name}: {context.accumulated_tool_input}'
                                    )
                                    tool_args = parse_tool_args(
                                        context.accumulated_tool_input
                                    )
                                    logger.debug(f'Parsed tool args: {tool_args}')

                                    sequence += 1

                                    if context.tool_name == 'status_update':
                                        # Extract status and message_data from first two positional arguments
                                        raw_status_value = tool_args.get('status') or (
                                            tool_args.get('args', [None])[0]
                                            if tool_args.get('args')
                                            else 'research_progress'
                                        )
                                        message_data = tool_args.get(
                                            'message_data'
                                        ) or (
                                            tool_args.get('args', [None, None])[1]
                                            if len(tool_args.get('args', [])) > 1
                                            else {}
                                        )

                                        # Determine the correct status type based on content
                                        status_value = raw_status_value

                                        # Extract just the status type if it's a JSON string
                                        if isinstance(raw_status_value, str):
                                            if raw_status_value.startswith('{'):
                                                try:
                                                    status_obj = json.loads(
                                                        raw_status_value
                                                    )
                                                    if (
                                                        isinstance(status_obj, dict)
                                                        and 'type' in status_obj
                                                    ):
                                                        status_value = status_obj[
                                                            'type'
                                                        ]

                                                        # If message_data is empty, use data from status_obj
                                                        if (
                                                            not message_data
                                                            and isinstance(
                                                                status_obj, dict
                                                            )
                                                        ):
                                                            message_data = {
                                                                k: v
                                                                for k, v in status_obj.items()
                                                                if k != 'type'
                                                            }
                                                except Exception as e:
                                                    # Keep original if parsing fails
                                                    logger.debug(
                                                        f'Error parsing status object: {e}'
                                                    )
                                            # If not a JSON string but contains common status types, extract them
                                            elif 'research_start' in raw_status_value:
                                                status_value = 'research_start'
                                            elif (
                                                'research_progress' in raw_status_value
                                            ):
                                                status_value = 'research_progress'
                                            elif (
                                                'research_complete' in raw_status_value
                                            ):
                                                status_value = 'research_complete'

                                        # Ensure message_data is a dict
                                        if isinstance(message_data, str):
                                            try:
                                                message_data = json.loads(message_data)
                                            except Exception as e:
                                                logger.debug(
                                                    f'Error parsing message data: {e}'
                                                )
                                                message_data = {'text': message_data}
                                        elif not isinstance(message_data, dict):
                                            message_data = {'text': str(message_data)}

                                        # If we have a phase in message_data, use it to determine status type
                                        if (
                                            isinstance(message_data, dict)
                                            and 'phase' in message_data
                                        ):
                                            phase = message_data.get('phase')
                                            if phase == 'start':
                                                status_value = 'research_start'
                                            elif phase in [
                                                'planning',
                                                'searching',
                                                'evaluating',
                                                'analyzing',
                                            ]:
                                                status_value = 'research_progress'
                                            elif phase == 'complete':
                                                status_value = 'research_complete'

                                        # Check message text for additional clues
                                        if (
                                            isinstance(message_data, dict)
                                            and 'text' in message_data
                                        ):
                                            text = message_data.get('text', '').lower()
                                            if (
                                                'beginning research' in text
                                                or 'start' in text
                                            ):
                                                status_value = 'research_start'
                                            elif (
                                                'research complete' in text
                                                or 'completed' in text
                                            ):
                                                status_value = 'research_complete'

                                        # Generate descriptive title from message_data
                                        descriptive_title = (
                                            self._generate_descriptive_title(
                                                status_value, message_data
                                            )
                                        )

                                        # Add title to message_data for frontend use
                                        enhanced_message_data = message_data.copy()

                                        # Always use our descriptive title, overriding any existing title
                                        # This ensures the UI shows the detailed status instead of "Processing..."
                                        enhanced_message_data['title'] = (
                                            descriptive_title
                                        )

                                        # Convert dict to JSON string for StatusEvent compatibility
                                        message = json.dumps(enhanced_message_data)

                                        logger.info(
                                            f"Emitting StatusEvent: status='{status_value}', title='{descriptive_title}', data='{message_data}'"
                                        )

                                        status_event = StatusEvent(
                                            response_id=response_message_id,
                                            status=status_value,
                                            message=message,  # Convert dict to JSON string
                                            sequence=sequence,
                                            emit=True,
                                            persist=True,
                                        )
                                        # Normalize the status event before yielding
                                        yield normalize_status_event(status_event)

                                    elif context.tool_name == 'http_request':
                                        # Generate status event for HTTP requests
                                        method = tool_args.get('method', 'GET').upper()
                                        url = tool_args.get('url', 'external API')

                                        # Extract domain from URL for better display
                                        try:
                                            from urllib.parse import urlparse

                                            parsed_url = urlparse(url)
                                            domain = parsed_url.netloc or url
                                        except Exception as e:
                                            logger.debug(f'Error parsing URL: {e}')
                                            domain = url

                                        message_data = {
                                            'phase': 'http_request',
                                            'text': f'Making {method} request to {domain}',
                                            'method': method,
                                            'url': url,
                                            'domain': domain,
                                            'title': f'Querying {domain}',
                                        }

                                        # Convert dict to JSON string for StatusEvent compatibility
                                        message = json.dumps(message_data)

                                        logger.info(
                                            f'Emitting StatusEvent for HTTP request: {method} {domain}'
                                        )

                                        status_event = StatusEvent(
                                            response_id=response_message_id,
                                            status='http_request',  # Simple string status
                                            message=message,  # Convert dict to JSON string
                                            sequence=sequence,
                                            emit=True,
                                            persist=True,
                                        )
                                        # Normalize the status event before yielding
                                        yield normalize_status_event(status_event)

                                    elif context.tool_name == 'add_document':
                                        # Extract document parameters from tool args
                                        title = (
                                            tool_args.get('title') or 'Unknown Document'
                                        )
                                        source = tool_args.get('source') or ''
                                        document_id = tool_args.get('document_id') or ''
                                        tool_args.get('summary') or ''

                                        logger.info(
                                            f"Emitting DocumentEvent: title='{title}', doc_id='{document_id}'"
                                        )

                                        yield DocumentEvent(
                                            response_id=response_message_id,
                                            title=title,
                                            pointer=source,
                                            document_id=document_id,
                                            mime_type='text/plain',  # Default
                                            sequence=sequence,
                                            emit=True,
                                            persist=True,
                                        )

                                    elif context.tool_name == 'add_citation':
                                        # Generate CitationEvent from tool completion
                                        document_id = tool_args.get('document_id') or ''
                                        text = tool_args.get('text') or ''
                                        page = tool_args.get('page')
                                        section = tool_args.get('section')
                                        citation_id = tool_args.get('citation_id')

                                        logger.info(
                                            f'Emitting CitationEvent from document: {document_id}'
                                        )

                                        from app.services.streaming.events import (
                                            CitationEvent,
                                        )

                                        yield CitationEvent(
                                            response_id=response_message_id,
                                            document_id=document_id,
                                            text=text,
                                            page=page,
                                            section=section,
                                            citation_id=citation_id,
                                            sequence=sequence,
                                            emit=True,
                                            persist=True,
                                        )

                                    logger.debug(
                                        f'Successfully emitted event for tool {context.tool_name}: {context.tool_id}'
                                    )

                                except Exception as e:
                                    logger.error(
                                        f'Error emitting event for tool {context.tool_name}: {e}'
                                    )
                                    logger.error(
                                        f'Tool input was: {context.accumulated_tool_input}'
                                    )
                                    import traceback

                                    logger.error(f'Traceback: {traceback.format_exc()}')

                            # Clean up the context
                            self._cleanup_block_context(content_block_index)

                    # Process messageStop events
                    elif 'messageStop' in event_data:
                        message_stop = event_data['messageStop']
                        stop_reason = message_stop.get('stopReason')

                        logger.debug(f'Message stopped with reason: {stop_reason}')

                        # Clean up any remaining blocks
                        remaining_blocks = list(self._content_blocks.keys())
                        for _ in remaining_blocks:
                            self._cleanup_block_context(_)

                        # Check if this is a final stop or should continue
                        if stop_reason in FINAL_STOP_REASONS:
                            # Emit final response end event
                            sequence += 1
                            logger.debug(
                                f'Final usage_metrics being sent in ResponseEndEvent: {usage_metrics}'
                            )
                            yield ResponseEndEvent(
                                response_id=response_message_id,
                                status='completed',
                                usage=usage_metrics,
                                sequence=sequence,
                                emit=True,
                                persist=True,
                                chat_id=chat_id,
                            )
                            logger.debug(
                                f'Response completed with reason: {stop_reason}'
                            )
                            return
                        else:
                            logger.debug(
                                f'Response continuing due to stop reason: {stop_reason}'
                            )

                    # Process metadata events
                    elif 'metadata' in event_data:
                        metadata = event_data['metadata']
                        logger.debug(f'Received metadata event: {metadata}')

                        # Update usage metrics
                        if 'usage' in metadata:
                            usage = metadata['usage']
                            logger.debug(f'Found usage in metadata: {usage}')
                            usage_metrics.update(usage)
                            logger.debug(f'Updated usage_metrics: {usage_metrics}')

                        # Emit metadata event
                        sequence += 1
                        meta_dict = {}

                        if 'usage' in metadata:
                            meta_dict['usage'] = metadata['usage']

                        if 'metrics' in metadata:
                            meta_dict['metrics'] = metadata['metrics']

                        yield MetadataEvent(
                            response_id=response_message_id,
                            metadata=meta_dict,
                            sequence=sequence,
                            emit=True,
                            persist=True,
                        )

                    # Process status events directly from the model
                    elif 'status' in event_data:
                        status_data = event_data['status']
                        status_value = status_data.get('status', 'research_progress')
                        message = status_data.get(
                            'message', '{"title": "Processing..."}'
                        )

                        logger.info(f'Received direct status event: {status_value}')

                        sequence += 1
                        status_event = StatusEvent(
                            response_id=response_message_id,
                            status=status_value,
                            message=message,
                            sequence=sequence,
                            emit=True,
                            persist=True,
                        )
                        # Normalize the status event before yielding
                        yield normalize_status_event(status_event)

                    # Process error events
                    elif any(
                        error_type in event_data
                        for error_type in [
                            'modelStreamErrorException',
                            'serviceUnavailableException',
                            'throttlingException',
                            'validationException',
                            'internalServerException',
                        ]
                    ):
                        error_type = next(
                            (key for key in event_data if key.endswith('Exception')),
                            'unknown',
                        )
                        error_info = event_data.get(error_type, {})

                        sequence += 1
                        yield ErrorEvent(
                            response_id=response_message_id,
                            error_type=error_type,
                            message=error_info.get(
                                'message', 'Strands streaming error'
                            ),
                            details=error_info,
                            sequence=sequence,
                            emit=True,
                            persist=True,
                        )

                        # Also emit a response end with error status
                        sequence += 1
                        yield ResponseEndEvent(
                            response_id=response_message_id,
                            status='error',
                            usage=usage_metrics,
                            sequence=sequence,
                            emit=True,
                            persist=True,
                            chat_id=chat_id,
                        )
                        return

                # Emit any remaining pending ContentEvents before final end
                for _block_index, block_context in list(self._content_blocks.items()):
                    if (
                        hasattr(block_context, 'pending_content_events')
                        and block_context.pending_content_events
                        and isinstance(block_context.pending_content_events, list)
                    ):
                        logger.debug(
                            f'Emitting {len(block_context.pending_content_events)} remaining ContentEvents'
                        )
                        for event_data in block_context.pending_content_events:
                            sequence += 1
                            yield ContentEvent(
                                response_id=event_data['response_id'],
                                content=event_data['content'],
                                content_block_index=event_data['content_block_index'],
                                block_sequence=event_data['block_sequence'],
                                sequence=sequence,
                                emit=event_data['emit'],
                                persist=event_data['persist'],
                            )
                            logger.debug(
                                f'Final ContentEvent: {event_data["content"][:50]}...'
                            )

                        # Clear the pending events after emitting
                        block_context.pending_content_events.clear()

                # Final end event if not already emitted
                sequence += 1
                yield ResponseEndEvent(
                    response_id=response_message_id,
                    status='completed',
                    usage=usage_metrics,
                    sequence=sequence,
                    emit=True,
                    persist=True,
                    chat_id=chat_id,
                )

            except Exception as e:
                import traceback

                error_traceback = traceback.format_exc()
                logger.error(f'Error processing Strands event stream: {e!s}')
                logger.error(f'Error traceback: {error_traceback}')
                logger.error(f'Exception type: {type(e).__name__}, dir(e): {dir(e)}')

                # Clean up any remaining blocks
                remaining_blocks = list(self._content_blocks.keys())
                for _ in remaining_blocks:
                    self._cleanup_block_context(_)

                # Yield error event
                error_event = ErrorEvent(
                    response_id=response_message_id,
                    error_type=type(e).__name__,
                    message='Something went wrong, please contact us for details',
                    details={
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                    },
                    sequence=998,
                    emit=True,
                    persist=True,
                )
                logger.debug(f'Yielding error event: {type(error_event)}')
                yield error_event

                # Yield completion event with error status
                yield ResponseEndEvent(
                    response_id=response_message_id,
                    status='error',
                    usage={},
                    sequence=999,
                    emit=True,
                    persist=True,
                    chat_id=chat_id,
                )

        except Exception as e:
            import traceback

            error_traceback = traceback.format_exc()
            logger.error(f'Error in Strands demo handler: {e!s}')
            logger.error(f'Outer handler error traceback: {error_traceback}')
            logger.error(f'Outer exception type: {type(e).__name__}, dir(e): {dir(e)}')

            # Clean up any remaining blocks
            remaining_blocks = list(self._content_blocks.keys())
            for _ in remaining_blocks:
                self._cleanup_block_context(_)

            # Yield error event
            error_event = ErrorEvent(
                response_id=response_message_id,
                error_type=type(e).__name__,
                message='Something went wrong, please contact us for details',
                details={
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                },
                sequence=999,  # High sequence number to ensure it comes after other events
                emit=True,
                persist=True,
            )
            logger.debug(f'Yielding outer error event: {type(error_event)}')
            yield error_event

            # Yield completion event with error status
            yield ResponseEndEvent(
                response_id=response_message_id,
                status='error',
                usage={},
                sequence=1000,
                emit=True,
                persist=True,
                chat_id=chat_id,
            )
