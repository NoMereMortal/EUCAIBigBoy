# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

from typing import Annotated, Any

from loguru import logger
from pydantic import BaseModel, BeforeValidator, Field

from app.models import (
    CitationPart,
    DocumentPart,
    ImagePart,
    MessagePart,
    PartType,
    ReasoningPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)


def convert_to_proper_part_types(parts: list[Any]) -> list[PartType]:
    """
    Convert generic MessagePart objects to properly typed part instances based on part_kind.
    This validator ensures all parts are properly typed instances of MessagePart subclasses.
    """
    if not parts:
        return []

    validated_parts: list[PartType] = []

    for part in parts:
        # Skip None parts
        if part is None:
            continue

        try:
            # If it's already a MessagePart, make sure it's the right subclass
            if isinstance(part, MessagePart):
                logger.debug(
                    f'Converting generic MessagePart with kind {part.part_kind} to proper type'
                )

                # Extract data from the part
                part_data = (
                    part.model_dump() if hasattr(part, 'model_dump') else part.dict()
                )
                part_kind = part.part_kind

                # Create appropriate specific part type
                if part_kind == 'text':
                    validated_parts.append(TextPart(**part_data))
                elif part_kind == 'image':
                    validated_parts.append(ImagePart(**part_data))
                elif part_kind == 'document':
                    validated_parts.append(DocumentPart(**part_data))
                elif part_kind == 'tool-call':
                    validated_parts.append(ToolCallPart(**part_data))
                elif part_kind == 'tool-return':
                    validated_parts.append(ToolReturnPart(**part_data))
                elif part_kind == 'reasoning':
                    validated_parts.append(ReasoningPart(**part_data))
                elif part_kind == 'citation':
                    validated_parts.append(CitationPart(**part_data))
                else:
                    # Fallback to TextPart for unknown part_kind
                    content = part.content if hasattr(part, 'content') else str(part)
                    validated_parts.append(TextPart(content=content))

                continue

            # Try to convert dict/JSON to proper type
            if isinstance(part, dict):
                part_kind: str | None = part.get('part_kind')

                if part_kind == 'text':
                    validated_parts.append(TextPart(**part))
                elif part_kind == 'image':
                    validated_parts.append(ImagePart(**part))
                elif part_kind == 'document':
                    validated_parts.append(DocumentPart(**part))
                elif part_kind == 'tool-call':
                    validated_parts.append(ToolCallPart(**part))
                elif part_kind == 'tool-return':
                    validated_parts.append(ToolReturnPart(**part))
                elif part_kind == 'reasoning':
                    validated_parts.append(ReasoningPart(**part))
                elif part_kind == 'citation':
                    validated_parts.append(CitationPart(**part))
                else:
                    # Default to TextPart if no part_kind or unknown
                    if 'content' in part:
                        validated_parts.append(TextPart(content=part['content']))
                    else:
                        validated_parts.append(TextPart(content=str(part)))
            else:
                # For any other type, convert to TextPart
                validated_parts.append(TextPart(content=str(part)))

        except Exception as e:
            logger.error(f'Error in part type conversion validator: {e}')
            # Create a fallback TextPart to avoid losing data
            try:
                content = ''
                if isinstance(part, dict) and 'content' in part:
                    content = str(part['content'])
                elif hasattr(part, 'content'):
                    content = str(part.content)
                else:
                    content = str(part)

                validated_parts.append(
                    TextPart(content=f'[Error: {e!s}] {content[:50]}...')
                )
            except Exception as e:
                validated_parts.append(TextPart(content='[Error processing part]'))

    return validated_parts


# Use both validators to ensure proper handling of parts
ValidatedPartList = Annotated[
    list[PartType], BeforeValidator(convert_to_proper_part_types)
]


class GenerateRequest(BaseModel):
    """Request model for generation endpoints."""

    task: str = Field(
        ..., description='Task handler to use (chat, search, reasoning, etc)'
    )
    chat_id: str = Field(..., description='Chat session ID')
    parent_id: str | None = Field(
        None, description='Parent message ID (for branching conversations)'
    )
    parts: ValidatedPartList = Field(
        ..., description='Message parts (system prompt, user text, images, etc)'
    )
    model_id: str = Field(
        ...,
        description='Model ID to use (e.g. us.anthropic.claude-3-5-sonnet-20240620-v1:0)',
    )
    context: list[dict[str, Any]] | None = Field(
        None, description='Optional context for the generation'
    )
    persona: str | None = Field(
        None, description='Optional persona to use for generation'
    )


class GenerateResponse(BaseModel):
    """Response model for non-streaming generate endpoint."""

    message_id: str
    chat_id: str
    parts: list[MessagePart] = Field(..., description='Generated message parts')
    usage: dict[str, Any] = Field(default_factory=dict, description='Usage statistics')
    metadata: dict[str, Any] = Field(
        default_factory=dict, description='Additional metadata'
    )
