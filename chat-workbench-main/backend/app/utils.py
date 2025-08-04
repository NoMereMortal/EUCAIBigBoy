# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Utility functions for the application."""

import inspect
import uuid
from datetime import date, datetime
from typing import Any, Literal

from nanoid import generate as nanoid_generate


def get_function_name() -> str:
    """Get function name."""
    return inspect.currentframe().f_back.f_code.co_name  # type: ignore


def make_json_serializable(obj: Any) -> Any:
    """Make an object JSON serializable.

    Args:
        obj: The object to make JSON serializable

    Returns:
        A JSON serializable version of the object
    """
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif hasattr(obj, 'model_dump'):
        # Handle Pydantic models
        return make_json_serializable(obj.model_dump())
    elif hasattr(obj, '__dict__'):
        # Handle objects with __dict__
        return make_json_serializable(obj.__dict__)
    else:
        # Fall back to string representation
        return str(obj)


def generate_nanoid(size: int = 21) -> str:
    """Generate a nanoid with consistent settings."""
    result = nanoid_generate(
        size=size,
        alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
    )
    if not isinstance(result, str):
        raise ValueError(
            f'Expected nanoid_generate to return str, got {type(result).__name__}'
        )
    return result


def mime_type_to_bedrock_format(
    mime_type: str | None = None,
    file_path: str | None = None,
    content_type: Literal['image', 'document'] = 'document',
) -> str:
    """Convert mime type to Bedrock-compatible format.

    Args:
        mime_type: The MIME type of the content
        file_path: Path or URI to the file, used as fallback for format detection
        content_type: Whether this is an image or document

    Returns:
        Format string compatible with Bedrock's format specification
    """
    # Image formats
    if content_type == 'image':
        if mime_type:
            image_formats = {
                'image/png': 'png',
                'image/jpeg': 'jpeg',
                'image/jpg': 'jpeg',
                'image/gif': 'gif',
                'image/webp': 'webp',
            }
            if mime_type in image_formats:
                return image_formats[mime_type]

        # Fall back to examining the file path (file extension)
        if file_path:
            path_lower = file_path.lower()
            if path_lower.endswith('.png'):
                return 'png'
            elif path_lower.endswith('.jpg') or path_lower.endswith('.jpeg'):
                return 'jpeg'
            elif path_lower.endswith('.gif'):
                return 'gif'
            elif path_lower.endswith('.webp'):
                return 'webp'

        # Default if we can't determine
        return 'png'

    # Document formats
    else:
        if mime_type:
            doc_formats = {
                'application/pdf': 'pdf',
                'text/csv': 'csv',
                'application/msword': 'doc',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
                'application/vnd.ms-excel': 'xls',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
                'text/html': 'html',
                'text/plain': 'txt',
                'text/markdown': 'md',
            }
            if mime_type in doc_formats:
                return doc_formats[mime_type]

        # Fall back to examining the file path (file extension)
        if file_path:
            path_lower = file_path.lower()
            if path_lower.endswith('.pdf'):
                return 'pdf'
            elif path_lower.endswith('.csv'):
                return 'csv'
            elif path_lower.endswith('.doc'):
                return 'doc'
            elif path_lower.endswith('.docx'):
                return 'docx'
            elif path_lower.endswith('.xls'):
                return 'xls'
            elif path_lower.endswith('.xlsx'):
                return 'xlsx'
            elif path_lower.endswith('.html'):
                return 'html'
            elif path_lower.endswith('.txt'):
                return 'txt'
            elif path_lower.endswith('.md'):
                return 'md'

        # Default if we can't determine
        return 'txt'
