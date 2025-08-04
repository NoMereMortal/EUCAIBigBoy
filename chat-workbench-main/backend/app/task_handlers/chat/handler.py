# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Pure conversation handler using Strands Agent without any tools."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from botocore.config import Config as BotocoreConfig
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from loguru import logger
from strands import Agent

from app.clients.bedrock_runtime.client import BedrockRuntimeClient
from app.clients.opensearch.client import OpenSearchClient
from app.models import Message
from app.services.streaming.events import (
    BaseEvent,
    ContentEvent,
    ErrorEvent,
    MetadataEvent,
    ReasoningEvent,
    ResponseEndEvent,
    ToolCallEvent,
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
from app.tracing import create_span, trace_async_generator_function
from app.utils import generate_nanoid


class ChatHandler(BaseTaskHandler):
    """Chat handler using Strands Agent."""

    def __init__(
        self,
        opensearch_client: OpenSearchClient,
        bedrock_runtime_client: BedrockRuntimeClient,
        botocore_config: BotocoreConfig,
    ) -> None:
        super().__init__()
        # Maps contentBlockIndex -> ContentBlockContext
        self._content_blocks: dict[int, ContentBlockContext] = {}
        # Maps tool IDs to names for quick lookups across blocks
        self._tool_id_mapping: dict[str, str] = {}
        # Store clients for use in tools
        self._opensearch_client = opensearch_client
        self._bedrock_runtime_client = bedrock_runtime_client

    def _get_or_create_block_context(self, index: int) -> ContentBlockContext:
        """Get an existing block context or create a new one."""
        if index not in self._content_blocks:
            block_context = ContentBlockContext()
            # Type ignore since we know we can set this even if the type definition doesn't show it
            block_context.start_time = datetime.now(timezone.utc)  # type: ignore
            self._content_blocks[index] = block_context
        return self._content_blocks[index]

    def _cleanup_block_context(self, index):
        """Clean up a block context when no longer needed."""
        if index in self._content_blocks:
            # Log block completion for debugging
            block_ctx = self._content_blocks[index]
            logger.debug(
                f'Cleaning up block {index}: '
                f'type={block_ctx.block_type}, tool={block_ctx.tool_name}'
            )
            del self._content_blocks[index]

    @property
    def name(self) -> str:
        """Name of the task handler."""
        return 'chat'

    @property
    def description(self) -> str:
        """Description of the task handler."""
        return 'Pure conversation handler using Strands Agent'

    @property
    def tools(self) -> list[str]:
        """List of tools available to this task handler."""
        return []

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
        # Ensure all elements are strings before joining
        text_only_content = (
            ' '.join([str(part) for part in text_only_parts]) if text_only_parts else ''
        )

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

            # Set up Jinja2 environment
            env = Environment(loader=FileSystemLoader(prompts_dir), autoescape=True)
            template = env.get_template('system.xml.j2')

            # Render the template with persona
            context = {'persona': persona or 'You are a helpful AI assistant.'}

            rendered_prompt = template.render(context)
            logger.debug(f'Rendered system prompt with persona: {persona}')

            return rendered_prompt

        except TemplateNotFound as e:
            logger.error(f'System prompt template not found: {e}')
            return fallback

        except Exception as e:
            logger.error(f'Error rendering system prompt template: {e}')
            return fallback

    @trace_async_generator_function(name='ChatHandler.handle')
    async def handle(
        self,
        chat_id: str,
        message_history: list[Message],
        user_message: Message,
        model_id: str,
        response_message_id: str,
        context: list[dict[str, Any]]
        | None = None,  # Match the parent class parameter name
        persona: str | None = None,
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
                messages: list[dict[str, Any]] = []
                for message in message_history:
                    bedrock_message = await message.to_bedrock()
                    messages.append(bedrock_message)

                # Process user's message
                user_multimodal_messages, user_text = await self._convert_user_message(
                    user_message
                )

            # If we have multimodal messages, add them to the list
            if user_multimodal_messages:
                messages.extend(user_multimodal_messages)

            # Always add the text content as a message (if it exists)
            # This is critical to fix the ValidationException when text is blank
            if user_text:
                text_message = {'role': 'user', 'content': [{'text': user_text}]}
                messages.append(text_message)
                logger.debug(
                    f'Added text message to Bedrock request: {user_text[:50]}...'
                )
            else:
                logger.warning(
                    'No text content in user message, this may cause a validation error'
                )

            # Create a span for agent initialization
            with create_span('initialize_agent', attributes={'model_id': model_id}):
                # Render the system prompt using the template
                system_prompt = self._render_system_prompt(persona)

                # Log the model ID being used for debugging
                logger.debug(f"Using model ID: '{model_id}' (length: {len(model_id)})")

                # Ensure model ID is correctly formatted (no whitespace)
                model_id = model_id.strip()

                # Type annotation to help the type checker
                agent = Agent(
                    model=model_id,  # Explicitly pass the model ID
                    tools=[],
                    system_prompt=system_prompt,
                    messages=messages,  # type: ignore # messages are compatible with Agent's expectations
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

                    if 'event' not in event:
                        logger.warning("Event doesn't contain 'event' key")
                        continue

                    # Get event data and type
                    event_data = event['event']
                    event_type = get_event_type(event)

                    logger.debug(f'Type: {event_type}')

                    # Process messageStart events
                    if 'messageStart' in event_data:
                        # Just log the start, no event to emit
                        logger.debug('Message started')

                    # Process contentBlockStart events
                    elif 'contentBlockStart' in event_data:
                        block_start = event_data['contentBlockStart']
                        content_block_index = block_start.get('contentBlockIndex', 0)

                        # Get or create block context
                        block_ctx = self._get_or_create_block_context(
                            content_block_index
                        )

                        # Check for tool use starts
                        start_info = block_start.get('start', {})
                        if 'toolUse' in start_info:
                            tool_use = start_info['toolUse']
                            block_ctx.tool_name = tool_use.get('name', '')
                            block_ctx.tool_id = tool_use.get('toolUseId', '')
                            # Use type ignore since we know this is valid
                            block_ctx.block_type = 'tool_call'  # type: ignore

                            # Store in cross-block tool ID mapping
                            if block_ctx.tool_id and block_ctx.tool_name:
                                self._tool_id_mapping[block_ctx.tool_id] = (
                                    block_ctx.tool_name
                                )
                                logger.debug(
                                    f'Registered tool: {block_ctx.tool_name} with ID {block_ctx.tool_id} for block {content_block_index}'
                                )

                    # Process contentBlockDelta events
                    elif 'contentBlockDelta' in event_data:
                        delta_event = event_data['contentBlockDelta']
                        content_block_index = delta_event.get('contentBlockIndex', 0)
                        delta = delta_event.get('delta', {})

                        # Get context for this block
                        block_ctx = self._get_or_create_block_context(
                            content_block_index
                        )

                        # Handle text content - emit immediately
                        if 'text' in delta:
                            text = delta['text']
                            if block_ctx.block_type is None:
                                # Use type ignore since we know this is valid
                                block_ctx.block_type = 'text'  # type: ignore

                            # Increment block sequence counter
                            block_ctx.block_sequence_counter += 1

                            sequence += 1
                            yield ContentEvent(
                                response_id=response_message_id,
                                content=text,
                                content_block_index=content_block_index,
                                block_sequence=block_ctx.block_sequence_counter,
                                sequence=sequence,
                                emit=True,
                                persist=True,
                            )
                            logger.debug(f'Emitting text content: {text}')

                        # Handle tool use input - accumulate and emit with complete context
                        elif 'toolUse' in delta:
                            # Add to accumulated tool input
                            tool_input_fragment = delta['toolUse'].get('input', '')

                            if block_ctx.block_type is None:
                                # Use type ignore since we know this is valid
                                block_ctx.block_type = 'tool_call'  # type: ignore

                            block_ctx.accumulated_tool_input += tool_input_fragment

                            # Extract or retrieve tool info
                            tool_use = delta.get('toolUse', {})

                            # Get tool ID from delta if missing in context
                            if not block_ctx.tool_id:
                                block_ctx.tool_id = tool_use.get(
                                    'toolUseId', generate_nanoid()
                                )

                            # Try multiple methods to get the tool name
                            if not block_ctx.tool_name:
                                # 1. Try from delta directly
                                block_ctx.tool_name = tool_use.get('name', '')

                                # 2. Try from cross-block tool ID mapping
                                if (
                                    not block_ctx.tool_name
                                    and block_ctx.tool_id in self._tool_id_mapping
                                ):
                                    block_ctx.tool_name = self._tool_id_mapping[
                                        block_ctx.tool_id
                                    ]

                                # 3. No pattern matching needed - chat handler has no tools

                            # Emit tool call event with current state (will be updated with complete input later)
                            try:
                                tool_args = parse_tool_args(tool_input_fragment)
                                # Increment block sequence counter
                                block_ctx.block_sequence_counter += 1

                                sequence += 1
                                yield ToolCallEvent(
                                    response_id=response_message_id,
                                    tool_name=block_ctx.tool_name,
                                    tool_id=block_ctx.tool_id,
                                    tool_args=tool_args,
                                    content_block_index=content_block_index,
                                    block_sequence=block_ctx.block_sequence_counter,
                                    sequence=sequence,
                                    emit=True,
                                    persist=True,
                                )
                                logger.debug(
                                    f'Emitting tool call delta: {block_ctx.tool_name} (ID: {block_ctx.tool_id})'
                                )
                            except Exception as e:
                                logger.error(
                                    f'Error processing tool input fragment: {e}'
                                )

                        # Handle reasoning content (emit immediately)
                        elif 'reasoningContent' in delta:
                            reasoning = delta['reasoningContent']
                            if block_ctx.block_type is None:
                                # Use type ignore since we know this is valid
                                block_ctx.block_type = 'reasoning'  # type: ignore

                            # Increment block sequence counter
                            block_ctx.block_sequence_counter += 1

                            sequence += 1
                            yield ReasoningEvent(
                                response_id=response_message_id,
                                text=reasoning.get('text'),
                                signature=reasoning.get('signature'),
                                redacted_content=reasoning.get('redactedContent'),
                                content_block_index=content_block_index,
                                block_sequence=block_ctx.block_sequence_counter,
                                sequence=sequence,
                                emit=True,
                                persist=True,
                            )
                            logger.debug('Emitting reasoning event')

                    # Process contentBlockStop events
                    elif 'contentBlockStop' in event_data:
                        block_stop = event_data['contentBlockStop']
                        content_block_index = block_stop.get('contentBlockIndex', 0)

                        # Get final context for block before cleanup
                        if content_block_index in self._content_blocks:
                            block_ctx = self._content_blocks[content_block_index]
                            logger.debug(
                                f'Content block stopped: {content_block_index}, type={block_ctx.block_type}'
                            )

                            # For tool calls with accumulated input, process the complete input
                            if (
                                block_ctx.block_type == 'tool_call'
                                and block_ctx.accumulated_tool_input
                            ):
                                try:
                                    # Final emission of tool event with complete inputs
                                    if block_ctx.tool_name:
                                        # Only emit if we have a proper tool name
                                        logger.debug(
                                            f'Final tool call for {block_ctx.tool_name} with input: {block_ctx.accumulated_tool_input}'
                                        )
                                except Exception as e:
                                    logger.error(
                                        f'Error processing complete tool input: {e}'
                                    )

                            # Clean up the context
                            self._cleanup_block_context(content_block_index)

                    # Process messageStop events
                    elif 'messageStop' in event_data:
                        message_stop = event_data['messageStop']
                        stop_reason = message_stop.get('stopReason')

                        logger.debug(f'Message stopped with reason: {stop_reason}')

                        # Clean up any remaining blocks
                        remaining_blocks = list(self._content_blocks.keys())
                        for block_index in remaining_blocks:
                            self._cleanup_block_context(block_index)

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
                for block_index in remaining_blocks:
                    self._cleanup_block_context(block_index)

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
            remaining_blocks = list(getattr(self, '_content_blocks', {}).keys())
            for block_index in remaining_blocks:
                self._cleanup_block_context(block_index)

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

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> 'ChatHandler':
        """Create an instance from configuration."""
        # Initialize clients from config
        opensearch_client = OpenSearchClient.from_config(config)
        bedrock_runtime_client = BedrockRuntimeClient.from_config(config)
        botocore_config = BotocoreConfig()

        return cls(
            opensearch_client=opensearch_client,
            bedrock_runtime_client=bedrock_runtime_client,
            botocore_config=botocore_config,
        )
