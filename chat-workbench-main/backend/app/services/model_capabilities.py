# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

import re
from typing import ClassVar


class ModelCapabilities:
    """Registry of model capabilities for content types."""

    # Default supported types for all models
    DEFAULT_SUPPORTED_TYPES: ClassVar[set[str]] = {
        'text/plain',
    }

    # Model-specific capabilities
    MODEL_CAPABILITIES: ClassVar[dict[str, set[str]]] = {
        'us.anthropic.claude-3-5-sonnet-20241022-v2:0': {
            'image/jpeg',
            'image/png',
            'image/gif',
            'application/pdf',
            'text/csv',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # docx
        },
        'us.anthropic.claude-3-5-sonnet-20240620-v1:0': {
            'image/jpeg',
            'image/png',
            'image/gif',
            'application/pdf',
            'text/csv',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # docx
        },
        'us.anthropic.claude-3-7-sonnet-20250219-v1:0': {
            'image/jpeg',
            'image/png',
            'image/gif',
            'application/pdf',
            'text/csv',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # docx
        },
    }

    # File size limits (in bytes)
    FILE_SIZE_LIMITS: ClassVar[dict[str, int]] = {
        'default': 20 * 1024 * 1024,  # 20MB default
        'image': 5 * 1024 * 1024,  # 5MB for images
        'document': 10 * 1024 * 1024,  # 10MB for documents
    }

    @classmethod
    def get_supported_types(cls, model_id: str) -> set[str]:
        """Get supported content types for a model."""
        # Start with default types
        supported = cls.DEFAULT_SUPPORTED_TYPES.copy()

        # Add model-specific types if available
        model_types = cls.MODEL_CAPABILITIES.get(model_id, set())
        supported.update(model_types)

        return supported

    @classmethod
    def normalize_model_id(cls, model_id: str) -> str:
        """Normalize model ID to standardized format for lookup."""
        # Try to find a direct match first
        if model_id in cls.MODEL_CAPABILITIES:
            return model_id

        # Extract base model without version
        # Examples: anthropic.claude-3-opus-20240229 -> anthropic.claude-3-opus
        # or openai:gpt-4-vision-preview -> openai:gpt-4-vision
        base_pattern = r'^(.+?[:.]([\w-]+)(?:-\d+.*)?)'
        match = re.match(base_pattern, model_id)
        if match:
            base_model = match.group(1)
            # Check both separator formats
            if ':' in base_model:
                provider, model_name = base_model.split(':', 1)
                alt_model = f'{provider}.{model_name}'
            else:
                provider, model_name = base_model.split('.', 1)
                alt_model = f'{provider}:{model_name}'

            # Try both formats
            for m in [base_model, alt_model]:
                if m in cls.MODEL_CAPABILITIES:
                    return m

        # Fall back to looking for partial match
        for supported_model in cls.MODEL_CAPABILITIES:
            # Convert colons to dots or vice versa to check alternative format
            if ':' in supported_model and supported_model.replace(':', '.') in model_id:
                return supported_model
            if '.' in supported_model and supported_model.replace('.', ':') in model_id:
                return supported_model

        # No match found, return original
        return model_id

    @classmethod
    def is_supported(cls, model_id: str, mime_type: str) -> bool:
        """Check if a content type is supported by the model."""
        # Normalize model ID
        normalized_id = cls.normalize_model_id(model_id)

        # Get supported types
        supported_types = cls.get_supported_types(normalized_id)

        # Check direct match
        if mime_type in supported_types:
            return True

        # Check mime type category (e.g., image/*)
        category = mime_type.split('/')[0] + '/*'
        return category in supported_types

    @classmethod
    def supports_images(cls, model_id: str) -> bool:
        """Check if a model supports image inputs."""
        normalized_id = cls.normalize_model_id(model_id)
        supported_types = cls.get_supported_types(normalized_id)
        return any(t.startswith('image/') for t in supported_types)

    @classmethod
    def supports_documents(cls, model_id: str) -> bool:
        """Check if a model supports document inputs."""
        normalized_id = cls.normalize_model_id(model_id)
        supported_types = cls.get_supported_types(normalized_id)
        return any(
            t.startswith('application/') or t.startswith('text/')
            for t in supported_types
            if t != 'text/plain'
        )

    @classmethod
    def supports_multimodal(cls, model_id: str) -> bool:
        """Check if a model supports any non-text inputs."""
        return cls.supports_images(model_id) or cls.supports_documents(model_id)

    @classmethod
    def get_size_limit(cls, mime_type: str) -> int:
        """Get file size limit for content type."""
        category = mime_type.split('/')[0]

        if category == 'image':
            return cls.FILE_SIZE_LIMITS['image']
        elif category in ('application', 'text'):
            return cls.FILE_SIZE_LIMITS['document']
        else:
            return cls.FILE_SIZE_LIMITS['default']
