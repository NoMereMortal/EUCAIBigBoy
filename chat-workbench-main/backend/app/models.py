# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from datetime import datetime, timezone
from typing import Annotated, Any, Literal, TypeVar, Union

from loguru import logger
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    Discriminator,
    Field,
    Tag,
)

from app.utils import generate_nanoid, mime_type_to_bedrock_format

# Define a type variable for MessagePart subclasses
MP = TypeVar('MP', bound='MessagePart')


# Define validator functions outside of the class
def validate_content(v):
    """Validate that content is not empty."""
    if v is None:
        raise ValueError('Content field must not be empty')
    if isinstance(v, str) and not v.strip():
        raise ValueError('Content field must not be empty string')
    if (
        isinstance(v, dict)
        and 'text' in v
        and (not v['text'] or not str(v['text']).strip())
    ):
        raise ValueError('Content.text field must not be empty')
    return v


class MessagePart(BaseModel):
    """Base class for all message parts."""

    part_kind: Literal[
        'text',
        'image',
        'document',
        'tool-call',
        'tool-return',
        'reasoning',
        'citation',
    ]
    content: Annotated[
        Any,
        Field(..., description='Content must not be empty'),
        AfterValidator(validate_content),
    ]
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    async def to_bedrock(self) -> dict[str, Any]:
        """
        Convert a MessagePart to the Amazon Bedrock format.
        Must be implemented by subclasses.

        Returns:
            dict: A dictionary in the Bedrock part format
        """
        raise NotImplementedError('Subclasses must implement to_bedrock()')


class TextPart(MessagePart):
    """Text content part."""

    part_kind: Literal[
        'text',
        'image',
        'document',
        'tool-call',
        'tool-return',
        'reasoning',
        'citation',
    ] = 'text'
    content: str

    async def to_bedrock(self) -> dict[str, Any]:
        """Convert TextPart to Bedrock format"""
        return {'text': self.content}


def ensure_image_content(v, info):
    """Ensure content field is present for ImagePart."""
    if v is None:
        # Use a descriptive name based on file_id or mime_type
        file_id = info.data.get('file_id', 'unknown')
        return f'[Image: {file_id}]'
    return v


class ImagePart(MessagePart):
    """Image content part."""

    part_kind: Literal[
        'text',
        'image',
        'document',
        'tool-call',
        'tool-return',
        'reasoning',
        'citation',
    ] = 'image'
    file_id: str  # Unique file identifier
    user_id: str  # Owner user ID
    mime_type: str
    width: int | None = None
    height: int | None = None
    format: str | None = None  # Format for Bedrock (jpeg, png, etc.)
    content: Annotated[Any, BeforeValidator(ensure_image_content)]

    def __init__(self, **data):
        # Ensure content field exists before initialization
        if 'content' not in data or data['content'] is None:
            # Create a content field based on available information
            file_id = data.get('file_id', 'unknown')
            data['content'] = f'[Image: {file_id}]'
            logger.debug(
                f'Auto-generated content field for ImagePart: {data["content"]}'
            )
        super().__init__(**data)

    async def to_bedrock(self, content_storage_service=None) -> dict[str, Any]:
        """
        Convert ImagePart to Bedrock format

        Args:
            content_storage_service: Optional ContentStorageService to resolve file ID to pointer
        """
        if content_storage_service:
            # Resolve file ID to pointer
            pointer = await content_storage_service.get_pointer_from_id(
                file_id=self.file_id, user_id=self.user_id
            )

            if not pointer:
                # If pointer resolution fails, return a placeholder
                return {'text': f'[Image {self.file_id} not found]'}
        else:
            # No content service provided, cannot resolve
            return {'text': f'[Image {self.file_id} - pointer resolution unavailable]'}

        # Determine format from part data or from mime_type
        _format = mime_type_to_bedrock_format(
            mime_type=self.mime_type, file_path=pointer, content_type='image'
        )

        return {
            'image': {'format': _format, 'source': {'s3Location': {'uri': pointer}}}
        }


def ensure_document_content(v, info):
    """Ensure content field is present for DocumentPart."""
    if v is None:
        # Use title if available, otherwise use file_id
        title = info.data.get('title')
        file_id = info.data.get('file_id', 'unknown')
        return f'[Document: {title or file_id}]'
    return v


class DocumentPart(MessagePart):
    """Document content part."""

    part_kind: Literal[
        'text',
        'image',
        'document',
        'tool-call',
        'tool-return',
        'reasoning',
        'citation',
    ] = 'document'
    file_id: str  # Unique file identifier
    mime_type: str
    pointer: str | None = None
    title: str | None = None
    user_id: str | None = None  # Owner user ID
    page_count: int | None = None
    word_count: int | None = None
    content: Annotated[Any, BeforeValidator(ensure_document_content)]

    def __init__(self, **data):
        # Ensure content field exists before initialization
        if 'content' not in data or data['content'] is None:
            # Create a content field based on available information
            title = data.get('title')
            file_id = data.get('file_id', 'unknown')
            data['content'] = f'[Document: {title or file_id}]'
            logger.debug(
                f'Auto-generated content field for DocumentPart: {data["content"]}'
            )
        super().__init__(**data)

    async def to_bedrock(self, content_storage_service=None) -> dict[str, Any]:
        """
        Convert DocumentPart to Bedrock format

        Args:
            content_storage_service: Optional ContentStorageService to resolve file ID to pointer
        """
        if content_storage_service:
            # Resolve file ID to pointer
            pointer = await content_storage_service.get_pointer_from_id(
                file_id=self.file_id, user_id=self.user_id
            )

            if not pointer:
                # If pointer resolution fails, return a placeholder
                return {'text': f'[Document {self.file_id} not found]'}
        else:
            # No content service provided, cannot resolve
            return {
                'text': f'[Document {self.file_id} - pointer resolution unavailable]'
            }

        # Determine format from part data or from mime_type
        _format = mime_type_to_bedrock_format(
            mime_type=self.mime_type, file_path=pointer, content_type='document'
        )

        document_name = self.title
        if not document_name:
            # Try to extract name from pointer
            document_name = pointer.split('/')[-1] if '/' in pointer else self.file_id

        return {
            'document': {
                'format': _format,
                'name': document_name,
                'source': {'s3Location': {'uri': pointer}},
            }
        }


class ToolCallPart(MessagePart):
    """Tool call part."""

    part_kind: Literal[
        'text',
        'image',
        'document',
        'tool-call',
        'tool-return',
        'reasoning',
        'citation',
    ] = 'tool-call'
    tool_name: str
    tool_args: dict[str, Any]
    tool_calls: list[dict[str, Any]] | None = None
    tool_id: str = Field(default_factory=generate_nanoid)
    content: Any | None = Field(default=None)  # Override to make it optional

    async def to_bedrock(self) -> dict[str, Any]:
        """Convert ToolCallPart to Bedrock format"""
        return {
            'toolUse': {
                'toolUseId': self.tool_id,
                'name': self.tool_name,
                'input': self.tool_args,
            }
        }


class ToolReturnPart(MessagePart):
    """Tool result part."""

    part_kind: Literal[
        'text',
        'image',
        'document',
        'tool-call',
        'tool-return',
        'reasoning',
        'citation',
    ] = 'tool-return'
    tool_name: str
    tool_id: str
    result: Any
    content: Any | None = Field(default=None)  # Override to make it optional

    async def to_bedrock(self) -> dict[str, Any]:
        """Convert ToolReturnPart to Bedrock format"""
        # Prepare content based on the result type
        content = []

        if isinstance(self.result, dict):
            # Convert dictionary result to format with proper typing
            if 'json' in self.result:
                content.append({'json': self.result['json']})
            if 'text' in self.result:
                content.append({'text': self.result['text']})
            if 'image' in self.result:
                img = self.result['image']
                content.append(
                    {
                        'image': {
                            'format': img.get('format', 'png'),
                            'source': img.get('source', {}),
                        }
                    }
                )
            if 'document' in self.result:
                doc = self.result['document']
                content.append(
                    {
                        'document': {
                            'format': doc.get('format', 'txt'),
                            'name': doc.get('name', 'document'),
                            'source': doc.get('source', {}),
                        }
                    }
                )
        elif isinstance(self.result, str):
            content.append({'text': self.result})
        else:
            # Convert non-string result to string
            content.append({'text': str(self.result)})

        # If no content was created, use a default text representation
        if not content:
            content.append({'text': str(self.result)})

        return {
            'toolResult': {
                'toolUseId': self.tool_id,
                'content': content,
                'status': 'success',  # Assuming success by default
            }
        }


class ReasoningPart(MessagePart):
    """Reasoning content part from model thinking."""

    part_kind: Literal[
        'text',
        'image',
        'document',
        'tool-call',
        'tool-return',
        'reasoning',
        'citation',
    ] = 'reasoning'
    content: str
    signature: str | None = None
    redacted_content: bytes = Field(default=b'')  # Default to empty bytes

    async def to_bedrock(self) -> dict[str, Any]:
        """Convert ReasoningPart to Bedrock format with proper reasoningContent structure"""
        return {
            'reasoningContent': {
                'reasoningText': {
                    'text': self.content,
                    'signature': self.signature or '',
                },
                'redactedContent': self.redacted_content,
            }
        }


class CitationPart(MessagePart):
    """Citation part referencing document content."""

    part_kind: Literal[
        'text',
        'image',
        'document',
        'tool-call',
        'tool-return',
        'reasoning',
        'citation',
    ] = 'citation'
    document_id: str
    text: str
    page: int | None = None
    section: str | None = None
    content: str = Field(default='')  # Ensure content is properly set and serialized
    citation_id: str | None = None
    reference_number: str | None = None  # For UI display
    document_title: str | None = None  # For UI display
    document_pointer: str | None = None  # For storage reference

    def __init__(self, **data):
        # Log the raw input data for debugging
        citation_id = data.get('citation_id', 'unknown')
        document_id = data.get('document_id', 'unknown')
        text_preview = data.get('text', '')[:50] + (
            '...' if len(data.get('text', '')) > 50 else ''
        )
        content_preview = data.get('content', '')[:50] + (
            '...' if len(data.get('content', '')) > 50 else ''
        )

        logger.debug(
            f'CitationPart.__init__ BEFORE: citation_id={citation_id}, document_id={document_id}, '
            f"text_len={len(data.get('text', ''))}, text='{text_preview}', "
            f"content_len={len(data.get('content', ''))}, content='{content_preview}'"
        )

        # Ensure both 'text' and 'content' fields are present and synchronized
        has_text = 'text' in data and data['text']
        has_content = 'content' in data and data['content']

        # Case 1: Text exists but content is missing or empty
        if has_text and not has_content:
            # Generate a formatted content field
            document_id = data.get('document_id', 'unknown')
            text = data['text']
            page = data.get('page')
            page_info = f' (page {page})' if page else ''
            data['content'] = (
                f'[Citation from {document_id}{page_info}]: {text[:100]}...'
                if len(text) > 100
                else f'[Citation from {document_id}{page_info}]: {text}'
            )
            logger.debug(
                f"CitationPart: Auto-generated content field: '{data['content'][:100]}...'"
            )

        # Case 2: Content exists but text is missing or empty
        elif has_content and not has_text:
            # Text should reflect the actual citation content, without the formatting
            # If content includes our standard prefix, extract the actual content
            content = data['content']
            if content.startswith('[Citation from'):
                # Try to extract just the text portion after the colon
                try:
                    # Find the position of the first colon
                    colon_pos = content.find(']:')
                    if colon_pos > 0:
                        # Extract everything after "]: "
                        data['text'] = content[colon_pos + 2 :].strip()
                        logger.debug(
                            f"CitationPart: Extracted text from content: '{data['text'][:100]}...'"
                        )
                    else:
                        # If no colon found, just use content as text
                        data['text'] = content
                        logger.debug(
                            f"CitationPart: Used content as text (no extraction): '{data['text'][:100]}...'"
                        )
                except Exception as e:
                    # If extraction fails, just use content directly
                    logger.warning(
                        f'CitationPart: Error extracting text from content: {e}'
                    )
                    data['text'] = content
                    logger.debug(
                        f"CitationPart: Used full content as text after error: '{data['text'][:100]}...'"
                    )
            else:
                # If content doesn't match our expected format, use it directly
                data['text'] = content
                logger.debug(
                    f"CitationPart: Synchronized text with content directly: '{data['text'][:100]}...'"
                )

        # Case 3: Both missing (should be caught by validators, but just in case)
        elif not has_text and not has_content:
            # Set default values to prevent validation errors
            data['text'] = 'No citation content available'
            data['content'] = '[Citation: No content available]'
            logger.warning(
                f'CitationPart: Both text and content were empty, setting defaults. citation_id={citation_id}, document_id={document_id}'
            )

        # Case 4: Both exist already - no synchronization needed
        # This is the normal case, nothing to do

        # Log final state before calling parent init
        logger.debug(
            f'CitationPart.__init__ AFTER: document_id={document_id}, '
            f'text_len={len(data.get("text", ""))}, content_len={len(data.get("content", ""))}, '
            f"text='{data.get('text', '')[:50]}...', content='{data.get('content', '')[:50]}...'"
        )

        super().__init__(**data)

    # Add property setter/getter for text and content to keep them in sync during usage
    @property
    def text(self) -> str:  # type: ignore[no-redef]
        return self.__dict__.get('text', '')

    @text.setter
    def text(self, value: str) -> None:
        # Update the text field
        self.__dict__['text'] = value

        # Also update content field to stay in sync, preserving format if possible
        current_content = self.__dict__.get('content', '')
        if current_content and current_content.startswith('[Citation from'):
            # Try to replace just the text part, keeping the prefix
            try:
                colon_pos = current_content.find(']:')
                if colon_pos > 0:
                    prefix = (
                        current_content[: colon_pos + 2] + ' '
                    )  # Include the colon and space
                    self.__dict__['content'] = f'{prefix}{value}'
                else:
                    # If format doesn't match, recreate the full content
                    page_info = f' (page {self.page})' if self.page else ''
                    self.__dict__['content'] = (
                        f'[Citation from {self.document_id}{page_info}]: {value[:100]}...'
                        if len(value) > 100
                        else f'[Citation from {self.document_id}{page_info}]: {value}'
                    )
            except Exception:
                # On any error, just set content to match text
                self.__dict__['content'] = value
        else:
            # If content doesn't have expected format, just set it directly
            self.__dict__['content'] = value

    async def to_bedrock(self) -> dict[str, Any]:
        """Convert CitationPart to Bedrock format (as text)"""
        # Log before serialization
        logger.debug(
            f'CitationPart.to_bedrock: START with document_id={self.document_id}, '
            f'text_len={len(self.text)}, content_len={len(self.content)}, '
            f"text='{self.text[:50]}...', content='{self.content[:50]}...'"
        )

        page_info = f' (page {self.page})' if self.page else ''
        section_info = f', section: {self.section}' if self.section else ''
        citation_id = f' Citation ID: {self.citation_id}' if self.citation_id else ''
        citation_text = f'[Citation from {self.document_id}{page_info}{section_info}]: {self.text}.{citation_id}'

        # Log after serialization
        logger.debug(
            f"CitationPart.to_bedrock: END with citation_text='{citation_text[:100]}...'"
        )

        return {'text': citation_text}


# Function to get the part_kind from a dict or object for use with the Discriminator
def get_part_kind(v: Any) -> str | None:
    if isinstance(v, dict):
        return v.get('part_kind')
    return getattr(v, 'part_kind', None)


# Define the discriminated union type for MessagePart subclasses
PartType = Annotated[
    Union[
        Annotated[TextPart, Tag('text')],
        Annotated[CitationPart, Tag('citation')],
        Annotated[ImagePart, Tag('image')],
        Annotated[DocumentPart, Tag('document')],
        Annotated[ToolCallPart, Tag('tool-call')],
        Annotated[ToolReturnPart, Tag('tool-return')],
        Annotated[ReasoningPart, Tag('reasoning')],
    ],
    Discriminator(get_part_kind),
]


class Message(BaseModel):
    """Base message model for all message types."""

    message_id: str
    chat_id: str
    parent_id: str | None = None
    kind: Literal['request', 'response']
    parts: list[PartType] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = 'complete'  # complete, pending, processing, error

    def __init__(self, **data: Any) -> None:
        # If parts is passed as empty or missing, initialize it
        if 'parts' not in data or not data['parts']:
            data['parts'] = []
            logger.debug(
                f'Initializing empty parts array for message {data.get("message_id", "unknown")}'
            )

        super().__init__(**data)
        if self.parent_id is None:
            self.parent_id = self.chat_id  # Use chat_id as parent_id for root messages

        # Log message creation details
        logger.debug(f'Created message {self.message_id} with {len(self.parts)} parts')

    async def to_bedrock(self, content_storage_service=None) -> dict[str, Any]:
        """
        Convert a Message to the Amazon Bedrock message format.

        Args:
            content_storage_service: Optional ContentStorageService to resolve file IDs

        Returns:
            dict: A dictionary in the Bedrock message format
        """
        role = 'user' if self.kind == 'request' else 'assistant'

        content_parts = []
        for part in self.parts:
            try:
                # Check if the part has a to_bedrock method that accepts the content storage service
                if hasattr(part, 'to_bedrock'):
                    if (
                        isinstance(part, (ImagePart, DocumentPart))
                        and content_storage_service
                    ):
                        # For parts that need content resolution
                        bedrock_part = await part.to_bedrock(content_storage_service)
                    else:
                        # For simpler parts
                        bedrock_part = await part.to_bedrock()

                    content_parts.append(bedrock_part)
                else:
                    # Fallback for unknown part types
                    if hasattr(part, 'content') and isinstance(part.content, str):
                        content_parts.append({'text': part.content})
                    else:
                        content_parts.append({'text': str(part)})
            except Exception as e:
                # Log error and try fallback conversion
                logger.error(f'Error converting part {part.part_kind}: {e}')
                # Fallback to text representation
                if hasattr(part, 'content') and isinstance(part.content, str):
                    content_parts.append({'text': part.content})
                else:
                    content_parts.append({'text': str(part)})

        return {'role': role, 'content': content_parts}

    @staticmethod
    async def to_bedrock_messages(
        messages: list['Message'], content_storage_service=None
    ) -> list[dict[str, Any]]:
        """
        Convert a list of Message objects to a list in the Amazon Bedrock message format.

        Args:
            messages: A list of Message objects
            content_storage_service: Optional ContentStorageService to resolve file IDs

        Returns:
            list: A list of dictionaries in the Bedrock message format

        Example:
            ```
            # Get messages from a chat session
            messages = chat_session.messages

            # Get content storage service
            content_storage_service = get_content_storage_service()

            # Convert to Bedrock format
            bedrock_messages = await Message.to_bedrock_messages(
                messages,
                content_storage_service
            )

            # Use with Bedrock client
            response = bedrock_client.invoke_model(
                modelId="us.anthropic.claude-3-5-sonnet-20240620-v1:0",
                contentType="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2048,
                    "messages": bedrock_messages
                })
            )
            ```
        """
        result = []
        for message in messages:
            bedrock_message = await message.to_bedrock(content_storage_service)
            result.append(bedrock_message)
        return result


class ModelRequest(Message):
    """Model request message."""

    kind: Literal['request', 'response'] = 'request'


class ModelResponse(Message):
    """Model response message."""

    kind: Literal['request', 'response'] = 'response'
    model_name: str = ''
    usage: dict[str, int] = Field(default_factory=dict)


class ChatSession(BaseModel):
    """Chat session model."""

    chat_id: str = Field(default_factory=generate_nanoid)
    user_id: str
    title: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = 'active'  # active, archived, deleted
    messages: list[Message] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)  # Integrated metrics


# Streaming support
class StreamEvent(BaseModel):
    """Event for streaming updates."""

    type: Literal['content', 'metadata', 'status', 'error']
    data: Any
    sequence: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StreamedPartUpdate(BaseModel):
    """Update for a streaming part."""

    part_index: int
    content_delta: str
    content_complete: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ListChatSessions(BaseModel):
    """List chat sessions response."""

    chats: list[ChatSession]
    last_evaluated_key: dict[str, Any] | None = None
